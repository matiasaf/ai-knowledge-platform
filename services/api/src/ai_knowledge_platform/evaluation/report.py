"""Run reports: one JSON file for machines and one Markdown summary per run.

Reports carry questions, metrics and provenance of the run (commit, dataset hash,
configuration). They never contain page text, secrets or environment values.
"""

import hashlib
import json
import secrets
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from ai_knowledge_platform.evaluation.dataset import Dataset
from ai_knowledge_platform.evaluation.retrieval import RankingMetrics, RetrievalReport

REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class GitState:
    commit: str | None
    dirty: bool | None


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    mode: Literal["offline"]
    started_at: datetime
    duration_seconds: float
    git: GitState
    dataset_name: str
    dataset_stage: str
    dataset_path: str
    dataset_sha256: str
    model: str | None


def new_run_id(started_at: datetime, dataset_name: str) -> str:
    return f"{started_at:%Y%m%dT%H%M%SZ}-{dataset_name}-{secrets.token_hex(3)}"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_state(cwd: Path) -> GitState:
    """Best effort: a missing git binary or repository yields unknown, not a failure."""
    try:
        commit = _git(cwd, "rev-parse", "HEAD")
        status = _git(cwd, "status", "--porcelain")
    except (OSError, subprocess.CalledProcessError):
        return GitState(commit=None, dirty=None)
    return GitState(commit=commit, dirty=bool(status))


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=10
    )
    return completed.stdout.strip()


def build_report(
    metadata: RunMetadata, dataset: Dataset, retrieval: RetrievalReport
) -> dict[str, object]:
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "run": {
            **asdict(metadata),
            "started_at": metadata.started_at.isoformat(),
        },
        "configuration": dataset.retrieval.model_dump(mode="json"),
        "retrieval": {
            "k": retrieval.k,
            "threshold_status": retrieval.threshold_status,
            "answerable": asdict(retrieval.answerable),
            "by_type": {name: asdict(metrics) for name, metrics in retrieval.by_type.items()},
            "unanswerable": asdict(retrieval.unanswerable),
            "cases": [
                {
                    **asdict(case),
                    "hit": case.hit,
                    "recall": case.recall,
                    "reciprocal_rank": case.reciprocal_rank,
                }
                for case in retrieval.cases
            ],
        },
        "failures": [{"case_id": case.id, "error": case.error} for case in retrieval.failures],
    }


def write_report(output_dir: Path, report: dict[str, object], markdown: str) -> tuple[Path, Path]:
    run = report["run"]
    assert isinstance(run, dict)
    run_id = str(run["run_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{run_id}.json"
    markdown_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown, encoding="utf-8")
    return json_path, markdown_path


def render_markdown(metadata: RunMetadata, dataset: Dataset, retrieval: RetrievalReport) -> str:
    config = dataset.retrieval
    commit = metadata.git.commit[:12] if metadata.git.commit else "unknown"
    if metadata.git.dirty:
        commit += " (uncommitted changes)"
    lines = [
        f"# Evaluation run `{metadata.run_id}`",
        "",
        f"- Mode: {metadata.mode} (no provider calls)",
        f"- Dataset: `{metadata.dataset_name}` ({metadata.dataset_stage}), "
        f"sha256 `{metadata.dataset_sha256[:12]}`",
        f"- Commit: `{commit}`",
        f"- Started: {metadata.started_at.isoformat()} · duration "
        f"{metadata.duration_seconds:.2f} s",
        f"- Retrieval: k={config.k}, chunk {config.chunk_size_chars} chars, "
        f"overlap {config.chunk_overlap_chars}",
        f"- Thresholds: **{retrieval.threshold_status}**",
    ]
    if metadata.dataset_stage == "draft":
        lines.append("- Draft dataset: these numbers are not a baseline.")
    lines += [
        "",
        "## Retrieval",
        "",
        "| Cases | n | Hit rate@k | Recall@k | MRR@k |",
        "|---|---|---|---|---|",
        _ranking_row("All answerable", retrieval.answerable),
        *(_ranking_row(name, metrics) for name, metrics in retrieval.by_type.items()),
        "",
        f"Unanswerable: {retrieval.unanswerable.cases_with_matches} of "
        f"{retrieval.unanswerable.case_count} returned lexical matches "
        f"(rate {retrieval.unanswerable.match_rate:.2f}). Retrieval has no abstention; "
        "refusal is scored by the answer evaluation.",
        "",
        "## Cases",
        "",
        "| Case | Type | Found / relevant | First relevant rank | Retrieved |",
        "|---|---|---|---|---|",
    ]
    for case in retrieval.cases:
        found = (
            "—" if case.type == "unanswerable" else f"{case.relevant_found}/{case.relevant_count}"
        )
        rank = str(case.first_relevant_rank) if case.first_relevant_rank else "—"
        lines.append(f"| `{case.id}` | {case.type} | {found} | {rank} | {case.retrieved_count} |")
    lines += ["", "## Failures", ""]
    if retrieval.failures:
        lines += [f"- `{case.id}`: {case.error}" for case in retrieval.failures]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def _ranking_row(label: str, metrics: RankingMetrics) -> str:
    if not metrics.case_count:
        return f"| {label} | 0 | — | — | — |"
    return (
        f"| {label} | {metrics.case_count} | {metrics.hit_rate_at_k:.3f} | "
        f"{metrics.recall_at_k:.3f} | {metrics.mrr_at_k:.3f} |"
    )
