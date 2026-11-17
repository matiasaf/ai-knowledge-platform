"""Schema v2 evaluation dataset contract.

One file holds the corpus and every case, so retrieval and answer evaluations score
the same questions. Relevance is labelled by document and page (optionally narrowed to
a character span), never by chunk ID, so labels stay valid when chunking changes.
See docs/plans/evaluation-v2-contract.md.
"""

from collections import Counter
from collections.abc import Hashable, Sequence
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SERVICE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = SERVICE_ROOT / "evals" / "v2_fixture.json"

# A dataset may only call itself a baseline once it meets these minimums.
BASELINE_MIN_CASES = 30
BASELINE_MAX_CASES = 40
BASELINE_MIN_UNANSWERABLE = 5
BASELINE_MIN_MULTI_DOC = 3

CaseType = Literal["factual", "multi_doc", "unanswerable"]
CaseTag = Literal["adversarial", "lexical_false_friend", "paraphrase"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Page(_Strict):
    page_number: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]


class Document(_Strict):
    document_id: UUID
    filename: Annotated[str, Field(min_length=1)]
    pages: Annotated[list[Page], Field(min_length=1)]


class Corpus(_Strict):
    provenance: Annotated[str, Field(min_length=1)]
    license: Annotated[str, Field(min_length=1)]
    documents: Annotated[list[Document], Field(min_length=1)]


class Span(_Strict):
    start_offset: Annotated[int, Field(ge=0)]
    end_offset: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("span end_offset must be greater than start_offset")
        return self


class PageRef(_Strict):
    document_id: UUID
    page_number: Annotated[int, Field(gt=0)]


class RelevantPassage(PageRef):
    """A page that answers the question; a span narrows it to a passage."""

    span: Span | None = None


class RequiredFact(_Strict):
    id: Annotated[str, Field(min_length=1)]
    alternatives: Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1)]
    acceptable_pages: Annotated[list[PageRef], Field(min_length=1)]


class Case(_Strict):
    id: Annotated[str, Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    type: CaseType
    language: Literal["en", "es"]
    tags: list[CaseTag] = Field(default_factory=list)
    question: Annotated[str, Field(min_length=1)]
    expected_answer: str | None
    relevant: list[RelevantPassage] = Field(default_factory=list)
    required_facts: list[RequiredFact] = Field(default_factory=list)
    forbidden_phrases: list[Annotated[str, Field(min_length=1)]] = Field(default_factory=list)
    reviewed: bool

    @model_validator(mode="after")
    def _type_rules(self) -> Self:
        if self.type == "unanswerable":
            if self.relevant or self.required_facts:
                raise ValueError(f"{self.id}: unanswerable cases cannot have relevant passages")
            if self.expected_answer is not None:
                raise ValueError(f"{self.id}: unanswerable cases must set expected_answer null")
            return self

        if not self.expected_answer:
            raise ValueError(f"{self.id}: answerable cases require expected_answer")
        if not self.relevant:
            raise ValueError(f"{self.id}: answerable cases require relevant passages")
        if not self.required_facts:
            raise ValueError(f"{self.id}: answerable cases require required_facts")
        documents = {passage.document_id for passage in self.relevant}
        if self.type == "multi_doc" and len(documents) < 2:
            raise ValueError(f"{self.id}: multi_doc cases need passages from two documents")
        if self.type == "factual" and len(documents) > 1:
            raise ValueError(f"{self.id}: cases spanning documents must use type multi_doc")

        _require_unique(self.id, "fact id", [fact.id for fact in self.required_facts])
        relevant_pages = {(passage.document_id, passage.page_number) for passage in self.relevant}
        for fact in self.required_facts:
            for page in fact.acceptable_pages:
                if (page.document_id, page.page_number) not in relevant_pages:
                    raise ValueError(
                        f"{self.id}: fact {fact.id} cites a page not listed as relevant"
                    )
        return self


class RetrievalThresholds(_Strict):
    hit_rate_at_k: Annotated[float, Field(ge=0, le=1)]
    recall_at_k: Annotated[float, Field(ge=0, le=1)]
    mrr_at_k: Annotated[float, Field(ge=0, le=1)]


class RetrievalConfig(_Strict):
    chunk_size_chars: Annotated[int, Field(gt=0)]
    chunk_overlap_chars: Annotated[int, Field(ge=0)]
    k: Annotated[int, Field(gt=0, le=20)]
    thresholds: RetrievalThresholds | None = None

    @model_validator(mode="after")
    def _overlap(self) -> Self:
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("chunk overlap must be smaller than chunk size")
        return self


class Dataset(_Strict):
    schema_version: Literal[2]
    name: Annotated[str, Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    stage: Literal["draft", "baseline"]
    corpus: Corpus
    retrieval: RetrievalConfig
    cases: Annotated[list[Case], Field(min_length=1)]

    @model_validator(mode="after")
    def _cross_references(self) -> Self:
        _require_unique(self.name, "document id", [d.document_id for d in self.corpus.documents])
        _require_unique(self.name, "case id", [case.id for case in self.cases])
        page_text: dict[tuple[UUID, int], str] = {}
        for document in self.corpus.documents:
            numbers = [page.page_number for page in document.pages]
            _require_unique(document.filename, "page number", numbers)
            for page in document.pages:
                page_text[(document.document_id, page.page_number)] = page.text

        for case in self.cases:
            for passage in case.relevant:
                text = page_text.get((passage.document_id, passage.page_number))
                if text is None:
                    raise ValueError(f"{case.id}: relevant page is not in the corpus")
                if passage.span and passage.span.end_offset > len(text):
                    raise ValueError(f"{case.id}: span exceeds page length")
            for fact in case.required_facts:
                texts = [
                    page_text[(page.document_id, page.page_number)].casefold()
                    for page in fact.acceptable_pages
                ]
                if not any(alt.casefold() in text for alt in fact.alternatives for text in texts):
                    raise ValueError(
                        f"{case.id}: no alternative for fact {fact.id} appears on its pages"
                    )

        if self.stage == "baseline":
            self._baseline_rules()
        return self

    def _baseline_rules(self) -> None:
        counts = Counter(case.type for case in self.cases)
        problems = []
        if not BASELINE_MIN_CASES <= len(self.cases) <= BASELINE_MAX_CASES:
            problems.append(f"{BASELINE_MIN_CASES}-{BASELINE_MAX_CASES} cases")
        if counts["unanswerable"] < BASELINE_MIN_UNANSWERABLE:
            problems.append(f"at least {BASELINE_MIN_UNANSWERABLE} unanswerable cases")
        if counts["multi_doc"] < BASELINE_MIN_MULTI_DOC:
            problems.append(f"at least {BASELINE_MIN_MULTI_DOC} multi_doc cases")
        if not all(case.reviewed for case in self.cases):
            problems.append("every case reviewed against its sources")
        if self.retrieval.thresholds is None:
            problems.append("retrieval thresholds")
        if problems:
            raise ValueError("baseline datasets require " + ", ".join(problems))


def _require_unique(scope: str, label: str, values: Sequence[Hashable]) -> None:
    duplicates = sorted(str(value) for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise ValueError(f"{scope}: duplicate {label}: {', '.join(duplicates)}")


def load_dataset(path: Path = DEFAULT_DATASET) -> Dataset:
    return Dataset.model_validate_json(path.read_text(encoding="utf-8"))
