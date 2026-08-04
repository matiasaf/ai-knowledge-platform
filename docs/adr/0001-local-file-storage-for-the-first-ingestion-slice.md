# 1. Local file storage for the first ingestion slice

- Status: accepted
- Date: 2026-08-04

## Context

The first vertical slice accepts a PDF upload and reports what was stored. It has one
consumer (the web app), one writer (the upload endpoint), and no reader beyond the
response it just produced. There are no queries, no listing, no filtering, no
concurrent writers competing for the same row, and no relationships between records.

The obvious "serious" choice is PostgreSQL behind a repository interface. Both would
be defensible later. Neither is justified by anything this slice actually does.

## Decision

Store the accepted PDF and a JSON metadata sidecar side by side under a configurable,
Git-ignored data directory, named by the document's UUID. Call `store_document`
directly from the route handler. Do not introduce a repository interface, an ORM, a
migration tool or a database container yet.

Writes are made durable in the ordinary sense of the word rather than transactionally:
the upload streams to a `.part` file, is renamed into place only after it validates,
and every artifact is removed if any later step fails.

## Consequences

What this buys:

- The persistence rules are readable in one file, with no indirection to follow.
- The test suite runs against real filesystem behaviour in a temporary directory,
  with no service to start and no fixtures to reset.
- Contributors can clone and run the project with two commands.
- The database schema gets designed when there is real data to model — chunks, pages,
  embeddings and evaluation runs — rather than guessed at now and migrated later.

What it costs, stated plainly:

- There is no way to list or query documents; the API cannot offer that endpoint yet.
- Two concurrent uploads of the same bytes produce two independent documents. There is
  no deduplication and no uniqueness constraint.
- Metadata and content can diverge if the process is killed between the rename and the
  sidecar write. The window is small and the recovery is to delete the orphan PDF, but
  it is a real gap that a transactional store would close.
- The data directory is local to one machine. Nothing here survives a container
  restart on ephemeral storage.

## When this gets revisited

When any of the following becomes true:

- documents must be listed, searched or filtered;
- ingestion produces derived records (pages, chunks, embeddings) that must stay
  consistent with their parent document;
- more than one process writes to the same store.

The first of those arrives with text extraction, so this decision is expected to be
short-lived. It is recorded so the replacement is a deliberate step rather than a
correction.
