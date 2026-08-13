"""HTTP surface for document ingestion."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from ai_knowledge_platform.config import Settings, get_settings
from ai_knowledge_platform.documents.domain import PDF_CONTENT_TYPE
from ai_knowledge_platform.documents.extraction import extract_stored_document
from ai_knowledge_platform.documents.schemas import DocumentExtractionResponse, DocumentResponse
from ai_knowledge_platform.documents.storage import store_document
from ai_knowledge_platform.errors import ApiError, ErrorCode, ErrorResponse

router = APIRouter(tags=["documents"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF document",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def upload_document(
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="A PDF file of at most the configured size")],
) -> DocumentResponse:
    """Accept a PDF, store it and return its metadata.

    The response status is `stored`: the file is persisted and nothing has parsed it yet.
    """
    if not file.filename:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.MISSING_FILENAME,
            message="The uploaded part must include a filename.",
        )

    if _base_media_type(file.content_type) != PDF_CONTENT_TYPE:
        raise ApiError(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            message=f"Only {PDF_CONTENT_TYPE} uploads are accepted.",
        )

    document = await store_document(
        file,
        documents_dir=settings.documents_dir,
        max_bytes=settings.max_upload_bytes,
    )
    return DocumentResponse.from_domain(document)


@router.post(
    "/documents/{document_id}/extraction",
    summary="Extract text from a stored PDF",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def extract_document_text(
    document_id: UUID,
    settings: SettingsDep,
) -> DocumentExtractionResponse:
    """Extract every page, preserving empty pages and one-based page provenance."""
    document, extraction = await extract_stored_document(
        document_id,
        documents_dir=settings.documents_dir,
        max_pages=settings.max_pdf_pages,
    )
    return DocumentExtractionResponse.from_domain(document, extraction)


def _base_media_type(content_type: str | None) -> str:
    """Strip parameters such as `; charset=` before comparing media types."""
    return (content_type or "").split(";")[0].strip().lower()
