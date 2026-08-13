import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from ai_knowledge_platform.documents import extraction as extraction_module
from ai_knowledge_platform.documents.domain import DocumentExtraction, ExtractedPage
from tests.conftest import MAX_PDF_PAGES, build_text_pdf


def _upload(
    client: TestClient,
    content: bytes,
    filename: str = "handbook.pdf",
) -> dict[str, object]:
    response = client.post(
        "/documents",
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def _encrypted_pdf() -> bytes:
    sink = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("not-shared-with-the-api", algorithm="RC4-128")
    writer.write(sink)
    return sink.getvalue()


def test_extracts_text_with_page_provenance_and_records_empty_pages(
    client: TestClient,
    documents_dir: Path,
) -> None:
    uploaded = _upload(client, build_text_pdf(["Policy alpha", ""]))

    response = client.post(f"/documents/{uploaded['id']}/extraction")

    assert response.status_code == 200
    body = response.json()
    assert body["document"]["id"] == uploaded["id"]
    assert body["document"]["status"] == "extracted"
    assert body["document"]["updated_at"] != uploaded["updated_at"]
    assert body["page_count"] == 2
    assert body["empty_page_count"] == 1
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert "Policy alpha" in body["pages"][0]["text"]
    assert body["pages"][0]["character_count"] == len(body["pages"][0]["text"])
    assert body["pages"][1] == {"page_number": 2, "text": "", "character_count": 0}

    document_id = UUID(str(uploaded["id"]))
    metadata = json.loads((documents_dir / f"{document_id}.json").read_text(encoding="utf-8"))
    extraction = json.loads(
        (documents_dir / f"{document_id}.extraction.json").read_text(encoding="utf-8")
    )
    assert metadata["status"] == "extracted"
    assert extraction["document_id"] == uploaded["id"]
    assert extraction["pages"] == body["pages"]


def test_repeating_extraction_returns_the_persisted_result(client: TestClient) -> None:
    uploaded = _upload(client, build_text_pdf(["Stable text"]))

    first = client.post(f"/documents/{uploaded['id']}/extraction")
    second = client.post(f"/documents/{uploaded['id']}/extraction")

    assert second.status_code == 200
    assert second.json() == first.json()


def test_processing_status_is_persisted_while_parser_work_is_running(
    client: TestClient,
    documents_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploaded = _upload(client, build_text_pdf(["Original text"]))
    document_id = UUID(str(uploaded["id"]))
    observed_statuses: list[str] = []

    def observe_processing(
        content_path: Path, extracted_id: UUID, max_pages: int
    ) -> DocumentExtraction:
        metadata = json.loads((documents_dir / f"{document_id}.json").read_text(encoding="utf-8"))
        observed_statuses.append(metadata["status"])
        assert content_path == documents_dir / f"{document_id}.pdf"
        assert extracted_id == document_id
        assert max_pages == MAX_PDF_PAGES
        return DocumentExtraction(
            document_id=document_id,
            pages=(ExtractedPage(page_number=1, text="Observed text"),),
            extracted_at=datetime.now(UTC),
        )

    monkeypatch.setattr(extraction_module, "_extract_pdf", observe_processing)

    response = client.post(f"/documents/{document_id}/extraction")

    assert response.status_code == 200
    assert observed_statuses == ["processing"]
    assert response.json()["document"]["status"] == "extracted"


def test_rejects_encrypted_pdf_without_removing_the_stored_source(
    client: TestClient,
    documents_dir: Path,
) -> None:
    uploaded = _upload(client, _encrypted_pdf(), "protected.pdf")

    response = client.post(f"/documents/{uploaded['id']}/extraction")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "encrypted_pdf"
    document_id = UUID(str(uploaded["id"]))
    metadata = json.loads((documents_dir / f"{document_id}.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "extraction_failed"
    assert (documents_dir / f"{document_id}.pdf").is_file()
    assert not (documents_dir / f"{document_id}.extraction.json").exists()


def test_rejects_pdf_above_page_limit_and_keeps_every_page_out_of_storage(
    client: TestClient,
    documents_dir: Path,
) -> None:
    uploaded = _upload(client, build_text_pdf(["one", "two", "three"]))

    response = client.post(f"/documents/{uploaded['id']}/extraction")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pdf_page_limit_exceeded"
    assert str(MAX_PDF_PAGES) in response.json()["error"]["message"]
    assert not (documents_dir / f"{uploaded['id']}.extraction.json").exists()


def test_reports_a_pdf_that_cannot_be_parsed_and_keeps_it_retryable(client: TestClient) -> None:
    uploaded = _upload(client, b"%PDF-this-is-not-a-readable-document")

    response = client.post(f"/documents/{uploaded['id']}/extraction")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pdf_extraction_failed"


def test_reports_missing_document_with_stable_error_code(client: TestClient) -> None:
    response = client.post("/documents/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa/extraction")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
