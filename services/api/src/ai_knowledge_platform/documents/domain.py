"""Domain model for an ingested document, independent of transport concerns."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

PDF_CONTENT_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"


class DocumentStatus(StrEnum):
    """Only states the platform can actually reach are modelled.

    `processing` and `ready` are deliberately absent: advertising them before text
    extraction and indexing exist would make the API promise capabilities it lacks.
    """

    STORED = "stored"


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
