# Current project progress

Last updated: 2026-10-30

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

Production preparation (`ROADMAP.md`, execution window 9–22 November):

- Done: `docs/architecture/ingestion-flow.md` and `docs/architecture/backend-boundaries.md`
  with sequence and state diagrams. The backend import rules are now enforced by
  `services/api/tests/test_architecture_boundaries.py`.
- Pending: milestone 4 live acceptance (blocked, see below).
- Consolidated study and implementation next steps in `ROADMAP.md`: current-stack
  diagnosis, dependencies, eight November sessions, acceptance evidence and the
  deferred long-term learning/implementation sequence. The two former planning
  documents were removed; their content lives in `ROADMAP.md` and git history.
- Dataset v2, judge calibration, tracing decisions and deployment remain pending.
  Corpus provenance and history review are not certified by this documentation work.

## Blocked

- Live model comparison, model/snapshot selection, answer-quality metrics and the live
  answered browser flow require `AKP_OPENAI_API_KEY` and `AKP_OPENAI_MODEL`.

## Next action

Confirm a publishable corpus and record the history/provenance review, then define
and validate the v2 dataset/report contract using the existing Python harness.
Draft the first 20 questions and grow to 30–40 with at least five unanswerable cases
before comparing retrieval changes. See the next-action checklist and deliverable contracts in `ROADMAP.md`.

In parallel with offline preparation, the project owner can configure provider
credentials outside the repository and a live-evaluation budget. Then compare models
with `make eval-answers`, record model/snapshot and metrics, and exercise a real
answered browser flow. Live acceptance remains required before claiming milestone 4
accepted or the combined evaluation delivered. The 12 November checkpoint cuts deploy
scope if evaluation is incomplete; the hard cutoff is 22 November.

## Resume checklist

- Read `AGENTS.md` and the relevant plan/ADRs.
- Check `git status --short` before editing.
- Confirm the environment with `make doctor`.
- Run `make check` before claiming full local verification.
- Update this file when the active state, blocker, next action or evidence changes.

## Latest verification

On 2026-10-30, documentation-only consolidation of study and implementation plans:

- `git diff --check` passed. Local Markdown file links in changed documents were
  checked and resolved. `ROADMAP.md` was translated to English and the two former
  planning pointer files were removed.
- `make check` and live evaluations were not rerun: this slice changes documentation
  only and makes no new application-quality or live-acceptance claims.

Earlier roadmap preparation on the same date:

- `make doctor` passed: shell Python 3.13.14, Node 24.22.1; declared runtime targets
  remain Python 3.12 and Node 22.
- `make eval-retrieval` passed: 4 cases, Recall@3 = 1.0, MRR@3 = 1.0. This is the
  existing saturated baseline, not a new quality improvement.
- `cd services/api && uv run python -m ai_knowledge_platform.answers.evaluation --validate-only`
  passed: 2 documents, 13 cases. No live provider calls or judge calibration ran.

## Previous API verification

On 2026-10-16, `make check-api` passed: Ruff, formatting, strict mypy (42 files), 58
tests including the new architecture boundary tests, retrieval thresholds and
validation of 13 answer cases. Web checks were not rerun because no web code changed.

## Previous harness verification

On 2026-08-21, `make check-api` passed (Ruff, formatting, strict mypy, 49 tests,
retrieval thresholds and validation of 13 answer cases). Web lint, type-check, 40 tests
and production build passed; `npm audit --audit-level=high` reported zero
vulnerabilities. The local web checks used Node.js 24 while `.nvmrc` and CI select
Node.js 22, so CI remains the exact target-runtime confirmation.
