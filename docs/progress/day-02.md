# Day 2 — Page-level text extraction with honest provenance

Date: 2026-08-12

## Goal

Take an already-stored PDF through bounded text extraction while preserving the page
number of every span and keeping empty pages visible. Expose the same real states and
failure boundaries through the API and browser.

## Completed

Backend

- Added `POST /documents/{id}/extraction` as an idempotent operation after success.
- Added `stored → processing → extracted | extraction_failed` transitions; interrupted
  persisted `processing` work can be retried after a process restart.
- Runs pypdf in a worker thread, with a configurable 250-page default limit checked
  before any page result is persisted.
- Persists an ordered, versioned extraction sidecar atomically. Every span carries a
  one-based page number; textless pages are stored with an empty string.
- Returns explicit error codes for missing documents, duplicate active work, encrypted
  PDFs, page-limit violations and parser failures.
- Keeps the original PDF on every extraction failure and removes incomplete derived
  data.

Frontend

- Upload success now flows into a distinct page-extraction phase with a polite live
  announcement and the form locked for the duration.
- The result shows document metadata, page and empty-page counts, and page-labelled
  previews for the first three pages.
- Extraction errors distinguish an accepted upload from failed parsing and offer a
  retry without uploading the source again.
- API payloads are shape-checked down to sequential page numbers and character counts.

Repository

- Added pypdf to the locked backend dependency set.
- Updated configuration examples, status vocabulary, architecture documentation and
  the roadmap.
- Recorded the one-milestone decision to keep atomic sidecars in ADR 3.

## Verified

- Backend lint, formatting and strict type checking pass; 17 pytest cases pass.
- Frontend lint and type checking pass; 19 Vitest cases pass.
- Production build and dependency audit pass.
- A live local smoke test covers health, upload and extraction against the real API.

## Next action

Define chunks that retain document and page provenance, then build a small fixed query
set and measure retrieval before adding answer generation. The storage decision must be
revisited as part of that work because chunk relationships and evaluation runs are
query-shaped data.
