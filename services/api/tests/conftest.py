"""Shared fixtures. Every test runs against a throwaway data directory."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_knowledge_platform.config import Settings, get_settings
from ai_knowledge_platform.main import create_app

# Small enough to write in a test, large enough that the size limit is not the
# constraint under test.
MAX_UPLOAD_BYTES = 4096

MINIMAL_PDF = (
    b"%PDF-1.7\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n"
    b"%%EOF\n"
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", max_upload_bytes=MAX_UPLOAD_BYTES)


@pytest.fixture
def documents_dir(settings: Settings) -> Path:
    return settings.documents_dir


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
