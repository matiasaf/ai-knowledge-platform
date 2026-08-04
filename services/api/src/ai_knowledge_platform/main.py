"""Application factory and ASGI entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_knowledge_platform import __version__, health
from ai_knowledge_platform.config import Settings, get_settings
from ai_knowledge_platform.documents import router as documents
from ai_knowledge_platform.errors import register_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API. Tests use this to run against a throwaway data directory."""
    settings = settings or get_settings()

    app = FastAPI(
        title="AI Knowledge Platform API",
        version=__version__,
        summary="Ingest trusted documents and, later, answer questions grounded in them.",
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
    return app


app = create_app()
