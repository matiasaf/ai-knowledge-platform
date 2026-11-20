"""Offline schema v2 evaluation.

    python -m ai_knowledge_platform.evaluation [DATASET] [--validate-only] [--output-dir DIR]

Exit codes: 0 passed or no thresholds set, 1 thresholds failed or a case errored,
2 invalid dataset. Live answer evaluation and judging are not part of this command yet.
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from ai_knowledge_platform.evaluation.dataset import DEFAULT_DATASET, SERVICE_ROOT, load_dataset
from ai_knowledge_platform.evaluation.report import (
    RunMetadata,
    build_report,
    file_sha256,
    git_state,
    new_run_id,
    render_markdown,
    write_report,
)
from ai_knowledge_platform.evaluation.retrieval import evaluate_retrieval

DEFAULT_OUTPUT_DIR = SERVICE_ROOT / "evals" / "results"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline v2 evaluation")
    parser.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--validate-only", action="store_true", help="Check the contract only")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    arguments = parser.parse_args(argv)
    dataset_path: Path = arguments.dataset.resolve()

    try:
        dataset = load_dataset(dataset_path)
    except ValidationError as exc:
        sys.stderr.write(f"Invalid dataset {dataset_path}:\n{exc}\n")
        return 2

    counts = {kind: sum(c.type == kind for c in dataset.cases) for kind in _CASE_TYPES}
    summary = ", ".join(f"{count} {kind}" for kind, count in counts.items())
    sys.stdout.write(f"Validated {dataset.name} ({dataset.stage}): {summary}.\n")
    if arguments.validate_only:
        return 0

    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    retrieval = evaluate_retrieval(dataset)
    metadata = RunMetadata(
        run_id=new_run_id(started_at, dataset.name),
        mode="offline",
        started_at=started_at,
        duration_seconds=round(time.perf_counter() - clock, 3),
        git=git_state(SERVICE_ROOT),
        dataset_name=dataset.name,
        dataset_stage=dataset.stage,
        dataset_path=_display_path(dataset_path),
        dataset_sha256=file_sha256(dataset_path),
        model=None,
    )
    markdown = render_markdown(metadata, dataset, retrieval)
    json_path, markdown_path = write_report(
        arguments.output_dir, build_report(metadata, dataset, retrieval), markdown
    )
    sys.stdout.write(markdown)
    sys.stdout.write(f"\nWrote {_display_path(json_path)} and {_display_path(markdown_path)}\n")
    return 1 if retrieval.threshold_status == "failed" else 0


_CASE_TYPES = ("factual", "multi_doc", "unanswerable")


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        str(resolved.relative_to(SERVICE_ROOT))
        if resolved.is_relative_to(SERVICE_ROOT)
        else str(resolved)
    )


if __name__ == "__main__":
    raise SystemExit(main())
