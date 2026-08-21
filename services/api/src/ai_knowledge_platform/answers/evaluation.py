"""Versioned live evaluation for grounded answer quality."""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ai_knowledge_platform.answers.domain import AnswerOutcome, GroundedAnswer
from ai_knowledge_platform.answers.openai_generator import OpenAIAnswerGenerator
from ai_knowledge_platform.answers.service import answer_question
from ai_knowledge_platform.config import Settings
from ai_knowledge_platform.documents.domain import DocumentExtraction, ExtractedPage
from ai_knowledge_platform.retrieval.chunking import chunk_extraction
from ai_knowledge_platform.retrieval.domain import DocumentIndex
from ai_knowledge_platform.retrieval.repository import replace_document_index

SERVICE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = SERVICE_ROOT / "evals" / "answers_v1.json"


class EvaluationPage(BaseModel):
    page_number: Annotated[int, Field(gt=0)]
    text: str


class EvaluationDocument(BaseModel):
    document_id: UUID
    filename: str
    pages: list[EvaluationPage]


class ExpectedPage(BaseModel):
    document_id: UUID
    page_number: Annotated[int, Field(gt=0)]


class RequiredFact(BaseModel):
    id: str
    alternatives: Annotated[list[str], Field(min_length=1)]
    acceptable_pages: Annotated[list[ExpectedPage], Field(min_length=1)]


class AnswerEvaluationCase(BaseModel):
    id: str
    question: str
    language: Literal["en", "es"]
    tags: list[
        Literal[
            "answerable", "unanswerable", "multi_evidence", "adversarial", "lexical_false_friend"
        ]
    ]
    expected_outcome: Literal["answered", "insufficient_evidence"]
    required_facts: list[RequiredFact] = Field(default_factory=list)
    forbidden_phrases: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_expected_content(self) -> "AnswerEvaluationCase":
        if self.expected_outcome == "answered" and not self.required_facts:
            raise ValueError("answerable cases require facts")
        if self.expected_outcome == "insufficient_evidence" and self.required_facts:
            raise ValueError("unanswerable cases cannot require facts")
        return self


class EvaluationThresholds(BaseModel):
    outcome_accuracy: Annotated[float, Field(ge=0, le=1)]
    unanswerable_refusal_accuracy: Annotated[float, Field(ge=0, le=1)]
    citation_validity: Annotated[float, Field(ge=0, le=1)]
    citation_completeness: Annotated[float, Field(ge=0, le=1)]
    citation_page_correctness: Annotated[float, Field(ge=0, le=1)]
    required_fact_coverage: Annotated[float, Field(ge=0, le=1)]
    forbidden_fact_rate: Annotated[float, Field(ge=0, le=1)]


class AnswerEvaluationDataset(BaseModel):
    schema_version: Literal[1]
    name: str
    chunk_size_chars: Annotated[int, Field(gt=0)]
    chunk_overlap_chars: Annotated[int, Field(ge=0)]
    evidence_limit: Annotated[int, Field(ge=1, le=10)]
    thresholds: EvaluationThresholds
    documents: Annotated[list[EvaluationDocument], Field(min_length=1)]
    cases: Annotated[list[AnswerEvaluationCase], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_policy_coverage(self) -> "AnswerEvaluationDataset":
        tags = [tag for case in self.cases for tag in case.tags]
        if tags.count("answerable") < 6:
            raise ValueError("answer evaluation requires at least six answerable cases")
        if tags.count("unanswerable") < 3:
            raise ValueError("answer evaluation requires at least three unanswerable cases")
        if tags.count("multi_evidence") < 2:
            raise ValueError("answer evaluation requires at least two multi-evidence cases")
        if "adversarial" not in tags or "lexical_false_friend" not in tags:
            raise ValueError(
                "answer evaluation requires adversarial and lexical false-friend cases"
            )
        if {case.language for case in self.cases} != {"en", "es"}:
            raise ValueError("answer evaluation requires English and Spanish cases")
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("evaluation chunk overlap must be smaller than chunk size")
        return self


class CaseResult(BaseModel):
    id: str
    expected_outcome: str
    actual_outcome: str
    outcome_correct: bool
    facts_found: int
    fact_count: int
    citation_pages_correct: int
    cited_fact_count: int
    forbidden_phrases_found: list[str]


class EvaluationReport(BaseModel):
    dataset: str
    model: str
    case_count: int
    outcome_accuracy: float
    unanswerable_refusal_accuracy: float
    citation_validity: float
    citation_completeness: float
    citation_page_correctness: float
    required_fact_coverage: float
    forbidden_fact_rate: float
    passed: bool
    cases: list[CaseResult]


def load_dataset(dataset_path: Path = DEFAULT_DATASET) -> AnswerEvaluationDataset:
    return AnswerEvaluationDataset.model_validate_json(dataset_path.read_text(encoding="utf-8"))


async def run_evaluation(
    settings: Settings,
    dataset_path: Path = DEFAULT_DATASET,
) -> EvaluationReport:
    dataset = load_dataset(dataset_path)
    if not settings.generation_configured:
        raise ValueError("AKP_OPENAI_API_KEY and AKP_OPENAI_MODEL are required")

    api_key = settings.openai_api_key
    model = settings.openai_model
    assert api_key is not None and model is not None
    generator = OpenAIAnswerGenerator(
        api_key=api_key.get_secret_value(),
        model=model,
        timeout_seconds=settings.answer_timeout_seconds,
        max_output_tokens=settings.answer_max_output_tokens,
    )

    try:
        with TemporaryDirectory(prefix="akp-answer-eval-") as temporary_dir:
            temporary_path = Path(temporary_dir)
            database_path = temporary_path / "knowledge.db"
            _index_corpus(dataset, database_path)
            answers = [
                await answer_question(
                    case.question,
                    generator=generator,
                    documents_dir=temporary_path / "documents",
                    database_path=database_path,
                    evidence_limit=dataset.evidence_limit,
                    document_id=None,
                )
                for case in dataset.cases
            ]
    finally:
        await generator.close()

    return _build_report(dataset, model=model, answers=answers)


def _index_corpus(dataset: AnswerEvaluationDataset, database_path: Path) -> None:
    fixed_time = datetime(2026, 8, 21, tzinfo=UTC)
    for source in dataset.documents:
        extraction = DocumentExtraction(
            document_id=source.document_id,
            pages=tuple(
                ExtractedPage(page_number=page.page_number, text=page.text) for page in source.pages
            ),
            extracted_at=fixed_time,
        )
        chunks = chunk_extraction(
            extraction,
            max_chars=dataset.chunk_size_chars,
            overlap_chars=dataset.chunk_overlap_chars,
        )
        replace_document_index(
            database_path,
            DocumentIndex(
                document_id=source.document_id,
                filename=source.filename,
                chunk_count=len(chunks),
                indexed_at=fixed_time,
            ),
            chunks,
        )


def _build_report(
    dataset: AnswerEvaluationDataset,
    *,
    model: str,
    answers: list[GroundedAnswer],
) -> EvaluationReport:
    results = [
        _evaluate_case(case, answer) for case, answer in zip(dataset.cases, answers, strict=True)
    ]
    answerable = [case for case in results if case.fact_count]
    unanswerable = [
        case for case in results if case.expected_outcome == AnswerOutcome.INSUFFICIENT_EVIDENCE
    ]
    total_claims = sum(len(answer.claims) for answer in answers)
    cited_claims = sum(
        sum(bool(claim.citation_ids) for claim in answer.claims) for answer in answers
    )
    citations = [citation for answer in answers for citation in answer.citations]
    valid_citations = sum(
        citation.end_offset - citation.start_offset == len(citation.text)
        and citation.page_number > 0
        for citation in citations
    )
    fact_count = sum(case.fact_count for case in answerable)
    facts_found = sum(case.facts_found for case in answerable)
    cited_fact_count = sum(case.cited_fact_count for case in answerable)
    correct_pages = sum(case.citation_pages_correct for case in answerable)
    forbidden_total = sum(len(case.forbidden_phrases) for case in dataset.cases)
    forbidden_found = sum(len(case.forbidden_phrases_found) for case in results)

    metrics = {
        "outcome_accuracy": _ratio(sum(case.outcome_correct for case in results), len(results)),
        "unanswerable_refusal_accuracy": _ratio(
            sum(case.outcome_correct for case in unanswerable), len(unanswerable)
        ),
        "citation_validity": _ratio(valid_citations, len(citations)),
        "citation_completeness": _ratio(cited_claims, total_claims),
        "citation_page_correctness": _ratio(correct_pages, cited_fact_count),
        "required_fact_coverage": _ratio(facts_found, fact_count),
        "forbidden_fact_rate": _ratio(forbidden_found, forbidden_total),
    }
    thresholds = dataset.thresholds
    passed = (
        metrics["outcome_accuracy"] >= thresholds.outcome_accuracy
        and metrics["unanswerable_refusal_accuracy"] >= thresholds.unanswerable_refusal_accuracy
        and metrics["citation_validity"] >= thresholds.citation_validity
        and metrics["citation_completeness"] >= thresholds.citation_completeness
        and metrics["citation_page_correctness"] >= thresholds.citation_page_correctness
        and metrics["required_fact_coverage"] >= thresholds.required_fact_coverage
        and metrics["forbidden_fact_rate"] <= thresholds.forbidden_fact_rate
    )
    return EvaluationReport(
        dataset=dataset.name,
        model=model,
        case_count=len(results),
        passed=passed,
        cases=results,
        **metrics,
    )


def _evaluate_case(case: AnswerEvaluationCase, answer: GroundedAnswer) -> CaseResult:
    citation_by_id = {citation.id: citation for citation in answer.citations}

    facts_found = 0
    cited_facts = 0
    correct_pages = 0
    for fact in case.required_facts:
        matching_claims = [
            claim
            for claim in answer.claims
            if any(
                alternative.casefold() in claim.text.casefold() for alternative in fact.alternatives
            )
        ]
        if not matching_claims:
            continue
        facts_found += 1
        cited_facts += 1
        acceptable = {(page.document_id, page.page_number) for page in fact.acceptable_pages}
        used_citations = {
            citation_by_id[citation_id]
            for claim in matching_claims
            for citation_id in claim.citation_ids
            if citation_id in citation_by_id
        }
        if any(
            (citation.document_id, citation.page_number) in acceptable
            for citation in used_citations
        ):
            correct_pages += 1

    answer_text = " ".join(claim.text for claim in answer.claims).casefold()
    forbidden = [phrase for phrase in case.forbidden_phrases if phrase.casefold() in answer_text]
    return CaseResult(
        id=case.id,
        expected_outcome=case.expected_outcome,
        actual_outcome=answer.outcome,
        outcome_correct=answer.outcome == case.expected_outcome,
        facts_found=facts_found,
        fact_count=len(case.required_facts),
        citation_pages_correct=correct_pages,
        cited_fact_count=cited_facts,
        forbidden_phrases_found=forbidden,
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate grounded answer quality")
    parser.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the dataset contract without calling a provider",
    )
    arguments = parser.parse_args()
    if arguments.validate_only:
        dataset = load_dataset(arguments.dataset)
        sys.stdout.write(
            f"Validated {dataset.name}: {len(dataset.documents)} documents, "
            f"{len(dataset.cases)} cases.\n"
        )
        return 0

    try:
        report = asyncio.run(run_evaluation(Settings(), arguments.dataset))
    except ValueError as exc:
        sys.stderr.write(f"Answer evaluation is not configured: {exc}\n")
        return 2
    sys.stdout.write(report.model_dump_json(indent=2) + "\n")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
