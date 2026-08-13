"""Bounded PDF text extraction with page-level source provenance."""

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import UUID

from fastapi import status
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from starlette.concurrency import run_in_threadpool

from ai_knowledge_platform.documents.domain import (
    Document,
    DocumentExtraction,
    DocumentStatus,
    ExtractedPage,
)
from ai_knowledge_platform.documents.storage import (
    document_content_path,
    load_document,
    load_extraction,
    persist_extraction,
    remove_extraction,
    update_document_status,
)
from ai_knowledge_platform.errors import ApiError, ErrorCode

_active_extractions: set[UUID] = set()
_active_extractions_guard = Lock()


async def extract_stored_document(
    document_id: UUID,
    *,
    documents_dir: Path,
    max_pages: int,
) -> tuple[Document, DocumentExtraction]:
    """Extract and persist one stored PDF, returning an idempotent result on repeats."""
    if not _claim_extraction(document_id):
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.EXTRACTION_IN_PROGRESS,
            message=f"Text extraction is already running for document {document_id}.",
        )

    try:
        document = load_document(documents_dir, document_id)
        downstream_statuses = {
            DocumentStatus.EXTRACTED,
            DocumentStatus.INDEXING,
            DocumentStatus.INDEXED,
            DocumentStatus.INDEXING_FAILED,
        }
        if document.status in downstream_statuses:
            return document, load_extraction(documents_dir, document_id)

        processing = update_document_status(document, DocumentStatus.PROCESSING, documents_dir)
        remove_extraction(documents_dir, document_id)
        try:
            extraction = await run_in_threadpool(
                _extract_pdf,
                document_content_path(documents_dir, document_id),
                document_id,
                max_pages,
            )
            persist_extraction(documents_dir, extraction)
            extracted = update_document_status(
                processing,
                DocumentStatus.EXTRACTED,
                documents_dir,
            )
        except BaseException:
            remove_extraction(documents_dir, document_id)
            update_document_status(
                processing,
                DocumentStatus.EXTRACTION_FAILED,
                documents_dir,
            )
            raise

        return extracted, extraction
    finally:
        _release_extraction(document_id)


def _extract_pdf(content_path: Path, document_id: UUID, max_pages: int) -> DocumentExtraction:
    """Run the blocking parser with an explicit page bound and no OCR guesses."""
    if not content_path.is_file():
        raise ApiError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Stored PDF content for document {document_id} is missing.",
        )

    try:
        reader = PdfReader(content_path)
        if reader.is_encrypted:
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code=ErrorCode.ENCRYPTED_PDF,
                message="Encrypted PDFs cannot be extracted without a password.",
            )

        page_count = len(reader.pages)
        if page_count > max_pages:
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code=ErrorCode.PDF_PAGE_LIMIT_EXCEEDED,
                message=f"PDF has {page_count} pages; the configured limit is {max_pages}.",
            )

        pages = tuple(
            ExtractedPage(page_number=page_number, text=page.extract_text() or "")
            for page_number, page in enumerate(reader.pages, start=1)
        )
    except ApiError:
        raise
    except (PdfReadError, TypeError, ValueError) as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.PDF_EXTRACTION_FAILED,
            message="The PDF could not be parsed for text extraction.",
        ) from exc

    return DocumentExtraction(
        document_id=document_id,
        pages=pages,
        extracted_at=datetime.now(UTC),
    )


def _claim_extraction(document_id: UUID) -> bool:
    """Prevent duplicate work while allowing interrupted `processing` states to retry."""
    with _active_extractions_guard:
        if document_id in _active_extractions:
            return False
        _active_extractions.add(document_id)
        return True


def _release_extraction(document_id: UUID) -> None:
    with _active_extractions_guard:
        _active_extractions.discard(document_id)
