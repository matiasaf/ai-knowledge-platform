"""Streaming validation and persistence of uploaded PDFs.

Uploads are written to a temporary sibling file and moved into place only once the
whole payload has been validated, so `data/documents` never exposes a partial PDF.
"""

import json
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile, status

from ai_knowledge_platform.documents.domain import PDF_SIGNATURE, Document
from ai_knowledge_platform.errors import ApiError, ErrorCode

CHUNK_SIZE = 64 * 1024


async def store_document(
    upload: UploadFile,
    *,
    documents_dir: Path,
    max_bytes: int,
) -> Document:
    """Validate the upload while streaming it to disk and return the stored document.

    Raises `ApiError` for oversized payloads and for content that is not a PDF.
    """
    documents_dir.mkdir(parents=True, exist_ok=True)

    document_id = uuid4()
    # The client-supplied filename is metadata only; it never reaches the filesystem,
    # which keeps path traversal and name collisions out of the problem space.
    content_path = documents_dir / f"{document_id}.pdf"
    metadata_path = documents_dir / f"{document_id}.json"
    partial_path = documents_dir / f"{document_id}.part"

    try:
        with partial_path.open("wb") as sink:
            byte_size = await _stream_validated_pdf(upload, sink, max_bytes=max_bytes)

        partial_path.replace(content_path)

        document = Document.stored(
            document_id=document_id,
            filename=upload.filename or "",
            byte_size=byte_size,
        )
        _write_metadata(metadata_path, document)
    except BaseException:
        # Cleanup covers rejections, storage faults and request cancellation alike:
        # later ingestion stages must be able to trust everything under data/documents.
        for path in (partial_path, content_path, metadata_path):
            path.unlink(missing_ok=True)
        raise

    return document


async def _stream_validated_pdf(upload: UploadFile, sink: BinaryIO, *, max_bytes: int) -> int:
    """Copy the upload into `sink` in bounded chunks and return the byte count."""
    header = await _read_exactly(upload, len(PDF_SIGNATURE))
    if not header.startswith(PDF_SIGNATURE):
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.INVALID_PDF,
            message="File content is not a PDF: the %PDF- signature is missing.",
        )

    byte_size = 0
    chunk = header
    while chunk:
        byte_size += len(chunk)
        if byte_size > max_bytes:
            raise ApiError(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                code=ErrorCode.FILE_TOO_LARGE,
                message=f"File exceeds the maximum upload size of {max_bytes} bytes.",
            )
        sink.write(chunk)
        chunk = await upload.read(CHUNK_SIZE)

    return byte_size


async def _read_exactly(upload: UploadFile, size: int) -> bytes:
    """Read `size` bytes, tolerating a stream that hands back short chunks."""
    buffer = b""
    while len(buffer) < size:
        chunk = await upload.read(size - len(buffer))
        if not chunk:
            break
        buffer += chunk
    return buffer


def _write_metadata(path: Path, document: Document) -> None:
    """Persist the JSON sidecar. Its keys mirror the API response by design."""
    payload: dict[str, str | int] = {
        "id": str(document.id),
        "filename": document.filename,
        "byte_size": document.byte_size,
        "content_type": document.content_type,
        "status": document.status.value,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
