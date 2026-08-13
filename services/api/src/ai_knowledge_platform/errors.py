"""Structured API errors with stable, machine-readable codes."""

from enum import StrEnum

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(StrEnum):
    """Codes clients may branch on. Treat every member as part of the public contract."""

    FILE_TOO_LARGE = "file_too_large"
    DOCUMENT_NOT_FOUND = "document_not_found"
    ENCRYPTED_PDF = "encrypted_pdf"
    EXTRACTION_IN_PROGRESS = "extraction_in_progress"
    PDF_EXTRACTION_FAILED = "pdf_extraction_failed"
    PDF_PAGE_LIMIT_EXCEEDED = "pdf_page_limit_exceeded"
    INVALID_PDF = "invalid_pdf"
    MISSING_FILENAME = "missing_filename"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    VALIDATION_ERROR = "validation_error"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    NOT_FOUND = "not_found"
    CLIENT_ERROR = "client_error"
    INTERNAL_ERROR = "internal_error"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    """Envelope returned by every failing endpoint."""

    error: ErrorDetail


class ApiError(Exception):
    """Raised by application code to produce an `ErrorResponse` with a known code."""

    def __init__(self, *, status_code: int, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _error_response(status_code: int, code: ErrorCode, message: str) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def register_error_handlers(app: FastAPI) -> None:
    """Make every error path share one response shape, including framework failures."""

    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else None
        field = ".".join(str(part) for part in first["loc"][1:]) if first else ""
        message = f"Invalid request: {field or 'request body'} is missing or malformed."
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.VALIDATION_ERROR, message
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(exc.status_code, _code_for_status(exc.status_code), str(exc.detail))


def _code_for_status(status_code: int) -> ErrorCode:
    """Map framework-raised statuses onto codes that describe what actually happened."""
    if status_code == status.HTTP_404_NOT_FOUND:
        return ErrorCode.NOT_FOUND
    if status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        return ErrorCode.METHOD_NOT_ALLOWED
    return ErrorCode.CLIENT_ERROR if status_code < 500 else ErrorCode.INTERNAL_ERROR
