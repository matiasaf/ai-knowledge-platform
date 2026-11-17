# 6. In-process request tracing with append-only JSONL records

- Status: accepted
- Date: 2026-11-16
- Roadmap: deliverable 2 (observability and experiment) in [ROADMAP.md](../../ROADMAP.md)

## Context

The roadmap needs per-request latency by stage, token usage, cost per query and recent
spend, measured on real runs, plus one experiment and one optimization whose effect is
shown with before/after numbers. Today the API records nothing: there is no request
identifier, no stage timing and no record of which model snapshot answered.

The service is a single local FastAPI process with no queue, no streaming and no
deployed environment. `knowledge.db` is a derived index that may be deleted and rebuilt
at any time (ADR 4), so it cannot hold history that must survive a rebuild. Questions
and evidence text can be private user content.

Options considered:

1. **OpenTelemetry SDK with an exporter and a collector or hosted backend.** Standard
   and portable, but it adds dependencies, a second service or an external account, and
   sends request data off the machine before there is an accepted deployment.
2. **Hosted LLM observability tool.** Fast dashboards, but the same data-egress problem,
   a vendor dependency and spend outside the project's budget.
3. **Custom in-process instrumentation writing local records.** Few lines of standard
   library code, no new service and full control over what is stored; the metrics
   analysis has to be written by hand.

## Decision

Use option 3.

- A pure ASGI middleware assigns every request a `request_id`. A client-supplied
  `X-Request-ID` is reused only when it matches `[A-Za-z0-9._-]{1,64}`; otherwise a new
  UUID4 hex value is generated. The ID is returned in the `X-Request-ID` response header
  and exposed through CORS.
- The active trace lives in a `contextvars.ContextVar`, so services and adapters add
  spans without passing a tracer through every signature. The tracing module uses only
  the standard library and stays importable by domain-adjacent code.
- Spans exist only for stages that actually run: `retrieval` (k, document filter, match
  count, retrieved chunk positions) and `generation` (prompt version, evidence count,
  provider model/snapshot, input and output tokens, outcome). A span records duration,
  `ok` or `error`, and the exception class on failure. There is no streaming, so time to
  first token is not applicable.
- On response completion the trace is written as one JSON line to
  `<data_dir>/traces/traces-YYYY-MM-DD.jsonl` (UTC date). The record holds the request
  ID, method, route template, HTTP status, total duration and spans. Writes are appended
  under a process lock off the event loop. A failed write is logged and never changes
  the HTTP response.
- Records never store question text, evidence text, claims, API keys or headers. They
  store identifiers, counts, durations, model names and token counts only.
- The prompt has an explicit `PROMPT_VERSION`. A test pins the hash of the instructions
  to that version so the instructions cannot change without a version bump.
- Tracing can be disabled with `AKP_TRACING_ENABLED=false`; the `X-Request-ID` header is
  still returned.

Trace files are operational history, not a source of truth for documents and not part
of the rebuildable index. Retention target: 30 days of daily files. Deletion is a
manual or scripted file removal; it is not automated in this slice.

## Consequences

- Latency percentiles, token totals and cost are computed by reading JSONL files. A
  metrics script and versioned per-model prices are the next slice (roadmap session 5)
  and are not part of this decision.
- Single-process, single-host only. Multiple API workers append to the same daily file;
  each record is written with one `write` call under a per-process lock, which keeps
  lines intact for the small records involved but is not a cross-process guarantee.
  A multi-worker or multi-host deployment needs a new decision.
- Trace files are not suitable for enforcing a spend cap. Budget reservation before
  provider calls (roadmap deliverable 3) needs an atomic store and its own decision.
- If the project later adopts OpenTelemetry, span names and attributes map directly;
  the middleware and `span()` helper are the only places to replace.
