# 2. The status vocabulary only names states that exist

- Status: accepted
- Date: 2026-08-04

## Context

Document ingestion UIs conventionally show `uploading → processing → ready`. It is
tempting to ship that vocabulary immediately, because it looks like the finished
product and costs nothing to render.

Nothing in this build parses, chunks or indexes a PDF. A `processing` state would be a
label with no work behind it, and `ready` would tell a user the document can be
questioned when it cannot.

## Decision

`DocumentStatus` has exactly one member, `stored`. The API returns it, the UI renders
it, and the copy next to it says the file is saved and has not been parsed. New
members are added in the same change that implements the work they describe.

The same rule applies to the UI: its state machine is `idle | uploading | stored |
error`, where `uploading` describes the in-flight HTTP request rather than any
server-side pipeline.

## Consequences

- A single-member enum looks odd out of context, so the reason lives in its docstring.
- Screenshots of this milestone show less than a mockup would. That is the point: what
  is on screen is what runs.
- Adding `processing` and `ready` later is an additive API change. Clients that switch
  on status will need to handle them, which is why the codes are documented as part of
  the public contract from the start.
