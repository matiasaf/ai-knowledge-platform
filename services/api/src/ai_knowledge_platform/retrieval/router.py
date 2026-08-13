"""HTTP surface for indexing and evidence retrieval."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from ai_knowledge_platform.config import Settings, get_settings
from ai_knowledge_platform.errors import ErrorResponse
from ai_knowledge_platform.retrieval.schemas import (
    DocumentIndexResponse,
    RetrievalMatchResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from ai_knowledge_platform.retrieval.service import (
    index_extracted_document,
    retrieve_evidence,
)

router = APIRouter(tags=["retrieval"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/documents/{document_id}/index",
    summary="Chunk and index an extracted document",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def index_document(document_id: UUID, settings: SettingsDep) -> DocumentIndexResponse:
    document, document_index = await index_extracted_document(
        document_id,
        documents_dir=settings.documents_dir,
        database_path=settings.knowledge_db_path,
        max_chunk_chars=settings.chunk_size_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )
    return DocumentIndexResponse.from_domain(document, document_index)


@router.post(
    "/retrieval/search",
    summary="Find page-level evidence in indexed documents",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def search_evidence(
    request: RetrievalSearchRequest,
    settings: SettingsDep,
) -> RetrievalSearchResponse:
    matches = await retrieve_evidence(
        request.query,
        database_path=settings.knowledge_db_path,
        limit=request.limit,
        document_id=request.document_id,
    )
    return RetrievalSearchResponse(
        query=request.query,
        match_count=len(matches),
        matches=[RetrievalMatchResponse.from_domain(match) for match in matches],
    )
