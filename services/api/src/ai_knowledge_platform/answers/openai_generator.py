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
    TokenUsage,
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

        # Read defensively: tracing metadata must never turn a valid answer into a failure.
        model = getattr(response, "model", None)
        model = model if isinstance(model, str) else None
        usage = _token_usage(getattr(response, "usage", None))
        if _contains_refusal(response.output):
            return GenerationResult(outcome=AnswerOutcome.SAFETY_REFUSED, model=model, usage=usage)

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
            model=model,
            usage=usage,
        )

    async def close(self) -> None:
        await self._client.close()


def _token_usage(usage: object) -> TokenUsage | None:
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
    return None


def _contains_refusal(output_items: object) -> bool:
    """Inspect SDK output defensively; refusals intentionally do not match the schema."""
    if not isinstance(output_items, list):
        return False
    for output in output_items:
        content = getattr(output, "content", ())
        if any(getattr(item, "type", None) == "refusal" for item in content):
            return True
    return False
