"""HTTP representations of documents, kept separate from the domain model.

The domain model may gain fields that are internal to ingestion (storage paths,
checksums, extraction attempts); the response schema is what clients depend on.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from ai_knowledge_platform.documents.domain import Document, DocumentStatus


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    byte_size: int
    content_type: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, document: Document) -> "DocumentResponse":
        return cls(
            id=document.id,
            filename=document.filename,
            byte_size=document.byte_size,
            content_type=document.content_type,
            status=document.status,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
