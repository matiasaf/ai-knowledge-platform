from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_knowledge_platform.answers.domain import (
    AnswerOutcome,
    Evidence,
    GeneratedClaim,
    GenerationResult,
)
from ai_knowledge_platform.answers.ports import (
    GenerationInvalidResponseError,
    GenerationProviderError,
    GenerationTimeoutError,
)
from ai_knowledge_platform.answers.router import get_answer_generator
from tests.conftest import build_text_pdf


class FakeGenerator:
    def __init__(
        self,
        result: GenerationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or GenerationResult(outcome=AnswerOutcome.INSUFFICIENT_EVIDENCE)
        self.error = error
        self.calls: list[tuple[str, tuple[Evidence, ...]]] = []

    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> GenerationResult:
        self.calls.append((question, evidence))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def indexed_document(client: TestClient) -> dict[str, object]:
    upload = client.post(
        "/documents",
        files={
            "file": (
                "security-runbook.pdf",
                build_text_pdf(["A lost company device must be reported within one hour."]),
                "application/pdf",
            )
        },
    )
    document = upload.json()
    assert client.post(f"/documents/{document['id']}/extraction").status_code == 200
    assert client.post(f"/documents/{document['id']}/index").status_code == 200
    return cast("dict[str, object]", document)


def test_answers_with_claims_and_server_resolved_citations(
    client: TestClient,
    indexed_document: dict[str, object],
) -> None:
    generator = FakeGenerator(
        GenerationResult(
            outcome=AnswerOutcome.ANSWERED,
            claims=(
                GeneratedClaim(
                    text="It must be reported within one hour.",
                    evidence_ids=("E1",),
                ),
            ),
        )
    )

    with OverrideGenerator(client, generator):
        response = client.post(
            "/answers",
            json={
                "question": "How soon must a lost device be reported?",
                "document_id": indexed_document["id"],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "answered"
    assert body["claims"] == [
        {
            "text": "It must be reported within one hour.",
            "citation_ids": ["C1"],
        }
    ]
    citation = body["citations"][0]
    assert citation["document_id"] == indexed_document["id"]
    assert citation["filename"] == "security-runbook.pdf"
    assert citation["page_number"] == 1
    assert citation["source_path"] == f"/documents/{indexed_document['id']}/content"
    assert len(generator.calls) == 1
    assert generator.calls[0][1][0].id == "E1"


def test_returns_insufficient_evidence_without_calling_generator(
    client: TestClient,
    indexed_document: dict[str, object],
) -> None:
    generator = FakeGenerator()

    with OverrideGenerator(client, generator):
        response = client.post(
            "/answers",
            json={
                "question": "What is the parental leave policy?",
                "document_id": indexed_document["id"],
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "question": "What is the parental leave policy?",
        "outcome": "insufficient_evidence",
        "claims": [],
        "citations": [],
    }
    assert generator.calls == []


def test_returns_safety_refusal_as_a_business_outcome(
    client: TestClient,
    indexed_document: dict[str, object],
) -> None:
    generator = FakeGenerator(GenerationResult(outcome=AnswerOutcome.SAFETY_REFUSED))

    with OverrideGenerator(client, generator):
        response = client.post(
            "/answers",
            json={
                "question": "What must be reported?",
                "document_id": indexed_document["id"],
            },
        )

    assert response.status_code == 200
    assert response.json()["outcome"] == "safety_refused"
    assert response.json()["claims"] == []
    assert response.json()["citations"] == []


def test_requires_generation_configuration_before_answering(
    client: TestClient,
    indexed_document: dict[str, object],
) -> None:
    response = client.post(
        "/answers",
        json={"question": "What must be reported?", "document_id": indexed_document["id"]},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "generation_not_configured"


def test_rejects_a_document_that_is_not_indexed(client: TestClient) -> None:
    upload = client.post(
        "/documents",
        files={"file": ("stored.pdf", build_text_pdf(["Stored only."]), "application/pdf")},
    )

    with OverrideGenerator(client, FakeGenerator()):
        response = client.post(
            "/answers",
            json={"question": "What is stored?", "document_id": upload.json()["id"]},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_indexed"


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (GenerationTimeoutError(), 504, "generation_timeout"),
        (GenerationProviderError(), 502, "generation_provider_error"),
        (GenerationInvalidResponseError(), 502, "generation_invalid_response"),
    ],
)
def test_translates_generation_failures(
    client: TestClient,
    indexed_document: dict[str, object],
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    with OverrideGenerator(client, FakeGenerator(error=error)):
        response = client.post(
            "/answers",
            json={
                "question": "When must a lost device be reported?",
                "document_id": indexed_document["id"],
            },
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code


def test_rejects_unknown_request_fields(client: TestClient) -> None:
    with OverrideGenerator(client, FakeGenerator()):
        response = client.post(
            "/answers",
            json={"question": "A valid question?", "model": "client-controlled"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_opens_the_original_pdf_inline(
    client: TestClient,
    indexed_document: dict[str, object],
) -> None:
    response = client.get(f"/documents/{indexed_document['id']}/content")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.content.startswith(b"%PDF-")


def test_reports_a_missing_stored_pdf(
    client: TestClient,
    indexed_document: dict[str, object],
    documents_dir: Path,
) -> None:
    document_id = UUID(str(indexed_document["id"]))
    (documents_dir / f"{document_id}.pdf").unlink()

    response = client.get(f"/documents/{document_id}/content")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"


def test_reports_a_corrupt_stored_pdf(
    client: TestClient,
    indexed_document: dict[str, object],
    documents_dir: Path,
) -> None:
    document_id = UUID(str(indexed_document["id"]))
    (documents_dir / f"{document_id}.pdf").write_bytes(b"not a pdf")

    response = client.get(f"/documents/{document_id}/content")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"


class OverrideGenerator:
    def __init__(self, client: TestClient, generator: FakeGenerator) -> None:
        self.client = client
        self.generator = generator

    def __enter__(self) -> None:
        app = cast("FastAPI", self.client.app)
        app.dependency_overrides[get_answer_generator] = lambda: self.generator

    def __exit__(self, *_: object) -> None:
        app = cast("FastAPI", self.client.app)
        app.dependency_overrides.pop(get_answer_generator, None)
