"""Typed application settings loaded from the environment."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchoring relative paths to the service root keeps `uv run` behaviour identical
# whether it is invoked from the repository root or from services/api.
SERVICE_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_PDF_PAGES = 250
DEFAULT_CHUNK_SIZE_CHARS = 1000
DEFAULT_CHUNK_OVERLAP_CHARS = 150
DEFAULT_ANSWER_EVIDENCE_LIMIT = 5
DEFAULT_ANSWER_MAX_OUTPUT_TOKENS = 800
DEFAULT_ANSWER_TIMEOUT_SECONDS = 30.0


class Settings(BaseSettings):
    """Runtime configuration. Every value is overridable through `AKP_*` variables."""

    model_config = SettingsConfigDict(
        env_prefix="AKP_",
        env_file=SERVICE_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    max_upload_bytes: Annotated[int, Field(gt=0)] = DEFAULT_MAX_UPLOAD_BYTES
    max_pdf_pages: Annotated[int, Field(gt=0)] = DEFAULT_MAX_PDF_PAGES
    chunk_size_chars: Annotated[int, Field(gt=0)] = DEFAULT_CHUNK_SIZE_CHARS
    chunk_overlap_chars: Annotated[int, Field(ge=0)] = DEFAULT_CHUNK_OVERLAP_CHARS
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    answer_evidence_limit: Annotated[int, Field(ge=1, le=10)] = DEFAULT_ANSWER_EVIDENCE_LIMIT
    answer_max_output_tokens: Annotated[int, Field(gt=0, le=4000)] = (
        DEFAULT_ANSWER_MAX_OUTPUT_TOKENS
    )
    answer_timeout_seconds: Annotated[float, Field(gt=0, le=120)] = DEFAULT_ANSWER_TIMEOUT_SECONDS
    cors_allow_origins: list[str] = ["http://localhost:3000"]

    @field_validator("data_dir")
    @classmethod
    def _anchor_to_service_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else (SERVICE_ROOT / value).resolve()

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        # Environment variables carry a comma-separated list so that .env files stay
        # readable; JSON would be the only alternative pydantic-settings accepts.
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _validate_chunk_window(self) -> "Settings":
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("chunk_overlap_chars must be smaller than chunk_size_chars")
        return self

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def knowledge_db_path(self) -> Path:
        return self.data_dir / "knowledge.db"

    @property
    def generation_configured(self) -> bool:
        return bool(
            self.openai_api_key
            and self.openai_api_key.get_secret_value().strip()
            and self.openai_model
            and self.openai_model.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
