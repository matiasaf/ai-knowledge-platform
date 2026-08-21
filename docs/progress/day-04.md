# Day 4 — Grounded answers with server-resolved citations

Date: 2026-08-21

## Goal

Generate answers only from retrieved chunks, make every accepted claim traceable to the
stored PDF, distinguish honest non-answers from technical failures and establish a
versioned answer-quality policy.

## Implemented

Backend

- Added `POST /answers` with global or document-scoped retrieval owned by the server.
- Added immutable answer-domain types and pure citation resolution.
- Added `answered`, `insufficient_evidence` and `safety_refused` outcomes.
- Rejects unknown evidence IDs, uncited claims, duplicate claims and contradictory
  outcomes before returning any generated text.
- Added an `AnswerGenerator` protocol and an async OpenAI Responses API adapter using
  Pydantic Structured Outputs, `store=false`, no tools, one retry and bounded output.
- Added stable configuration, timeout, provider and invalid-response errors.
- Keeps upload, extraction, indexing and retrieval available without an API key.
- Added `GET /documents/{id}/content` with inline PDF delivery for source verification.

Frontend

- Added an accessible grounded-question form with pending, answered,
  insufficient-evidence, safety-refusal and error states.
- Renders claims with resolvable citation markers and source cards.
- Opens the stored PDF with a page fragment while retaining page metadata as fallback.
- Runtime-validates outcome invariants, citation references, offsets and source paths
  before rendering.
- Retains the retrieval-only panel as a diagnostic surface.

Evaluation

- Added `evals/answers_v1.json` with 13 English/Spanish cases.
- Covers answerable, unanswerable, multi-evidence, lexical false-friend and adversarial
  document cases.
- Added a live runner for outcome accuracy, rejection accuracy, citation validity,
  citation completeness, citation-page correctness, required-fact coverage and
  forbidden-fact rate.
- Dataset policy validation runs in `make check`; the paid live evaluation remains
  explicit through `make eval-answers`.

## Verified without provider credentials

- Backend lint, formatting and strict type checking pass; 49 pytest cases pass.
- Frontend lint and type checking pass; 40 Vitest cases pass.
- Frontend production build passes.
- The answer dataset validates: 2 documents and 13 cases.
- Retrieval evaluation remains a separate quality gate.
- SDK adapter tests verify structured parsing, `store=false`, absence of tools,
  refusals and missing output without making network calls.

## Acceptance still pending

`AKP_OPENAI_API_KEY` was not available in the implementation environment. Therefore these
items are deliberately not claimed:

- comparison of two current models;
- selection and pinning of a production model/snapshot;
- live answer-evaluation metrics;
- live browser verification of an answered response.

The application exposes this honestly as `generation_not_configured`; no fallback
fabricates an answer. Configure `AKP_OPENAI_API_KEY` and `AKP_OPENAI_MODEL`, then run
`make eval-answers` and the browser acceptance flow before marking milestone 4 done.
