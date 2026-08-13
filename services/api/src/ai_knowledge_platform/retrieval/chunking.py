"""Deterministic character-window chunking that never crosses a PDF page."""

from uuid import UUID

from ai_knowledge_platform.documents.domain import DocumentExtraction
from ai_knowledge_platform.retrieval.domain import RetrievalChunk


def chunk_extraction(
    extraction: DocumentExtraction,
    *,
    max_chars: int,
    overlap_chars: int,
) -> tuple[RetrievalChunk, ...]:
    """Split page text into bounded, overlapping spans with source offsets."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")

    chunks: list[RetrievalChunk] = []
    for page in extraction.pages:
        chunks.extend(
            _chunk_page(
                document_id=extraction.document_id,
                page_number=page.page_number,
                text=page.text,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )
        )
    return tuple(chunks)


def _chunk_page(
    *,
    document_id: UUID,
    page_number: int,
    text: str,
    max_chars: int,
    overlap_chars: int,
) -> list[RetrievalChunk]:
    chunks: list[RetrievalChunk] = []
    cursor = 0
    chunk_index = 0
    while cursor < len(text):
        start = _skip_whitespace(text, cursor)
        if start >= len(text):
            break

        hard_end = min(start + max_chars, len(text))
        end = _preferred_end(text, start=start, hard_end=hard_end, max_chars=max_chars)
        while end > start and text[end - 1].isspace():
            end -= 1
        if end <= start:
            end = hard_end

        chunks.append(
            RetrievalChunk(
                document_id=document_id,
                page_number=page_number,
                chunk_index=chunk_index,
                text=text[start:end],
                start_offset=start,
                end_offset=end,
            )
        )
        chunk_index += 1
        if hard_end == len(text):
            break

        cursor = max(start + 1, end - overlap_chars)
        # Start the overlap at a word boundary. Advancing is safer than moving back to
        # `start`, which could prevent progress after a short paragraph boundary.
        while cursor < end and cursor > 0 and not text[cursor - 1].isspace():
            cursor += 1

    return chunks


def _skip_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _preferred_end(text: str, *, start: int, hard_end: int, max_chars: int) -> int:
    if hard_end == len(text):
        return hard_end

    lower_bound = start + max(1, max_chars // 2)
    for marker in ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "):
        boundary = text.rfind(marker, lower_bound, hard_end)
        if boundary >= 0:
            return boundary + (1 if marker[0] in ".?!;," else 0)
    return hard_end
