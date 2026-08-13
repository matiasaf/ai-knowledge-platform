"""Application services for indexing extracted pages and retrieving evidence."""

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import UUID

from fastapi import status
from starlette.concurrency import run_in_threadpool

from ai_knowledge_platform.documents.domain import Document, DocumentExtraction, DocumentStatus
from ai_knowledge_platform.documents.storage import (
    load_document,
    load_extraction,
    update_document_status,
)
from ai_knowledge_platform.errors import ApiError, ErrorCode
from ai_knowledge_platform.retrieval.chunking import chunk_extraction
from ai_knowledge_platform.retrieval.domain import DocumentIndex, RetrievalMatch
from ai_knowledge_platform.retrieval.repository import (
    load_document_index,
    replace_document_index,
    search_chunks,
)

_active_indexes: set[UUID] = set()
_active_indexes_guard = Lock()


async def index_extracted_document(
    document_id: UUID,
    *,
    documents_dir: Path,
    database_path: Path,
    max_chunk_chars: int,
    overlap_chars: int,
) -> tuple[Document, DocumentIndex]:
    """Create an idempotent page-bounded index for one extracted document."""
    if not _claim_index(document_id):
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.INDEXING_IN_PROGRESS,
            message=f"Indexing is already running for document {document_id}.",
        )

    try:
        document = load_document(documents_dir, document_id)
        if document.status is DocumentStatus.INDEXED:
            existing = load_document_index(database_path, document_id)
            if existing is None:
                raise ApiError(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Retrieval index for document {document_id} is missing.",
                )
            return document, existing

        allowed_statuses = {
            DocumentStatus.EXTRACTED,
            DocumentStatus.INDEXING,
            DocumentStatus.INDEXING_FAILED,
        }
        if document.status not in allowed_statuses:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code=ErrorCode.DOCUMENT_NOT_EXTRACTED,
                message="Document text must be extracted before it can be indexed.",
            )

        indexing = update_document_status(document, DocumentStatus.INDEXING, documents_dir)
        try:
            extraction = load_extraction(documents_dir, document_id)
            document_index = await run_in_threadpool(
                _build_and_store_index,
                indexing,
                extraction,
                database_path,
                max_chunk_chars,
                overlap_chars,
            )
            indexed = update_document_status(indexing, DocumentStatus.INDEXED, documents_dir)
        except BaseException:
            update_document_status(indexing, DocumentStatus.INDEXING_FAILED, documents_dir)
            raise

        return indexed, document_index
    finally:
        _release_index(document_id)


async def retrieve_evidence(
    query: str,
    *,
    database_path: Path,
    limit: int,
    document_id: UUID | None,
) -> tuple[RetrievalMatch, ...]:
    return await run_in_threadpool(
        search_chunks,
        database_path,
        query,
        limit=limit,
        document_id=document_id,
    )


def _build_and_store_index(
    document: Document,
    extraction: DocumentExtraction,
    database_path: Path,
    max_chunk_chars: int,
    overlap_chars: int,
) -> DocumentIndex:
    chunks = chunk_extraction(
        extraction,
        max_chars=max_chunk_chars,
        overlap_chars=overlap_chars,
    )
    document_index = DocumentIndex(
        document_id=document.id,
        filename=document.filename,
        chunk_count=len(chunks),
        indexed_at=datetime.now(UTC),
    )
    replace_document_index(database_path, document_index, chunks)
    return document_index


def _claim_index(document_id: UUID) -> bool:
    with _active_indexes_guard:
        if document_id in _active_indexes:
            return False
        _active_indexes.add(document_id)
        return True


def _release_index(document_id: UUID) -> None:
    with _active_indexes_guard:
        _active_indexes.discard(document_id)
