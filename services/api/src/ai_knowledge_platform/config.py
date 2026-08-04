"""Typed application settings loaded from the environment."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchoring relative paths to the service root keeps `uv run` behaviour identical
# whether it is invoked from the repository root or from services/api.
SERVICE_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


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

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
