"""Application factory and ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_knowledge_platform import __version__, health
from ai_knowledge_platform.answers import router as answers
from ai_knowledge_platform.answers.openai_generator import OpenAIAnswerGenerator
from ai_knowledge_platform.config import Settings, get_settings
from ai_knowledge_platform.documents import router as documents
from ai_knowledge_platform.errors import register_error_handlers
from ai_knowledge_platform.retrieval import router as retrieval


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API. Tests use this to run against a throwaway data directory."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        generator: OpenAIAnswerGenerator | None = None
        if settings.generation_configured:
            api_key = settings.openai_api_key
            model = settings.openai_model
            assert api_key is not None and model is not None
            generator = OpenAIAnswerGenerator(
                api_key=api_key.get_secret_value(),
                model=model,
                timeout_seconds=settings.answer_timeout_seconds,
                max_output_tokens=settings.answer_max_output_tokens,
            )
        app.state.answer_generator = generator
        try:
            yield
        finally:
            if generator is not None:
                await generator.close()

    app = FastAPI(
        title="AI Knowledge Platform API",
        version=__version__,
        summary="Ingest trusted documents and answer questions grounded in them.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(retrieval.router)
    app.include_router(answers.router)
    return app


app = create_app()
