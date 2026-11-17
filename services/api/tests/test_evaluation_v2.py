import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ai_knowledge_platform.evaluation.__main__ import main
from ai_knowledge_platform.evaluation.dataset import DEFAULT_DATASET, Dataset, load_dataset
from ai_knowledge_platform.evaluation.retrieval import evaluate_retrieval

HANDBOOK = "11111111-1111-4111-8111-111111111111"
RUNBOOK = "22222222-2222-4222-8222-222222222222"


def _raw() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(DEFAULT_DATASET.read_text(encoding="utf-8"))
    return raw


def _case(raw: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(case for case in raw["cases"] if case["id"] == case_id)


def _page(document_id: str, page_number: int) -> dict[str, Any]:
    return {"document_id": document_id, "page_number": page_number}


def test_fixture_is_a_valid_unreviewed_draft() -> None:
    dataset = load_dataset()

    assert dataset.name == "v2-fixture"
    assert dataset.stage == "draft"
    assert [case.type for case in dataset.cases].count("unanswerable") == 4
    assert [case.type for case in dataset.cases].count("multi_doc") == 2
    assert not any(case.reviewed for case in dataset.cases)


def _unanswerable_with_page(raw: dict[str, Any]) -> None:
    _case(raw, "unknown-parental-leave")["relevant"] = [_page(HANDBOOK, 1)]


def _multi_doc_in_one_document(raw: dict[str, Any]) -> None:
    case = _case(raw, "leave-and-device-window")
    case["relevant"] = [_page(HANDBOOK, 2)]
    case["required_facts"] = case["required_facts"][:1]


def _factual_spanning_documents(raw: dict[str, Any]) -> None:
    _case(raw, "annual-leave-days")["relevant"].append(_page(RUNBOOK, 1))


def _page_missing_from_corpus(raw: dict[str, Any]) -> None:
    _case(raw, "annual-leave-days")["relevant"] = [_page(HANDBOOK, 9)]
    _case(raw, "annual-leave-days")["required_facts"][0]["acceptable_pages"] = [_page(HANDBOOK, 9)]


def _span_past_page_end(raw: dict[str, Any]) -> None:
    _case(raw, "annual-leave-days")["relevant"][0]["span"] = {
        "start_offset": 0,
        "end_offset": 10_000,
    }


def _fact_not_on_its_page(raw: dict[str, Any]) -> None:
    _case(raw, "annual-leave-days")["required_facts"][0]["alternatives"] = ["thirty days"]


def _fact_page_not_relevant(raw: dict[str, Any]) -> None:
    fact = _case(raw, "annual-leave-days")["required_facts"][0]
    fact["acceptable_pages"] = [_page(HANDBOOK, 1)]


def _duplicate_case_id(raw: dict[str, Any]) -> None:
    raw["cases"].append(dict(raw["cases"][0]))


def _answerable_without_expected_answer(raw: dict[str, Any]) -> None:
    _case(raw, "annual-leave-days")["expected_answer"] = None


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_unanswerable_with_page, "unanswerable cases cannot have relevant passages"),
        (_multi_doc_in_one_document, "multi_doc cases need passages from two documents"),
        (_factual_spanning_documents, "must use type multi_doc"),
        (_page_missing_from_corpus, "relevant page is not in the corpus"),
        (_span_past_page_end, "span exceeds page length"),
        (_fact_not_on_its_page, "no alternative for fact leave-days appears"),
        (_fact_page_not_relevant, "cites a page not listed as relevant"),
        (_duplicate_case_id, "duplicate case id"),
        (_answerable_without_expected_answer, "answerable cases require expected_answer"),
    ],
)
def test_contract_rejects_inconsistent_labels(
    mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    raw = _raw()
    mutate(raw)

    with pytest.raises(ValidationError, match=message):
        Dataset.model_validate(raw)


def test_a_draft_cannot_be_promoted_to_baseline() -> None:
    raw = _raw()
    raw["stage"] = "baseline"

    with pytest.raises(ValidationError) as error:
        Dataset.model_validate(raw)

    message = str(error.value)
    assert "30-40 cases" in message
    assert "at least 5 unanswerable cases" in message
    assert "every case reviewed" in message
    assert "retrieval thresholds" in message


def test_fixture_retrieval_reports_misses_and_denominators() -> None:
    report = evaluate_retrieval(load_dataset())
    by_id = {case.id: case for case in report.cases}

    assert report.threshold_status == "not_set"
    assert report.answerable.case_count == 10
    assert report.answerable.hit_rate_at_k == pytest.approx(0.8)
    assert report.answerable.recall_at_k == pytest.approx(0.8)
    assert report.answerable.mrr_at_k == pytest.approx(0.8)
    assert report.by_type["multi_doc"].recall_at_k == 1.0
    # Lexical retrieval misses a paraphrase and a Spanish question over English text.
    assert by_id["credential-rotation-paraphrase"].first_relevant_rank is None
    assert by_id["leave-request-portal-es"].relevant_found == 0
    assert report.unanswerable.case_count == 4
    assert report.unanswerable.cases_with_matches == 2
    assert not report.failures


def test_span_restricts_relevance_to_overlapping_chunks() -> None:
    raw = _raw()
    case = _case(raw, "adversarial-incident-channel")
    case["relevant"][0]["span"] = {"start_offset": 0, "end_offset": 5}

    report = evaluate_retrieval(Dataset.model_validate(raw))
    result = next(item for item in report.cases if item.id == "adversarial-incident-channel")

    assert result.relevant_found == 0


def test_thresholds_fail_explicitly() -> None:
    raw = _raw()
    raw["retrieval"]["thresholds"] = {"hit_rate_at_k": 0.9, "recall_at_k": 0.9, "mrr_at_k": 0.9}

    report = evaluate_retrieval(Dataset.model_validate(raw))

    assert report.threshold_status == "failed"


def test_cli_writes_json_and_markdown_without_page_text(tmp_path: Path) -> None:
    assert main(["--output-dir", str(tmp_path)]) == 0

    [json_path] = tmp_path.glob("*.json")
    [markdown_path] = tmp_path.glob("*.md")
    assert json_path.stem == markdown_path.stem
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["run"]["mode"] == "offline"
    assert report["run"]["model"] is None
    assert report["run"]["dataset_name"] == "v2-fixture"
    assert len(report["run"]["dataset_sha256"]) == 64
    assert report["configuration"]["k"] == 3
    assert report["retrieval"]["answerable"]["case_count"] == 10
    assert report["failures"] == []
    page_text = "Full-time employees receive twenty business days"
    assert page_text not in json_path.read_text(encoding="utf-8")
    assert "not a baseline" in markdown_path.read_text(encoding="utf-8")


def test_cli_rejects_invalid_dataset(tmp_path: Path) -> None:
    raw = _raw()
    _unanswerable_with_page(raw)
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(raw), encoding="utf-8")

    assert main([str(invalid), "--validate-only"]) == 2


def test_validate_only_writes_nothing(tmp_path: Path) -> None:
    assert main(["--validate-only", "--output-dir", str(tmp_path)]) == 0
    assert not any(tmp_path.iterdir())
