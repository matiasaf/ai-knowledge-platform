# 3. Keep page extraction in atomic sidecars for one more milestone

- Status: accepted
- Date: 2026-08-12

## Context

ADR 1 expected local sidecars to be revisited as soon as ingestion produced derived
records. Page extraction now produces exactly that: an ordered set of text spans tied
to a document and a page number.

Moving to PostgreSQL is defensible, but this milestone still has one writer, one reader
immediately after the write, no listing or filtering, and no relationships beyond the
parent document ID. A database, migrations and a container would expand the local
runtime without answering a query the product can issue today.

## Decision

Keep the original PDF and metadata sidecar, and persist one additional
`{uuid}.extraction.json` artifact with a versioned shape. It contains the document ID,
extraction timestamp and an ordered page array. Every page is present, including pages
whose extracted text is empty, and every text span carries a one-based page number.

Write JSON through a sibling `.part` file and rename only after the full payload is
serialized. Update document metadata in the same atomic-file manner. Extraction is
idempotent once complete; failed attempts remove incomplete derived artifacts and keep
the original PDF.

## Consequences

- The whole local system still starts with `make api` and `make web`; no database or
  container is required.
- Page provenance is visible and testable in the persisted artifact rather than held
  only in memory.
- PDF, metadata and extraction are three independent atomic files, not one transaction.
  A process kill between renames can leave a recoverable inconsistency.
- Listing, filtering, chunk relationships and retrieval evaluation runs would be
  awkward and inefficient in sidecars.

## When this gets replaced

Milestone 3 introduces chunks and query-shaped retrieval data. Before that milestone
is considered complete, choose a store that can query documents and chunks, preserve
their provenance relationships, and support reproducible evaluation runs. This ADR is
an explicit one-milestone extension, not a general endorsement of JSON as a database.
