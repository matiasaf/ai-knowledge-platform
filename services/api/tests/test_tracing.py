import hashlib
import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ai_knowledge_platform.answers.domain import (
    AnswerOutcome,
    GeneratedClaim,
    GenerationResult,
    TokenUsage,
)
from ai_knowledge_platform.answers.ports import GenerationTimeoutError
from ai_knowledge_platform.answers.prompt import GROUNDING_INSTRUCTIONS, PROMPT_VERSION
from ai_knowledge_platform.config import Settings, get_settings
from ai_knowledge_platform.main import create_app
from ai_knowledge_platform.observability import middleware
from tests.conftest import build_text_pdf
from tests.test_answers import FakeGenerator, OverrideGenerator

QUESTION = "How soon must a lost device be reported?"


def read_traces(settings: Settings) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(settings.traces_dir.glob("traces-*.jsonl")):
        records.extend(json.loads(line) for line in path.read_text().splitlines())
    return records


def traces_text(settings: Settings) -> str:
    return "".join(p.read_text() for p in settings.traces_dir.glob("traces-*.jsonl"))


@pytest.fixture
def indexed_document_id(client: TestClient) -> str:
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
    document_id = str(upload.json()["id"])
    assert client.post(f"/documents/{document_id}/extraction").status_code == 200
    assert client.post(f"/documents/{document_id}/index").status_code == 200
    return document_id


def test_every_response_carries_a_generated_request_id(client: TestClient) -> None:
    first = client.get("/health")
    second = client.get("/health")

    assert len(first.headers["X-Request-ID"]) == 32
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_safe_client_request_id_is_reused_and_unsafe_one_replaced(
    client: TestClient, settings: Settings
) -> None:
    reused = client.get("/health", headers={"X-Request-ID": "client-abc.123"})
    replaced = client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})

    assert reused.headers["X-Request-ID"] == "client-abc.123"
    assert replaced.headers["X-Request-ID"] != "bad id\nwith newline"
    ids = [record["request_id"] for record in read_traces(settings)]
    assert ids == ["client-abc.123", replaced.headers["X-Request-ID"]]


def test_search_records_route_template_and_retrieval_span_without_query_text(
    client: TestClient, settings: Settings, indexed_document_id: str
) -> None:
    response = client.post("/retrieval/search", json={"query": "lost device reported", "limit": 3})

    assert response.status_code == 200
    record = read_traces(settings)[-1]
    assert record["request_id"] == response.headers["X-Request-ID"]
    assert record["route"] == "/retrieval/search"
    assert record["status_code"] == 200
    assert record["duration_ms"] >= 0
    [retrieval] = record["spans"]
    assert retrieval["name"] == "retrieval"
    assert retrieval["status"] == "ok"
    assert retrieval["attributes"]["k"] == 3
    assert retrieval["attributes"]["matches"] == 1
    assert retrieval["attributes"]["chunks"] == [f"{indexed_document_id}:1:0"]
    assert "lost device reported" not in traces_text(settings)

    index_record = read_traces(settings)[-2]
    assert index_record["route"] == "/documents/{document_id}/index"


def test_answer_records_generation_model_tokens_and_outcome_without_content(
    client: TestClient, settings: Settings, indexed_document_id: str
) -> None:
    generator = FakeGenerator(
        GenerationResult(
            outcome=AnswerOutcome.ANSWERED,
            claims=(GeneratedClaim(text="Within one hour.", evidence_ids=("E1",)),),
            model="test-model-2026-01-01",
            usage=TokenUsage(input_tokens=321, output_tokens=12),
        )
    )

    with OverrideGenerator(client, generator):
        response = client.post(
            "/answers", json={"question": QUESTION, "document_id": indexed_document_id}
        )

    assert response.status_code == 200
    record = read_traces(settings)[-1]
    assert record["route"] == "/answers"
    assert record["attributes"] == {"answer_outcome": "answered"}
    assert [span["name"] for span in record["spans"]] == ["retrieval", "generation"]
    generation = record["spans"][1]
    assert generation["status"] == "ok"
    assert generation["attributes"] == {
        "prompt_version": PROMPT_VERSION,
        "evidence": 1,
        "model": "test-model-2026-01-01",
        "provider_outcome": "answered",
        "input_tokens": 321,
        "output_tokens": 12,
    }
    text = traces_text(settings)
    assert QUESTION not in text
    assert "Within one hour." not in text
    assert "must be reported" not in text


@pytest.mark.usefixtures("indexed_document_id")
def test_retrieval_miss_records_outcome_without_generation_span(
    client: TestClient, settings: Settings
) -> None:
    with OverrideGenerator(client, FakeGenerator()):
        response = client.post(
            "/answers",
            json={"question": "What is the parental leave policy?"},
        )

    assert response.json()["outcome"] == "insufficient_evidence"
    record = read_traces(settings)[-1]
    assert record["attributes"] == {"answer_outcome": "insufficient_evidence"}
    assert [span["name"] for span in record["spans"]] == ["retrieval"]


@pytest.mark.usefixtures("indexed_document_id")
def test_provider_failure_marks_generation_span_as_error(
    client: TestClient, settings: Settings
) -> None:
    with OverrideGenerator(client, FakeGenerator(error=GenerationTimeoutError())):
        response = client.post("/answers", json={"question": QUESTION})

    assert response.status_code == 504
    record = read_traces(settings)[-1]
    assert record["status_code"] == 504
    assert "answer_outcome" not in record["attributes"]
    generation = record["spans"][1]
    assert generation["status"] == "error"
    assert generation["error"] == "GenerationTimeoutError"
    assert generation["duration_ms"] >= 0


@pytest.fixture
def untraced_client(settings: Settings) -> Iterator[TestClient]:
    disabled = settings.model_copy(update={"tracing_enabled": False})
    app = create_app(disabled)
    app.dependency_overrides[get_settings] = lambda: disabled
    with TestClient(app) as test_client:
        yield test_client


def test_disabled_tracing_writes_nothing_but_keeps_request_id(
    untraced_client: TestClient, settings: Settings
) -> None:
    response = untraced_client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert not settings.traces_dir.exists()


def test_trace_write_failure_does_not_change_the_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail(_self: middleware.JsonlTraceSink, _record: dict[str, Any]) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(middleware.JsonlTraceSink, "write", fail)

    response = client.get("/health")

    assert response.status_code == 200
    assert "Could not persist trace" in caplog.text


def test_request_id_header_is_exposed_to_browsers(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert "X-Request-ID" in response.headers["Access-Control-Expose-Headers"]


def test_prompt_version_is_bumped_when_instructions_change() -> None:
    # If this fails, bump PROMPT_VERSION in answers/prompt.py and update this pin.
    pinned = {"grounding-v1": "6a6df4dc1b2be0e38f2f0ba9b5e994fdd8020370c9d158c2425571f415c7736e"}
    digest = hashlib.sha256(GROUNDING_INSTRUCTIONS.encode()).hexdigest()

    assert pinned.get(PROMPT_VERSION) == digest
