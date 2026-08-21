"""Domain types and invariants for evidence-grounded answers."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from ai_knowledge_platform.retrieval.domain import RetrievalMatch

MAX_CLAIMS = 5
MAX_CLAIM_CHARS = 1000
MAX_EVIDENCE_PER_CLAIM = 3


class AnswerOutcome(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SAFETY_REFUSED = "safety_refused"


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    match: RetrievalMatch


@dataclass(frozen=True, slots=True)
class GeneratedClaim:
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GenerationResult:
    outcome: AnswerOutcome
    claims: tuple[GeneratedClaim, ...] = ()


@dataclass(frozen=True, slots=True)
class Citation:
    id: str
    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int

    @property
    def source_path(self) -> str:
        return f"/documents/{self.document_id}/content"


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    text: str
    citation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    question: str
    outcome: AnswerOutcome
    claims: tuple[GroundedClaim, ...] = ()
    citations: tuple[Citation, ...] = ()


def prepare_evidence(matches: tuple[RetrievalMatch, ...]) -> tuple[Evidence, ...]:
    """Assign request-local, deterministic IDs to ranked retrieval matches."""
    return tuple(Evidence(id=f"E{index}", match=match) for index, match in enumerate(matches, 1))


def ground_generation(
    question: str,
    generation: GenerationResult,
    evidence: tuple[Evidence, ...],
) -> GroundedAnswer:
    """Resolve provider references against trusted retrieval metadata."""
    if generation.outcome is not AnswerOutcome.ANSWERED:
        if generation.claims:
            raise ValueError("a non-answer outcome cannot contain claims")
        return GroundedAnswer(question=question, outcome=generation.outcome)

    if not generation.claims or len(generation.claims) > MAX_CLAIMS:
        raise ValueError("an answered result must contain between one and five claims")

    evidence_by_id = {item.id: item for item in evidence}
    citation_id_by_evidence: dict[str, str] = {}
    citations: list[Citation] = []
    grounded_claims: list[GroundedClaim] = []
    seen_claims: set[str] = set()

    for claim in generation.claims:
        text = claim.text.strip()
        if not text or len(text) > MAX_CLAIM_CHARS:
            raise ValueError("claim text is empty or too long")
        if text in seen_claims:
            raise ValueError("answered results cannot contain duplicate claims")
        seen_claims.add(text)

        unique_evidence_ids = tuple(dict.fromkeys(claim.evidence_ids))
        if not unique_evidence_ids or len(unique_evidence_ids) > MAX_EVIDENCE_PER_CLAIM:
            raise ValueError("each claim must cite between one and three evidence items")

        claim_citation_ids: list[str] = []
        for evidence_id in unique_evidence_ids:
            source = evidence_by_id.get(evidence_id)
            if source is None:
                raise ValueError(f"unknown evidence ID: {evidence_id}")

            citation_id = citation_id_by_evidence.get(evidence_id)
            if citation_id is None:
                citation_id = f"C{len(citations) + 1}"
                citation_id_by_evidence[evidence_id] = citation_id
                match = source.match
                citations.append(
                    Citation(
                        id=citation_id,
                        document_id=match.document_id,
                        filename=match.filename,
                        page_number=match.page_number,
                        chunk_index=match.chunk_index,
                        text=match.text,
                        start_offset=match.start_offset,
                        end_offset=match.end_offset,
                    )
                )
            claim_citation_ids.append(citation_id)

        grounded_claims.append(GroundedClaim(text=text, citation_ids=tuple(claim_citation_ids)))

    return GroundedAnswer(
        question=question,
        outcome=AnswerOutcome.ANSWERED,
        claims=tuple(grounded_claims),
        citations=tuple(citations),
    )
