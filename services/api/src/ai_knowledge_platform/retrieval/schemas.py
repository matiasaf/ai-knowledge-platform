"""HTTP representations for document indexing and evidence retrieval."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from ai_knowledge_platform.documents.domain import Document
from ai_knowledge_platform.documents.schemas import DocumentResponse
from ai_knowledge_platform.retrieval.domain import DocumentIndex, RetrievalMatch


class DocumentIndexResponse(BaseModel):
    document: DocumentResponse
    chunk_count: int
    indexed_at: datetime

    @classmethod
    def from_domain(
        cls,
        document: Document,
        document_index: DocumentIndex,
    ) -> "DocumentIndexResponse":
        return cls(
            document=DocumentResponse.from_domain(document),
            chunk_count=document_index.chunk_count,
            indexed_at=document_index.indexed_at,
        )


class RetrievalSearchRequest(BaseModel):
    query: Annotated[str, Field(min_length=2, max_length=500)]
    limit: Annotated[int, Field(ge=1, le=20)] = 5
    document_id: UUID | None = None


class RetrievalMatchResponse(BaseModel):
    rank: int
    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int

    @classmethod
    def from_domain(cls, match: RetrievalMatch) -> "RetrievalMatchResponse":
        return cls(
            rank=match.rank,
            document_id=match.document_id,
            filename=match.filename,
            page_number=match.page_number,
            chunk_index=match.chunk_index,
            text=match.text,
            start_offset=match.start_offset,
            end_offset=match.end_offset,
        )


class RetrievalSearchResponse(BaseModel):
    query: str
    match_count: int
    matches: list[RetrievalMatchResponse]
