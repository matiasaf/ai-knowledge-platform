"""Domain types for page-bounded chunks and evidence retrieval."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RetrievalChunk:
    document_id: UUID
    page_number: int
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class DocumentIndex:
    document_id: UUID
    filename: str
    chunk_count: int
    indexed_at: datetime


@dataclass(frozen=True, slots=True)
class RetrievalMatch:
    rank: int
    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
