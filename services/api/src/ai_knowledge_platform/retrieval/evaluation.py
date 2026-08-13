"""Reproducible retrieval evaluation over a fixed, versioned corpus."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ai_knowledge_platform.documents.domain import DocumentExtraction, ExtractedPage
from ai_knowledge_platform.retrieval.chunking import chunk_extraction
from ai_knowledge_platform.retrieval.domain import DocumentIndex
from ai_knowledge_platform.retrieval.repository import replace_document_index, search_chunks

SERVICE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = SERVICE_ROOT / "evals" / "retrieval_v1.json"


class EvaluationPage(BaseModel):
    page_number: Annotated[int, Field(gt=0)]
    text: str


class EvaluationDocument(BaseModel):
    document_id: UUID
    filename: str
    pages: list[EvaluationPage]


class RelevantPage(BaseModel):
    document_id: UUID
    page_number: Annotated[int, Field(gt=0)]


class EvaluationCase(BaseModel):
    id: str
    query: str
    relevant_pages: list[RelevantPage]


class EvaluationThresholds(BaseModel):
    recall_at_k: Annotated[float, Field(ge=0, le=1)]
    mrr_at_k: Annotated[float, Field(ge=0, le=1)]


class EvaluationDataset(BaseModel):
    schema_version: Literal[1]
    name: str
    chunk_size_chars: Annotated[int, Field(gt=0)]
    chunk_overlap_chars: Annotated[int, Field(ge=0)]
    k: Annotated[int, Field(gt=0, le=20)]
    thresholds: EvaluationThresholds
    documents: list[EvaluationDocument]
    cases: list[EvaluationCase]


class EvaluationCaseResult(BaseModel):
    id: str
    query: str
    recall_at_k: float
    reciprocal_rank: float
    first_relevant_rank: int | None


class EvaluationReport(BaseModel):
    dataset: str
    case_count: int
    k: int
    recall_at_k: float
    mrr_at_k: float
    passed: bool
    cases: list[EvaluationCaseResult]


def run_evaluation(dataset_path: Path = DEFAULT_DATASET) -> EvaluationReport:
    dataset = EvaluationDataset.model_validate_json(dataset_path.read_text(encoding="utf-8"))
    if dataset.chunk_overlap_chars >= dataset.chunk_size_chars:
        raise ValueError("evaluation chunk overlap must be smaller than chunk size")
    if not dataset.cases or any(not case.relevant_pages for case in dataset.cases):
        raise ValueError("evaluation requires cases with at least one relevant page")

    with TemporaryDirectory(prefix="akp-retrieval-eval-") as temporary_dir:
        database_path = Path(temporary_dir) / "knowledge.db"
        _index_corpus(dataset, database_path)
        case_results = [
            _evaluate_case(case, database_path=database_path, k=dataset.k) for case in dataset.cases
        ]

    recall = sum(result.recall_at_k for result in case_results) / len(case_results)
    mrr = sum(result.reciprocal_rank for result in case_results) / len(case_results)
    passed = recall >= dataset.thresholds.recall_at_k and mrr >= dataset.thresholds.mrr_at_k
    return EvaluationReport(
        dataset=dataset.name,
        case_count=len(case_results),
        k=dataset.k,
        recall_at_k=recall,
        mrr_at_k=mrr,
        passed=passed,
        cases=case_results,
    )


def _index_corpus(dataset: EvaluationDataset, database_path: Path) -> None:
    fixed_time = datetime(2026, 8, 13, tzinfo=UTC)
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
        document_index = DocumentIndex(
            document_id=source.document_id,
            filename=source.filename,
            chunk_count=len(chunks),
            indexed_at=fixed_time,
        )
        replace_document_index(database_path, document_index, chunks)


def _evaluate_case(
    case: EvaluationCase,
    *,
    database_path: Path,
    k: int,
) -> EvaluationCaseResult:
    matches = search_chunks(database_path, case.query, limit=k)
    relevant = {(expected.document_id, expected.page_number) for expected in case.relevant_pages}
    retrieved = [(match.document_id, match.page_number) for match in matches]
    retrieved_relevant = relevant.intersection(retrieved)
    recall = len(retrieved_relevant) / len(relevant)
    first_relevant_rank = next(
        (rank for rank, page in enumerate(retrieved, start=1) if page in relevant),
        None,
    )
    reciprocal_rank = 1 / first_relevant_rank if first_relevant_rank is not None else 0.0
    return EvaluationCaseResult(
        id=case.id,
        query=case.query,
        recall_at_k=recall,
        reciprocal_rank=reciprocal_rank,
        first_relevant_rank=first_relevant_rank,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate local evidence retrieval")
    parser.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_DATASET)
    arguments = parser.parse_args()
    report = run_evaluation(arguments.dataset)
    sys.stdout.write(report.model_dump_json(indent=2) + "\n")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
