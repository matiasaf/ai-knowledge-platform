from uuid import UUID

import pytest

from ai_knowledge_platform.answers.domain import (
    AnswerOutcome,
    GeneratedClaim,
    GenerationResult,
    ground_generation,
    prepare_evidence,
)
from ai_knowledge_platform.retrieval.domain import RetrievalMatch

DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")


def _match(rank: int, *, page_number: int = 1) -> RetrievalMatch:
    text = f"Evidence text {rank}"
    return RetrievalMatch(
        rank=rank,
        document_id=DOCUMENT_ID,
        filename="runbook.pdf",
        page_number=page_number,
        chunk_index=rank - 1,
        text=text,
        start_offset=0,
        end_offset=len(text),
    )


def test_resolves_and_deduplicates_citations_from_trusted_matches() -> None:
    evidence = prepare_evidence((_match(1), _match(2, page_number=2)))
    generation = GenerationResult(
        outcome=AnswerOutcome.ANSWERED,
        claims=(
            GeneratedClaim(text="First claim.", evidence_ids=("E2", "E1", "E2")),
            GeneratedClaim(text="Second claim.", evidence_ids=("E1",)),
        ),
    )

    answer = ground_generation("Question?", generation, evidence)

    assert [citation.id for citation in answer.citations] == ["C1", "C2"]
    assert [citation.page_number for citation in answer.citations] == [2, 1]
    assert answer.claims[0].citation_ids == ("C1", "C2")
    assert answer.claims[1].citation_ids == ("C2",)
    assert answer.citations[0].source_path == f"/documents/{DOCUMENT_ID}/content"


@pytest.mark.parametrize(
    "generation",
    [
        GenerationResult(outcome=AnswerOutcome.ANSWERED),
        GenerationResult(
            outcome=AnswerOutcome.ANSWERED,
            claims=(GeneratedClaim(text="Unsupported.", evidence_ids=()),),
        ),
        GenerationResult(
            outcome=AnswerOutcome.ANSWERED,
            claims=(GeneratedClaim(text="Invented.", evidence_ids=("E9",)),),
        ),
        GenerationResult(
            outcome=AnswerOutcome.INSUFFICIENT_EVIDENCE,
            claims=(GeneratedClaim(text="Contradiction.", evidence_ids=("E1",)),),
        ),
    ],
)
def test_rejects_invalid_generation_invariants(generation: GenerationResult) -> None:
    with pytest.raises(ValueError):
        ground_generation("Question?", generation, prepare_evidence((_match(1),)))


def test_preserves_an_explicit_non_answer() -> None:
    answer = ground_generation(
        "Unknown?",
        GenerationResult(outcome=AnswerOutcome.INSUFFICIENT_EVIDENCE),
        prepare_evidence((_match(1),)),
    )

    assert answer.outcome is AnswerOutcome.INSUFFICIENT_EVIDENCE
    assert answer.claims == ()
    assert answer.citations == ()
