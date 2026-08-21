# 2. The status vocabulary only names states that exist

- Status: accepted
- Date: 2026-08-04
- Last updated: 2026-08-13

## Context

Document ingestion UIs conventionally show `uploading → processing → ready`. It is
tempting to ship that vocabulary immediately, because it looks like the finished
product and costs nothing to render.

At milestone 1 nothing parsed, chunked or indexed a PDF. A `processing` state would
have been a label with no work behind it, and `ready` would have told a user the
document could be questioned when it could not.

## Decision

At milestone 1, `DocumentStatus` had exactly one member: `stored`. New members are
added only in the same change that implements the work they describe.

Milestone 2 adds `processing`, `extracted` and `extraction_failed`. `processing` is
persisted before the PDF parser starts, `extracted` only after the complete page set is
atomically stored, and `extraction_failed` preserves a retryable distinction from a
plain upload. `ready` remains absent because extracted text is not chunked, indexed or
queryable.

Milestone 3 adds `indexing`, `indexed` and `indexing_failed`. `indexed` means page-
bounded chunks are committed to the local retrieval database and can be searched. It
does not by itself mean the system can formulate or validate an answer.

Milestone 4 deliberately keeps `indexed` as the terminal document state. Answer
availability is a runtime capability combining an indexed corpus with provider
configuration and availability; it is not durable work performed on one document.
Adding `ready` would become false whenever a key expires or a provider is unavailable
without any transition in the document itself. `POST /answers` therefore reports
configuration and provider failures independently.

The UI mirrors those boundaries: browser upload progress is distinct from server-side
page extraction and indexing, while either failure still shows the work that completed
before it.

## Consequences

- Clients that switch on status must handle additive members; the frontend validates
  the entire documented vocabulary before rendering.
- A process killed mid-extraction can leave persisted metadata at `processing`. A new
  process treats that as interrupted work and permits an explicit retry.
- Screenshots still show less than a finished product mockup. That is the point: what
  is on screen is what runs.
- `ready` remains reserved for a future durable state with a precise invariant. It is
  not an alias for “indexed while an external service happens to be reachable.”
