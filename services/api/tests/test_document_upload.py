import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from tests.conftest import MAX_UPLOAD_BYTES, MINIMAL_PDF


def test_accepts_pdf_and_returns_stored_metadata(client: TestClient) -> None:
    response = client.post(
        "/documents",
        files={"file": ("quarterly-report.pdf", MINIMAL_PDF, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"])
    assert body["filename"] == "quarterly-report.pdf"
    assert body["byte_size"] == len(MINIMAL_PDF)
    assert body["content_type"] == "application/pdf"
    assert body["status"] == "stored"
    assert body["created_at"] == body["updated_at"]


def test_stored_file_and_sidecar_match_the_response(
    client: TestClient, documents_dir: Path
) -> None:
    response = client.post(
        "/documents",
        files={"file": ("handbook.pdf", MINIMAL_PDF, "application/pdf")},
    )
    body = response.json()

    stored_pdf = documents_dir / f"{body['id']}.pdf"
    sidecar = documents_dir / f"{body['id']}.json"
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))

    assert stored_pdf.read_bytes() == MINIMAL_PDF
    assert metadata["byte_size"] == stored_pdf.stat().st_size
    for field in ("id", "filename", "byte_size", "content_type", "status"):
        assert metadata[field] == body[field]
    # Both sides are ISO-8601 UTC but spell the offset differently ("+00:00" vs "Z"),
    # so the instants are compared rather than the strings.
    for field in ("created_at", "updated_at"):
        assert datetime.fromisoformat(metadata[field]) == datetime.fromisoformat(body[field])


def test_rejects_declared_non_pdf_content_type(client: TestClient, documents_dir: Path) -> None:
    response = client.post(
        "/documents",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"
    assert not documents_dir.exists()


def test_rejects_content_that_only_claims_to_be_a_pdf(client: TestClient) -> None:
    response = client.post(
        "/documents",
        files={"file": ("spoofed.pdf", b"GIF89a not a pdf at all", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_pdf"


def test_rejects_file_above_the_size_limit(client: TestClient) -> None:
    oversized = MINIMAL_PDF + b"0" * MAX_UPLOAD_BYTES

    response = client.post(
        "/documents",
        files={"file": ("oversized.pdf", oversized, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_rejected_uploads_leave_no_files_behind(client: TestClient, documents_dir: Path) -> None:
    client.post(
        "/documents",
        files={"file": ("spoofed.pdf", b"not a pdf", "application/pdf")},
    )
    client.post(
        "/documents",
        files={"file": ("oversized.pdf", MINIMAL_PDF + b"0" * MAX_UPLOAD_BYTES, "application/pdf")},
    )

    assert list(documents_dir.iterdir()) == []
