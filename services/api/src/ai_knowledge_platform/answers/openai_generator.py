"""OpenAI Responses API adapter for structured grounded answers."""

from typing import Annotated, Literal

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_knowledge_platform.answers.domain import (
    MAX_CLAIM_CHARS,
    MAX_CLAIMS,
    MAX_EVIDENCE_PER_CLAIM,
    AnswerOutcome,
    Evidence,
    GeneratedClaim,
    GenerationResult,
)
from ai_knowledge_platform.answers.ports import (
    GenerationInvalidResponseError,
    GenerationProviderError,
    GenerationTimeoutError,
)
from ai_knowledge_platform.answers.prompt import (
    GROUNDING_INSTRUCTIONS,
    build_generation_input,
)


class ProviderClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=MAX_CLAIM_CHARS)]
    evidence_ids: Annotated[
        list[str],
        Field(min_length=1, max_length=MAX_EVIDENCE_PER_CLAIM),
    ]


class ProviderAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["answered", "insufficient_evidence"]
    claims: Annotated[list[ProviderClaim], Field(max_length=MAX_CLAIMS)]

    @model_validator(mode="after")
    def _validate_outcome(self) -> "ProviderAnswer":
        if self.outcome == "answered" and not self.claims:
            raise ValueError("answered output requires at least one claim")
        if self.outcome == "insufficient_evidence" and self.claims:
            raise ValueError("insufficient evidence output cannot contain claims")
        return self


class OpenAIAnswerGenerator:
    """Generate typed claims without exposing provider types to the application."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=1,
        )

    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> GenerationResult:
        try:
            response = await self._client.responses.parse(
                model=self._model,
                instructions=GROUNDING_INSTRUCTIONS,
                input=build_generation_input(question, evidence),
                text_format=ProviderAnswer,
                max_output_tokens=self._max_output_tokens,
                store=False,
            )
        except APITimeoutError as exc:
            raise GenerationTimeoutError from exc
        except (APIConnectionError, APIStatusError) as exc:
            raise GenerationProviderError from exc

        if _contains_refusal(response.output):
            return GenerationResult(outcome=AnswerOutcome.SAFETY_REFUSED)

        if response.status != "completed":
            raise GenerationInvalidResponseError

        parsed = response.output_parsed
        if parsed is None:
            raise GenerationInvalidResponseError

        return GenerationResult(
            outcome=AnswerOutcome(parsed.outcome),
            claims=tuple(
                GeneratedClaim(
                    text=claim.text,
                    evidence_ids=tuple(claim.evidence_ids),
                )
                for claim in parsed.claims
            ),
        )

    async def close(self) -> None:
        await self._client.close()


def _contains_refusal(output_items: object) -> bool:
    """Inspect SDK output defensively; refusals intentionally do not match the schema."""
    if not isinstance(output_items, list):
        return False
    for output in output_items:
        content = getattr(output, "content", ())
        if any(getattr(item, "type", None) == "refusal" for item in content):
            return True
    return False
