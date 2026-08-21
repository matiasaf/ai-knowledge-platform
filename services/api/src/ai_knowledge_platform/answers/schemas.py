"""HTTP schemas for grounded answer generation."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ai_knowledge_platform.answers.domain import (
    AnswerOutcome,
    Citation,
    GroundedAnswer,
    GroundedClaim,
)


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, Field(min_length=2, max_length=500)]
    document_id: UUID | None = None


class GroundedClaimResponse(BaseModel):
    text: str
    citation_ids: list[str]

    @classmethod
    def from_domain(cls, claim: GroundedClaim) -> "GroundedClaimResponse":
        return cls(text=claim.text, citation_ids=list(claim.citation_ids))


class CitationResponse(BaseModel):
    id: str
    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    start_offset: int
    end_offset: int
    excerpt: str
    source_path: str

    @classmethod
    def from_domain(cls, citation: Citation) -> "CitationResponse":
        return cls(
            id=citation.id,
            document_id=citation.document_id,
            filename=citation.filename,
            page_number=citation.page_number,
            chunk_index=citation.chunk_index,
            start_offset=citation.start_offset,
            end_offset=citation.end_offset,
            excerpt=citation.text,
            source_path=citation.source_path,
        )


class AnswerResponse(BaseModel):
    question: str
    outcome: AnswerOutcome
    claims: list[GroundedClaimResponse]
    citations: list[CitationResponse]

    @classmethod
    def from_domain(cls, answer: GroundedAnswer) -> "AnswerResponse":
        return cls(
            question=answer.question,
            outcome=answer.outcome,
            claims=[GroundedClaimResponse.from_domain(claim) for claim in answer.claims],
            citations=[CitationResponse.from_domain(citation) for citation in answer.citations],
        )
