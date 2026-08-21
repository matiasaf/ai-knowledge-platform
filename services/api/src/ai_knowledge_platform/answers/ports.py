"""Ports and stable failures for external answer generation."""

from typing import Protocol

from ai_knowledge_platform.answers.domain import Evidence, GenerationResult


class GenerationTimeoutError(Exception):
    """The provider did not finish within the configured timeout."""


class GenerationProviderError(Exception):
    """The provider could not complete a request."""


class GenerationInvalidResponseError(Exception):
    """The provider returned no complete, usable structured result."""


class AnswerGenerator(Protocol):
    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> GenerationResult: ...
