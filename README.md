# AI Knowledge Platform

Ingest trusted documents, ask questions about them, get grounded answers with
verifiable citations, and observe retrieval quality, latency, failures and cost.

**Status: milestone 1 of an in-progress project.** Document ingestion works end to
end — upload, validation, storage and honest state reporting. Retrieval, answers and
citations are not built yet, and nothing in this repository pretends otherwise. The
[roadmap](#roadmap) says what comes next; [`docs/progress`](docs/progress) records what
each milestone actually delivered.

## The problem

Teams keep their real knowledge in documents: policies, contracts, runbooks, research.
When someone asks a question, an answer is only useful if the reader can check it
against the source. Most internal assistants fail on exactly that: the answer sounds
plausible, the source is unclear, and nobody can tell whether the system retrieved the
right passage or invented a confident sentence.

The target user is a team that already has trusted documents and needs answers they can
defend.

## Why this is not another chatbot demo

A chat window in front of a model is a weekend project. The engineering is everywhere
else, and that is what this repository is being built to show:

- **Evidence before fluency.** Every answer will be traceable to a page in a specific
  document. A retrieval failure must be visible as a failure, not smoothed over.
- **States that mean something.** The API reports `stored` after an upload, not
  `processing` or `ready`, because nothing parses or indexes the file yet. See
  [ADR 2](docs/adr/0002-document-status-vocabulary.md).
- **Measurable quality.** Retrieval and answer evaluations are planned as reproducible
  runs, not as vibes on a demo query.
- **Observable operation.** Latency, tokens, cost and failure rates are product
  surfaces, not afterthoughts.
- **Deliberate scope.** Each milestone is a thin vertical slice that runs, is tested
  and is documented, rather than scaffolding for features that do not exist.

## What works today

Backend

- `GET /health`.
- `POST /documents` (`multipart/form-data`) that accepts PDFs only.
- Two-layer validation: the declared media type **and** the `%PDF-` file signature, so
  a `.txt` renamed to `.pdf` is rejected.
- A configurable size limit (10 MB by default) enforced while the request streams in
  64 KiB chunks, so an oversized upload is refused without being read into memory.
- Storage that writes to a temporary `.part` file and renames it into place only after
  the whole payload validates; every artifact is removed if any step fails, so no
  partial document is ever left behind.
- A UUID generated once per accepted document; the client-supplied filename is stored
  as metadata and never used as a path.
- A JSON metadata sidecar per document.
- One error envelope for every failure, including framework validation errors, with
  stable machine-readable codes.
- CORS limited to the configured frontend origin.

Frontend

- A single-purpose product shell with an accessible upload form, wired to the real API.
- An explicit `idle | uploading | stored | error` state machine — no state is rendered
  that the backend cannot actually reach.
- Accepted documents display filename, size and document ID.
- Failures render through `role="alert"`; progress announces through a polite live
  region; focus moves to the result only on success, so a failure leaves the caret on
  the form. The submit button uses `aria-disabled` rather than `disabled`, because
  disabling the focused element drops focus to the document body mid-upload.
- API responses are shape-checked before rendering; an unexpected payload falls back to
  our own copy rather than leaking through the UI.

## Not implemented yet

Listed so the scope of this repository is not overstated. None of the following exists
in any form here:

PDF text extraction · OCR · chunking · embeddings · vector search · pgvector · any LLM
call · question answering · citations · retrieval or answer evaluation · latency, token
and cost observability · feedback capture · guardrails · authentication ·
multi-tenancy · PostgreSQL · Docker Compose · background workers or queues · cloud
infrastructure · a design system · non-PDF file types · document listing endpoints.

## Architecture

```
Browser ──────────────► Next.js App Router (apps/web)
                          │  client-side FormData upload
                          ▼
                        FastAPI (services/api)
                          │  media type + %PDF- signature + size, checked while streaming
                          ▼
                        Local data directory
                          {uuid}.pdf   the unmodified upload
                          {uuid}.json  its metadata sidecar
```

The API is a single process with no database, no queue and no external service. The
web app is a static-rendered shell whose only dynamic part is the client component that
performs the upload.

Inside the API, the request path is deliberately short: the route handler validates the
declared media type, then `store_document` streams, validates and persists. The domain
`Document` is a frozen dataclass, separate from the Pydantic response schema, so the
wire format can change without touching ingestion rules.

There is no repository interface and no ORM. That is a decision, not an omission —
[ADR 1](docs/adr/0001-local-file-storage-for-the-first-ingestion-slice.md) records why,
including what it costs.

## Repository structure

```
.
├── apps/web/                  Next.js 16 App Router frontend
│   ├── app/                   layout, page and the upload form client component
│   ├── lib/api.ts             typed API client; failures returned as values
│   └── *.test.ts(x)           Vitest suites colocated with what they cover
├── services/api/              FastAPI backend
│   ├── src/ai_knowledge_platform/
│   │   ├── config.py          typed settings
│   │   ├── errors.py          error envelope and stable error codes
│   │   ├── health.py          GET /health
│   │   ├── main.py            application factory
│   │   └── documents/         domain model, schemas, storage, router
│   └── tests/                 pytest suite, temporary data directories only
├── docs/adr/                  architecture decision records
├── docs/progress/             what each milestone actually delivered
├── .github/workflows/ci.yml   separate backend and frontend jobs
└── Makefile                   the same gates CI runs
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — installs and pins Python 3.12+ for you.
- Node.js 22 or newer, with npm.
- `make` is optional; every command below is shown in its raw form too.

## Quickstart

Clone the repository, then from the repository root:

```bash
make install     # uv sync in services/api, npm ci in apps/web
```

Run the two processes in separate terminals:

```bash
make api         # http://localhost:8000  (docs at /docs)
make web         # http://localhost:3000
```

Without `make`, from the repository root:

```bash
cd services/api && uv sync && uv run uvicorn ai_knowledge_platform.main:app --reload --port 8000
cd apps/web     && npm ci  && npm run dev
```

Open <http://localhost:3000> and upload a PDF. Accepted files appear under
`services/api/data/documents/`, which is Git-ignored.

Defaults work with no configuration. Copy the environment examples only if you need to
change them:

```bash
cp services/api/.env.example services/api/.env
cp apps/web/.env.example     apps/web/.env.local
```

## Configuration

Backend (`services/api/.env`, all optional):

| Variable                   | Default                 | Purpose                                                              |
| -------------------------- | ----------------------- | -------------------------------------------------------------------- |
| `AKP_DATA_DIR`             | `data`                  | Where documents and sidecars are written. Relative paths resolve against `services/api`, never the shell's working directory. |
| `AKP_MAX_UPLOAD_BYTES`     | `10485760` (10 MB)      | Maximum accepted upload size. Must be positive.                       |
| `AKP_CORS_ALLOW_ORIGINS`   | `http://localhost:3000` | Comma-separated list of browser origins allowed to call the API.      |

Frontend (`apps/web/.env.local`, optional):

| Variable                   | Default                 | Purpose                                                              |
| -------------------------- | ----------------------- | -------------------------------------------------------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | API origin used by the browser. Must keep the `NEXT_PUBLIC_` prefix.  |

No secrets are required to run this project, and none are stored in it.

## Verification

`make check` runs everything CI runs. Individually, from the repository root:

```bash
cd services/api && uv run ruff check .          # lint
cd services/api && uv run ruff format --check . # formatting
cd services/api && uv run mypy                  # strict type checking
cd services/api && uv run pytest                # tests

cd apps/web && npm run lint       # Biome lint and format check
cd apps/web && npm run typecheck  # tsc --noEmit
cd apps/web && npm run test       # Vitest + Testing Library
cd apps/web && npm run build      # production build
cd apps/web && npm audit          # dependency audit
```

The backend suite covers the health endpoint, a successful upload, rejection by
declared media type, rejection of content that only claims to be a PDF, rejection above
the size limit, the absence of leftover files after any rejection, consistency between
the stored PDF, its sidecar and the API response, and that framework-raised failures
(unknown route, wrong method, missing form field) use the same error envelope as
application errors. Tests run against temporary directories and never write into the
project's data directory.

The frontend suite covers the upload state machine at two boundaries. The component
tests drive `idle → uploading → stored` and `idle → uploading → error` with the API
client mocked, including the in-flight state held open by a hand-resolved promise, the
refusal to start a second request while one is open, focus moving to the result only on
success, and the field being cleared for the next upload. The API client tests run
against a mocked `fetch` and pin the behaviour that is easy to regress: snake_case to
camelCase mapping, that `FormData` is posted with no hand-written `Content-Type`
header, and that a payload which is not the documented envelope falls back to our own
copy instead of rendering whatever the server returned.

## Roadmap

| Milestone | Scope                                                                        | State       |
| --------- | ---------------------------------------------------------------------------- | ----------- |
| 1         | Repository foundation, validated PDF upload, honest ingestion states          | Done        |
| 2         | PDF text extraction with page-level provenance                                | Next        |
| 3         | Chunking and retrieval, with evaluation before any generation                 | Planned     |
| 4         | Grounded answers with verifiable citations                                    | Planned     |
| 5         | Latency, token, cost and failure observability; feedback capture              | Planned     |

Milestone 2 is deliberately narrow: text per page, provenance attached to every
extracted span, and explicit handling of encrypted PDFs and pages with no text layer.
Embeddings and model calls come after provenance is trustworthy, not before.

## Decision records

- [ADR 1 — Local file storage for the first ingestion slice](docs/adr/0001-local-file-storage-for-the-first-ingestion-slice.md)
- [ADR 2 — The status vocabulary only names states that exist](docs/adr/0002-document-status-vocabulary.md)

## Project status

This is an active portfolio project, built in public in small vertical slices. It is
not a product and is not deployed anywhere. Milestone 1 is complete and verified
locally; everything described under "Not implemented yet" is genuinely absent.
