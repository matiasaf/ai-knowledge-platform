"""Streaming validation and persistence of uploaded PDFs.

Uploads are written to a temporary sibling file and moved into place only once the
whole payload has been validated, so `data/documents` never exposes a partial PDF.
"""

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from fastapi import UploadFile, status

from ai_knowledge_platform.documents.domain import (
    PDF_SIGNATURE,
    Document,
    DocumentExtraction,
    DocumentStatus,
    ExtractedPage,
)
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
    metadata_partial_path = metadata_path.with_suffix(".json.part")

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
        for path in (partial_path, content_path, metadata_path, metadata_partial_path):
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
    _write_json_atomically(path, payload)


def load_document(documents_dir: Path, document_id: UUID) -> Document:
    """Load a document snapshot or report an explicit missing/corrupt state."""
    metadata_path = documents_dir / f"{document_id}.json"
    if not metadata_path.is_file():
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.DOCUMENT_NOT_FOUND,
            message=f"Document {document_id} was not found.",
        )

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        document = Document(
            id=UUID(payload["id"]),
            filename=payload["filename"],
            byte_size=payload["byte_size"],
            content_type=payload["content_type"],
            status=DocumentStatus(payload["status"]),
            created_at=datetime.fromisoformat(payload["created_at"]),
            updated_at=datetime.fromisoformat(payload["updated_at"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise _corrupt_storage_error(document_id, "metadata") from exc

    if document.id != document_id:
        raise _corrupt_storage_error(document_id, "metadata")
    return document


def update_document_status(
    document: Document,
    status_value: DocumentStatus,
    documents_dir: Path,
) -> Document:
    """Persist a state transition and return the updated immutable snapshot."""
    updated = document.with_status(status_value)
    _write_metadata(documents_dir / f"{document.id}.json", updated)
    return updated


def document_content_path(documents_dir: Path, document_id: UUID) -> Path:
    return documents_dir / f"{document_id}.pdf"


def persist_extraction(documents_dir: Path, extraction: DocumentExtraction) -> None:
    """Atomically persist all page spans only after extraction completed."""
    payload: dict[str, object] = {
        "schema_version": 1,
        "document_id": str(extraction.document_id),
        "extracted_at": extraction.extracted_at.isoformat(),
        "pages": [
            {
                "page_number": page.page_number,
                "text": page.text,
                "character_count": page.character_count,
            }
            for page in extraction.pages
        ],
    }
    _write_json_atomically(
        documents_dir / f"{extraction.document_id}.extraction.json",
        payload,
    )


def load_extraction(documents_dir: Path, document_id: UUID) -> DocumentExtraction:
    """Load an existing extraction, validating its page provenance."""
    extraction_path = documents_dir / f"{document_id}.extraction.json"
    if not extraction_path.is_file():
        raise _corrupt_storage_error(document_id, "extraction")

    try:
        payload = json.loads(extraction_path.read_text(encoding="utf-8"))
        if payload["schema_version"] != 1 or UUID(payload["document_id"]) != document_id:
            raise ValueError
        pages = tuple(
            ExtractedPage(page_number=page["page_number"], text=page["text"])
            for page in payload["pages"]
        )
        if any(
            page.page_number != expected_page or page.character_count != source["character_count"]
            for expected_page, (page, source) in enumerate(
                zip(pages, payload["pages"], strict=True), start=1
            )
        ):
            raise ValueError
        return DocumentExtraction(
            document_id=document_id,
            pages=pages,
            extracted_at=datetime.fromisoformat(payload["extracted_at"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise _corrupt_storage_error(document_id, "extraction") from exc


def remove_extraction(documents_dir: Path, document_id: UUID) -> None:
    """Remove partial or completed derived data after a failed attempt."""
    extraction_path = documents_dir / f"{document_id}.extraction.json"
    extraction_path.unlink(missing_ok=True)
    extraction_path.with_suffix(".json.part").unlink(missing_ok=True)


def _write_json_atomically(path: Path, payload: Mapping[str, object]) -> None:
    partial_path = path.with_suffix(f"{path.suffix}.part")
    partial_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    partial_path.replace(path)


def _corrupt_storage_error(document_id: UUID, artifact: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=ErrorCode.INTERNAL_ERROR,
        message=f"Stored {artifact} for document {document_id} is missing or invalid.",
    )
