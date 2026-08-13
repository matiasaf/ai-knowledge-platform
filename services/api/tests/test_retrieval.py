import json
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from ai_knowledge_platform.config import Settings
from tests.conftest import build_text_pdf


def _upload_extract_and_index(
    client: TestClient,
    page_texts: list[str],
    filename: str = "handbook.pdf",
) -> tuple[dict[str, object], dict[str, object]]:
    upload = client.post(
        "/documents",
        files={"file": (filename, build_text_pdf(page_texts), "application/pdf")},
    )
    assert upload.status_code == 201
    document = upload.json()
    extraction = client.post(f"/documents/{document['id']}/extraction")
    assert extraction.status_code == 200
    indexed = client.post(f"/documents/{document['id']}/index")
    assert indexed.status_code == 200
    return document, indexed.json()


def test_indexes_extracted_pages_and_returns_ranked_evidence(
    client: TestClient,
    documents_dir: Path,
    settings: Settings,
) -> None:
    document, indexed = _upload_extract_and_index(
        client,
        [
            "Annual leave requests are submitted in the people portal.",
            "Expense reports must include an itemized receipt within thirty days.",
        ],
        "employee-handbook.pdf",
    )

    indexed_document = indexed["document"]
    assert isinstance(indexed_document, dict)
    assert indexed_document["status"] == "indexed"
    assert indexed["chunk_count"] == 2
    response = client.post(
        "/retrieval/search",
        json={"query": "Where are annual leave requests submitted?", "limit": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "Where are annual leave requests submitted?"
    assert body["match_count"] >= 1
    first = body["matches"][0]
    assert first["rank"] == 1
    assert first["document_id"] == document["id"]
    assert first["filename"] == "employee-handbook.pdf"
    assert first["page_number"] == 1
    assert first["chunk_index"] == 0
    assert "people portal" in first["text"]
    assert first["end_offset"] - first["start_offset"] == len(first["text"])

    metadata = json.loads(
        (documents_dir / f"{UUID(str(document['id']))}.json").read_text(encoding="utf-8")
    )
    assert metadata["status"] == "indexed"
    assert settings.knowledge_db_path.is_file()


def test_indexing_is_idempotent_and_search_can_be_scoped_to_one_document(
    client: TestClient,
) -> None:
    first_document, first_index = _upload_extract_and_index(
        client,
        ["The support escalation code is ORBIT."],
        "operations.pdf",
    )
    second_document, _ = _upload_extract_and_index(
        client,
        ["The finance approval code is LEDGER."],
        "finance.pdf",
    )

    repeated = client.post(f"/documents/{first_document['id']}/index")
    assert repeated.status_code == 200
    assert repeated.json() == first_index

    unscoped = client.post("/retrieval/search", json={"query": "code"})
    assert unscoped.status_code == 200
    assert {match["document_id"] for match in unscoped.json()["matches"]} == {
        first_document["id"],
        second_document["id"],
    }

    scoped = client.post(
        "/retrieval/search",
        json={"query": "code", "document_id": second_document["id"]},
    )
    assert scoped.status_code == 200
    assert {match["document_id"] for match in scoped.json()["matches"]} == {second_document["id"]}


def test_refuses_indexing_before_extraction(client: TestClient) -> None:
    upload = client.post(
        "/documents",
        files={"file": ("stored.pdf", build_text_pdf(["Not extracted"]), "application/pdf")},
    )

    response = client.post(f"/documents/{upload.json()['id']}/index")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_extracted"


def test_indexes_a_textless_document_without_inventing_chunks(client: TestClient) -> None:
    _, indexed = _upload_extract_and_index(client, [""])

    assert indexed["chunk_count"] == 0
    search = client.post("/retrieval/search", json={"query": "anything"})
    assert search.status_code == 200
    assert search.json()["matches"] == []


def test_plain_language_search_does_not_expose_fts_query_syntax(client: TestClient) -> None:
    _upload_extract_and_index(client, ["A literal policy OR operator is harmless."])

    response = client.post(
        "/retrieval/search",
        json={"query": 'policy OR "unterminated ( NEAR'},
    )

    assert response.status_code == 200
    assert response.json()["match_count"] >= 1


def test_search_rejects_a_query_without_letters_or_numbers(client: TestClient) -> None:
    response = client.post("/retrieval/search", json={"query": "!? --"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "search_query_empty"
