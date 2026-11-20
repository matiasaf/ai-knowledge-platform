"""Offline retrieval metrics for schema v2 datasets.

The corpus is indexed into a temporary SQLite database with the dataset's chunking,
then each question goes through the production `search_chunks` path.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from ai_knowledge_platform.documents.domain import DocumentExtraction, ExtractedPage
from ai_knowledge_platform.errors import ApiError
from ai_knowledge_platform.evaluation.dataset import Case, CaseType, Dataset, RelevantPassage
from ai_knowledge_platform.retrieval.chunking import chunk_extraction
from ai_knowledge_platform.retrieval.domain import DocumentIndex, RetrievalMatch
from ai_knowledge_platform.retrieval.repository import replace_document_index, search_chunks

ThresholdStatus = Literal["passed", "failed", "not_set"]
_FIXED_TIME = datetime(2026, 11, 9, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class CaseResult:
    id: str
    type: CaseType
    question: str
    retrieved_count: int
    relevant_count: int
    relevant_found: int
    first_relevant_rank: int | None
    error: str | None

    @property
    def hit(self) -> bool:
        return self.relevant_found > 0

    @property
    def recall(self) -> float:
        return self.relevant_found / self.relevant_count if self.relevant_count else 0.0

    @property
    def reciprocal_rank(self) -> float:
        return 1 / self.first_relevant_rank if self.first_relevant_rank else 0.0


@dataclass(frozen=True, slots=True)
class RankingMetrics:
    """Means over answerable cases; `case_count` is the denominator."""

    case_count: int
    hit_rate_at_k: float
    recall_at_k: float
    mrr_at_k: float


@dataclass(frozen=True, slots=True)
class UnanswerableMetrics:
    """Lexical search has no abstention, so any match here is reported, not gated."""

    case_count: int
    cases_with_matches: int
    match_rate: float


@dataclass(frozen=True, slots=True)
class RetrievalReport:
    k: int
    answerable: RankingMetrics
    by_type: dict[str, RankingMetrics]
    unanswerable: UnanswerableMetrics
    threshold_status: ThresholdStatus
    cases: tuple[CaseResult, ...]

    @property
    def failures(self) -> tuple[CaseResult, ...]:
        return tuple(case for case in self.cases if case.error)


def evaluate_retrieval(dataset: Dataset) -> RetrievalReport:
    config = dataset.retrieval
    with TemporaryDirectory(prefix="akp-eval-v2-") as temporary_dir:
        database_path = Path(temporary_dir) / "knowledge.db"
        _index_corpus(dataset, database_path)
        results = tuple(
            _evaluate_case(case, database_path=database_path, k=config.k) for case in dataset.cases
        )

    answerable = [case for case in results if case.type != "unanswerable"]
    unanswerable = [case for case in results if case.type == "unanswerable"]
    with_matches = sum(case.retrieved_count > 0 for case in unanswerable)
    report = RetrievalReport(
        k=config.k,
        answerable=_ranking(answerable),
        by_type={
            case_type: _ranking([case for case in answerable if case.type == case_type])
            for case_type in ("factual", "multi_doc")
        },
        unanswerable=UnanswerableMetrics(
            case_count=len(unanswerable),
            cases_with_matches=with_matches,
            match_rate=with_matches / len(unanswerable) if unanswerable else 0.0,
        ),
        threshold_status="not_set",
        cases=results,
    )
    return replace(report, threshold_status=_threshold_status(dataset, report))


def _index_corpus(dataset: Dataset, database_path: Path) -> None:
    for source in dataset.corpus.documents:
        extraction = DocumentExtraction(
            document_id=source.document_id,
            pages=tuple(
                ExtractedPage(page_number=page.page_number, text=page.text) for page in source.pages
            ),
            extracted_at=_FIXED_TIME,
        )
        chunks = chunk_extraction(
            extraction,
            max_chars=dataset.retrieval.chunk_size_chars,
            overlap_chars=dataset.retrieval.chunk_overlap_chars,
        )
        replace_document_index(
            database_path,
            DocumentIndex(
                document_id=source.document_id,
                filename=source.filename,
                chunk_count=len(chunks),
                indexed_at=_FIXED_TIME,
            ),
            chunks,
        )


def _evaluate_case(case: Case, *, database_path: Path, k: int) -> CaseResult:
    try:
        matches = search_chunks(database_path, case.question, limit=k)
    except ApiError as exc:
        # A search failure is a miss with a recorded error, never a skipped case.
        return CaseResult(
            id=case.id,
            type=case.type,
            question=case.question,
            retrieved_count=0,
            relevant_count=len(case.relevant),
            relevant_found=0,
            first_relevant_rank=None,
            error=f"{exc.code}: {exc.message}",
        )

    found: set[int] = set()
    first_rank: int | None = None
    for match in matches:
        hits = {i for i, passage in enumerate(case.relevant) if _matches(match, passage)}
        if hits and first_rank is None:
            first_rank = match.rank
        found |= hits
    return CaseResult(
        id=case.id,
        type=case.type,
        question=case.question,
        retrieved_count=len(matches),
        relevant_count=len(case.relevant),
        relevant_found=len(found),
        first_relevant_rank=first_rank,
        error=None,
    )


def _matches(match: RetrievalMatch, passage: RelevantPassage) -> bool:
    if (match.document_id, match.page_number) != (passage.document_id, passage.page_number):
        return False
    if passage.span is None:
        return True
    return (
        match.start_offset < passage.span.end_offset
        and passage.span.start_offset < match.end_offset
    )


def _ranking(cases: list[CaseResult]) -> RankingMetrics:
    count = len(cases)
    if not count:
        return RankingMetrics(case_count=0, hit_rate_at_k=0.0, recall_at_k=0.0, mrr_at_k=0.0)
    return RankingMetrics(
        case_count=count,
        hit_rate_at_k=sum(case.hit for case in cases) / count,
        recall_at_k=sum(case.recall for case in cases) / count,
        mrr_at_k=sum(case.reciprocal_rank for case in cases) / count,
    )


def _threshold_status(dataset: Dataset, report: RetrievalReport) -> ThresholdStatus:
    if report.failures:
        return "failed"
    thresholds = dataset.retrieval.thresholds
    if thresholds is None:
        return "not_set"
    metrics = report.answerable
    passed = (
        metrics.case_count > 0
        and metrics.hit_rate_at_k >= thresholds.hit_rate_at_k
        and metrics.recall_at_k >= thresholds.recall_at_k
        and metrics.mrr_at_k >= thresholds.mrr_at_k
    )
    return "passed" if passed else "failed"
