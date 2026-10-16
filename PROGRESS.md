# Current project progress

Last updated: 2026-08-21

This is the resumable state for active work. Detailed completed-slice records live in
`docs/progress/`; plans and architectural rationale live in `docs/plans/` and
`docs/adr/`.

## Done

- Milestones 1–3 are complete: validated PDF ingestion, page-level extraction and
  measured lexical retrieval.
- Milestone 4 is implemented: grounded answers, server-resolved citations, explicit
  non-answer states and a versioned answer-quality dataset.
- Provider-independent backend and frontend quality gates pass according to
  `docs/progress/day-04.md`.
- The repository harness now has a root agent map, resumable state, a documentation
  index, declared runtime families and matching local/CI offline evaluation gates.

## In progress

- Milestone 4 live acceptance.

## Blocked

- Live model comparison, model/snapshot selection, answer-quality metrics and the live
  answered browser flow require `AKP_OPENAI_API_KEY` and `AKP_OPENAI_MODEL`.

## Next action

Configure provider credentials outside the repository, compare candidate models with
`make eval-answers`, record the selected model and metrics, then exercise one real
answered browser flow before marking milestone 4 accepted.

After acceptance, follow `docs/plans/roadmap.md` (currently week 1 of 24): the next
slice is `retrieval_v2`, a larger retrieval dataset that replaces the saturated
baseline before any embedding work. Milestone 5 (observability and feedback) moves to
weeks 9–12.

## Resume checklist

- Read `AGENTS.md` and the relevant plan/ADRs.
- Check `git status --short` before editing.
- Confirm the environment with `make doctor`.
- Run `make check` before claiming full local verification.
- Update this file when the active state, blocker, next action or evidence changes.

## Latest harness verification

On 2026-08-21, `make check-api` passed (Ruff, formatting, strict mypy, 49 tests,
retrieval thresholds and validation of 13 answer cases). Web lint, type-check, 40 tests
and production build passed; `npm audit --audit-level=high` reported zero
vulnerabilities. The local web checks used Node.js 24 while `.nvmrc` and CI select
Node.js 22, so CI remains the exact target-runtime confirmation.
