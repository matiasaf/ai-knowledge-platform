"""Application service for retrieve, generate and resolve."""

from pathlib import Path
from uuid import UUID

from fastapi import status

from ai_knowledge_platform.answers.domain import (
    AnswerOutcome,
    GroundedAnswer,
    ground_generation,
    prepare_evidence,
)
from ai_knowledge_platform.answers.ports import (
    AnswerGenerator,
    GenerationInvalidResponseError,
    GenerationProviderError,
    GenerationTimeoutError,
)
from ai_knowledge_platform.answers.prompt import PROMPT_VERSION
from ai_knowledge_platform.documents.domain import DocumentStatus
from ai_knowledge_platform.documents.storage import load_document
from ai_knowledge_platform.errors import ApiError, ErrorCode
from ai_knowledge_platform.observability.tracing import set_trace_attribute, span
from ai_knowledge_platform.retrieval.service import retrieve_evidence


async def answer_question(
    question: str,
    *,
    generator: AnswerGenerator | None,
    documents_dir: Path,
    database_path: Path,
    evidence_limit: int,
    document_id: UUID | None,
) -> GroundedAnswer:
    """Answer from retrieved chunks or return an explicit non-answer outcome."""
    normalized_question = question.strip()
    if generator is None:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.GENERATION_NOT_CONFIGURED,
            message="Answer generation is not configured for this API.",
        )

    if document_id is not None:
        document = load_document(documents_dir, document_id)
        if document.status is not DocumentStatus.INDEXED:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code=ErrorCode.DOCUMENT_NOT_INDEXED,
                message="The selected document must be indexed before it can answer questions.",
            )

    matches = await retrieve_evidence(
        normalized_question,
        database_path=database_path,
        limit=evidence_limit,
        document_id=document_id,
    )
    if not matches:
        set_trace_attribute("answer_outcome", AnswerOutcome.INSUFFICIENT_EVIDENCE.value)
        return GroundedAnswer(
            question=normalized_question,
            outcome=AnswerOutcome.INSUFFICIENT_EVIDENCE,
        )

    evidence = prepare_evidence(matches)
    try:
        with span("generation", prompt_version=PROMPT_VERSION, evidence=len(evidence)) as stage:
            generation = await generator.generate(
                question=normalized_question,
                evidence=evidence,
            )
            stage.set("model", generation.model)
            stage.set("provider_outcome", generation.outcome.value)
            if generation.usage is not None:
                stage.set("input_tokens", generation.usage.input_tokens)
                stage.set("output_tokens", generation.usage.output_tokens)
        answer = ground_generation(normalized_question, generation, evidence)
        set_trace_attribute("answer_outcome", answer.outcome.value)
        return answer
    except GenerationTimeoutError as exc:
        raise ApiError(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            code=ErrorCode.GENERATION_TIMEOUT,
            message="Answer generation timed out. Please try again.",
        ) from exc
    except GenerationProviderError as exc:
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code=ErrorCode.GENERATION_PROVIDER_ERROR,
            message="The answer provider could not complete the request.",
        ) from exc
    except (GenerationInvalidResponseError, ValueError) as exc:
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code=ErrorCode.GENERATION_INVALID_RESPONSE,
            message="The answer provider returned an invalid grounded response.",
        ) from exc
