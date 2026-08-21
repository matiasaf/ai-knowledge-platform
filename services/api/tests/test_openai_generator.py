import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from ai_knowledge_platform.answers.domain import AnswerOutcome, Evidence
from ai_knowledge_platform.answers.openai_generator import (
    OpenAIAnswerGenerator,
    ProviderAnswer,
    ProviderClaim,
)
from ai_knowledge_platform.answers.ports import GenerationInvalidResponseError
from ai_knowledge_platform.retrieval.domain import RetrievalMatch


def _evidence() -> tuple[Evidence, ...]:
    text = "Requests are submitted in the people portal."
    return (
        Evidence(
            id="E1",
            match=RetrievalMatch(
                rank=1,
                document_id=UUID("11111111-1111-4111-8111-111111111111"),
                filename="handbook.pdf",
                page_number=2,
                chunk_index=0,
                text=text,
                start_offset=0,
                end_offset=len(text),
            ),
        ),
    )


def test_calls_responses_parse_with_private_stateless_context() -> None:
    asyncio.run(_assert_responses_parse_call())


async def _assert_responses_parse_call() -> None:
    generator = OpenAIAnswerGenerator(
        api_key="test-key",
        model="test-model",
        timeout_seconds=10,
        max_output_tokens=400,
    )
    parse = AsyncMock(
        return_value=SimpleNamespace(
            output=[],
            status="completed",
            output_parsed=ProviderAnswer(
                outcome="answered",
                claims=[ProviderClaim(text="Use the people portal.", evidence_ids=["E1"])],
            ),
        )
    )
    generator._client.responses.parse = parse  # type: ignore[method-assign]

    try:
        result = await generator.generate(question="Where?", evidence=_evidence())
    finally:
        await generator.close()

    assert result.outcome is AnswerOutcome.ANSWERED
    assert result.claims[0].evidence_ids == ("E1",)
    assert parse.await_args is not None
    kwargs = parse.await_args.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["store"] is False
    assert "tools" not in kwargs
    assert kwargs["max_output_tokens"] == 400
    assert '"id": "E1"' in kwargs["input"]
    assert "people portal" in kwargs["input"]


def test_maps_provider_refusal_to_safety_outcome() -> None:
    asyncio.run(_assert_provider_refusal())


async def _assert_provider_refusal() -> None:
    generator = OpenAIAnswerGenerator(
        api_key="test-key",
        model="test-model",
        timeout_seconds=10,
        max_output_tokens=400,
    )
    generator._client.responses.parse = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
            status="completed",
            output_parsed=None,
        )
    )

    try:
        result = await generator.generate(question="Question?", evidence=_evidence())
    finally:
        await generator.close()

    assert result.outcome is AnswerOutcome.SAFETY_REFUSED
    assert result.claims == ()


def test_rejects_an_absent_structured_output() -> None:
    asyncio.run(_assert_absent_structured_output())


async def _assert_absent_structured_output() -> None:
    generator = OpenAIAnswerGenerator(
        api_key="test-key",
        model="test-model",
        timeout_seconds=10,
        max_output_tokens=400,
    )
    generator._client.responses.parse = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(output=[], status="completed", output_parsed=None)
    )

    try:
        with pytest.raises(GenerationInvalidResponseError):
            await generator.generate(question="Question?", evidence=_evidence())
    finally:
        await generator.close()


def test_rejects_an_incomplete_response_even_if_it_contains_parsed_data() -> None:
    asyncio.run(_assert_incomplete_response())


async def _assert_incomplete_response() -> None:
    generator = OpenAIAnswerGenerator(
        api_key="test-key",
        model="test-model",
        timeout_seconds=10,
        max_output_tokens=400,
    )
    generator._client.responses.parse = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            output=[],
            status="incomplete",
            output_parsed=ProviderAnswer(
                outcome="answered",
                claims=[ProviderClaim(text="Partial claim.", evidence_ids=["E1"])],
            ),
        )
    )

    try:
        with pytest.raises(GenerationInvalidResponseError):
            await generator.generate(question="Question?", evidence=_evidence())
    finally:
        await generator.close()
