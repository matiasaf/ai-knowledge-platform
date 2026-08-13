"""Domain model for an ingested document, independent of transport concerns."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

PDF_CONTENT_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"


class DocumentStatus(StrEnum):
    """States backed by concrete storage or extraction work."""

    STORED = "stored"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    EXTRACTION_FAILED = "extraction_failed"


@dataclass(frozen=True, slots=True)
class Document:
    id: UUID
    filename: str
    byte_size: int
    content_type: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def stored(cls, *, document_id: UUID, filename: str, byte_size: int) -> "Document":
        now = datetime.now(UTC)
        return cls(
            id=document_id,
            filename=filename,
            byte_size=byte_size,
            content_type=PDF_CONTENT_TYPE,
            status=DocumentStatus.STORED,
            created_at=now,
            updated_at=now,
        )

    def with_status(self, status: DocumentStatus) -> "Document":
        """Return a new snapshot after a real ingestion state transition."""
        return Document(
            id=self.id,
            filename=self.filename,
            byte_size=self.byte_size,
            content_type=self.content_type,
            status=status,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """Text span whose one-based page number is its source provenance."""

    page_number: int
    text: str

    @property
    def character_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True, slots=True)
class DocumentExtraction:
    document_id: UUID
    pages: tuple[ExtractedPage, ...]
    extracted_at: datetime

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def empty_page_count(self) -> int:
        return sum(not page.text.strip() for page in self.pages)
