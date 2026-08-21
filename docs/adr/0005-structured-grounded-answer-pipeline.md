# 5. Structured grounded-answer pipeline behind a provider port

- Status: accepted
- Date: 2026-08-21

## Context

Milestone 3 can retrieve page-bounded evidence with exact document, page, chunk and
offset provenance. Milestone 4 must turn that evidence into useful answers without
allowing fluent model output to manufacture or weaken attribution.

A free-form answer with citation markers would require parsing text written by the
model. Letting the client submit context would make the evidence boundary untrustworthy.
Generating first and finding citations afterward would be post-hoc attribution rather
than grounding.

The application is still local and single-user. It has no identity, conversation
history, background jobs or need to persist generated content.

## Decision

Expose one synchronous `POST /answers` use case. The server retrieves up to five
existing FTS matches, assigns request-local evidence IDs and sends only the question
and those passages to an `AnswerGenerator` port.

The first adapter uses the OpenAI Responses API with Structured Outputs. The provider
returns an outcome plus atomic claims referencing only evidence IDs. The application
resolves those IDs against the original `RetrievalMatch` objects and creates all
document, page, chunk, offset and source-path metadata itself.

An answered result is valid only if it has one to five unique claims and every claim
has one to three resolvable evidence references. A non-answer has no claims or
citations. Invalid provider output fails the whole request; it is never partially
rendered.

No retrieval matches returns `insufficient_evidence` without a provider request.
Relevant-looking matches may still be rejected by the generator. Provider safety
refusals remain a separate `safety_refused` outcome. Configuration, timeout, connection
and invalid-output failures remain technical errors.

The adapter sends `store=false`, uses no tools or conversation state and is configured
only on the server. The API can start without a key; only `/answers` returns
`generation_not_configured`. Responses are not streamed or persisted.

The exact model is not fixed by this ADR. It must be selected through the versioned
answer evaluation and recorded with its snapshot and results.

## Consequences

- Citations cannot reference a document or page the server did not retrieve.
- Provider and HTTP types do not enter the answer domain.
- Unit and contract tests run without network or paid requests.
- Ingestion and retrieval remain available when generation is not configured.
- Complete structured output must arrive before the UI shows any claim, increasing
  perceived latency relative to streaming.
- Questions and retrieved passages leave the local machine during generation even
  though the complete PDF does not.
- `store=false` minimizes provider application state but is not a promise of zero
  retention; organization controls and provider policies still apply.
- Answer history, retry jobs and feedback require future persistence decisions.

## When this gets revisited

Revisit streaming only if a buffered design preserves atomic validation. Revisit
provider selection when another adapter has a measured quality, privacy or operational
advantage. Revisit persistence only together with identity, retention and deletion
requirements. Revisit the evidence limit or retrieval strategy only through both
retrieval and answer evaluations.
