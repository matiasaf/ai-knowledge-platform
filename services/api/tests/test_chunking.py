from datetime import UTC, datetime
from itertools import pairwise
from uuid import uuid4

from ai_knowledge_platform.documents.domain import DocumentExtraction, ExtractedPage
from ai_knowledge_platform.retrieval.chunking import chunk_extraction


def test_chunks_stay_inside_pages_and_keep_exact_source_offsets() -> None:
    document_id = uuid4()
    first_page = (
        "Alpha policy explains the annual leave allowance. "
        "Employees request leave through the people portal. "
        "Managers review each request before the planned absence."
    )
    extraction = DocumentExtraction(
        document_id=document_id,
        pages=(
            ExtractedPage(page_number=1, text=first_page),
            ExtractedPage(page_number=2, text=""),
            ExtractedPage(page_number=3, text="A short final page."),
        ),
        extracted_at=datetime.now(UTC),
    )

    chunks = chunk_extraction(extraction, max_chars=70, overlap_chars=12)

    assert len(chunks) >= 3
    assert {chunk.page_number for chunk in chunks} == {1, 3}
    assert [chunk.chunk_index for chunk in chunks if chunk.page_number == 3] == [0]
    for chunk in chunks:
        source = first_page if chunk.page_number == 1 else "A short final page."
        assert chunk.text == source[chunk.start_offset : chunk.end_offset]
        assert 0 < len(chunk.text) <= 70

    first_page_chunks = [chunk for chunk in chunks if chunk.page_number == 1]
    assert all(
        following.start_offset < preceding.end_offset
        for preceding, following in pairwise(first_page_chunks)
    )


def test_chunking_is_deterministic() -> None:
    extraction = DocumentExtraction(
        document_id=uuid4(),
        pages=(ExtractedPage(page_number=1, text="one two three four five six seven"),),
        extracted_at=datetime.now(UTC),
    )

    first = chunk_extraction(extraction, max_chars=18, overlap_chars=4)
    second = chunk_extraction(extraction, max_chars=18, overlap_chars=4)

    assert first == second
