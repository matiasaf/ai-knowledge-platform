# Day 3 — Page-bounded retrieval with a measured baseline

Date: 2026-08-13

## Goal

Turn extracted pages into searchable evidence without losing provenance, expose ranked
passages rather than fabricated answers, and establish a reproducible quality baseline
before adding any model call.

## Completed

Backend

- Added `POST /documents/{id}/index` with persisted
  `extracted → indexing → indexed | indexing_failed` transitions and idempotent success.
- Added deterministic character-window chunking. Chunks never cross page boundaries,
  overlap at word boundaries and retain exact source start/end offsets.
- Added a versioned SQLite database with relational document/chunk records and an
  external-content FTS5 index synchronized by triggers.
- Added `POST /retrieval/search` for global or document-scoped lexical retrieval. User
  prose is compiled to quoted tokens, not interpreted as raw FTS syntax.
- Runs blocking SQLite work outside the async event loop and returns stable errors for
  invalid state, duplicate active indexing and invalid search text.

Frontend

- Upload now flows through storage, page extraction and evidence indexing as distinct
  states, each backed by real server work.
- The indexed result reports page, empty-page and chunk counts while retaining the page
  preview from extraction.
- Extraction and indexing failures have separate retry paths and never require a
  successful earlier step to be repeated.
- Added a standalone evidence search that survives page reloads through the persistent
  local index. Results show rank, filename, page, exact excerpt, document ID and chunk.
- Empty search results explicitly report a retrieval miss and do not infer an answer.

Evaluation

- Added `evals/retrieval_v1.json`, a versioned two-document, four-query policy set.
- Added a runner reporting Recall@3 and MRR@3, with thresholds enforced by exit status.
- The current deterministic baseline scores `Recall@3 = 1.0` and `MRR@3 = 1.0`.
- `make eval-retrieval`, `make check` and CI all run the same evaluation.

## Verified

- Backend lint, formatting and strict type checking pass; 26 pytest cases pass.
- Frontend lint and type checking pass; 30 Vitest cases pass.
- Production build and dependency audit pass.
- A live browser flow covers upload, extraction, indexing and retrieval against the real
  local services with no console errors.

## Next action

Add grounded answer generation over retrieved chunks. The API must refuse unsupported
answers, return document/page citations that map to the retrieved evidence, and evaluate
faithfulness separately from retrieval quality. Authentication, deployment and broad
observability remain later milestones.
