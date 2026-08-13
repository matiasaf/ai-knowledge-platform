# AI Knowledge Platform

Ingest trusted documents, ask questions about them, get grounded answers with
verifiable citations, and observe retrieval quality, latency, failures and cost.

**Status: milestone 3 of an in-progress project.** Document ingestion, page-level PDF
text extraction and measured lexical retrieval work end to end. Generated answers and
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
- **States that mean something.** Upload and extraction move through `stored`,
  `processing`, `extracted`, `indexing`, `indexed` and explicit failure states. `ready`
  is still absent because nothing can answer a question yet. See
  [ADR 2](docs/adr/0002-document-status-vocabulary.md).
- **Measurable quality.** The checked-in retrieval set reports Recall@3 and MRR@3 and
  fails CI below its declared thresholds. Answer evaluation comes with generation.
- **Observable operation.** Latency, tokens, cost and failure rates are product
  surfaces, not afterthoughts.
- **Deliberate scope.** Each milestone is a thin vertical slice that runs, is tested
  and is documented, rather than scaffolding for features that do not exist.

## What works today

Backend

- `GET /health`.
- `POST /documents` (`multipart/form-data`) that accepts PDFs only.
- `POST /documents/{id}/extraction`, which extracts an already-stored PDF and is
  idempotent after a successful run.
- `POST /documents/{id}/index`, which creates page-bounded chunks and transactionally
  replaces that document in the local retrieval index.
- `POST /retrieval/search`, which returns ranked evidence across all indexed documents
  or within one document.
- Two-layer validation: the declared media type **and** the `%PDF-` file signature, so
  a `.txt` renamed to `.pdf` is rejected.
- A configurable size limit (10 MB by default) enforced while the request streams in
  64 KiB chunks, so an oversized upload is refused without being read into memory.
- Storage that writes to a temporary `.part` file and renames it into place only after
  the whole payload validates; every artifact is removed if any step fails, so no
  partial document is ever left behind.
- A UUID generated once per accepted document; the client-supplied filename is stored
  as metadata and never used as a path.
- Text extraction runs outside the async event loop and is bounded to 250 pages by
  default, before any page text is persisted.
- Every page produces a span with a one-based page number. A scanned or otherwise
  textless page is retained with an empty string rather than silently dropped.
- Encrypted, over-limit and unreadable PDFs receive stable error codes. The original
  upload stays intact and the document moves to a retryable `extraction_failed` state.
- Atomic JSON sidecars for document metadata and completed page extraction results.
- Deterministic overlapping chunks that never cross a PDF page and retain exact source
  offsets, document ID and one-based page provenance.
- A versioned SQLite database with relational chunk records and FTS5/BM25 ranking. Its
  search index is kept synchronized by database triggers.
- Plain-language search is compiled into quoted tokens; client input is never executed
  as raw FTS syntax.
- A fixed two-document, four-query evaluation with enforced Recall@3 and MRR@3
  thresholds; both currently score 1.0.
- One error envelope for every failure, including framework validation errors, with
  stable machine-readable codes.
- CORS limited to the configured frontend origin.

Frontend

- A single-purpose product shell with an accessible upload form, wired to the real API.
- An explicit upload/extraction state machine that exposes both network progress and
  server-side parsing/indexing without claiming an answer exists.
- Extracted documents display filename, size, document ID, page counts, empty-page
  counts, chunk counts and previews labelled with their page provenance.
- Extraction and indexing failures keep prior successful work visible and offer the
  correct retry without repeating upload.
- A separate evidence search renders ranked excerpts with filename, page, document ID
  and chunk provenance. Zero matches are shown as a retrieval miss, not an answer.
- Failures render through `role="alert"`; progress announces through a polite live
  region; focus moves to the result only on success, so a failure leaves the caret on
  the form. The submit button uses `aria-disabled` rather than `disabled`, because
  disabling the focused element drops focus to the document body mid-upload.
- API responses are shape-checked before rendering; an unexpected payload falls back to
  our own copy rather than leaking through the UI.

## Not implemented yet

Listed so the scope of this repository is not overstated. None of the following exists
in any form here:

OCR · embeddings · semantic or hybrid retrieval · vector search · pgvector · any LLM
call · question answering · citations · answer evaluation · latency, token and cost
observability · feedback capture · guardrails · authentication · multi-tenancy ·
PostgreSQL · Docker Compose · background workers or queues · cloud infrastructure · a
design system · non-PDF file types · document listing endpoints.

## Architecture

```
Browser ──────────────► Next.js App Router (apps/web)
                          │  upload → extract → index; evidence search
                          ▼
                        FastAPI (services/api)
                          ├─ streaming validation + bounded pypdf extraction
                          │    {uuid}.pdf              unmodified upload
                          │    {uuid}.json             document state
                          │    {uuid}.extraction.json  page text
                          └─ deterministic chunking + SQLite FTS5/BM25
                               knowledge.db            documents, chunks, search index
```

The API is a single process with an embedded SQLite database, no queue and no external
service. The web app is a static-rendered shell whose client components perform the
ingestion workflow and evidence searches.

Inside the API, the request path is deliberately short: the route handler validates the
declared media type, then `store_document` streams, validates and persists. Extraction
updates the status to `processing`, parses in a worker thread, atomically persists the
complete page set and only then transitions to `extracted`. The domain models are
frozen dataclasses, separate from the Pydantic response schemas. Indexing then chunks
each non-empty page, replaces one document in SQLite in a transaction and transitions
to `indexed` only after commit.

There is no ORM. Sidecars remain the source of truth for ingestion; the retrieval index
is derived and rebuildable. [ADR 4](docs/adr/0004-sqlite-fts5-for-local-retrieval.md)
records why SQLite FTS5 is the current measured baseline rather than PostgreSQL or a
vector store.

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
│   │   ├── documents/         domain, storage, extraction, schemas and routes
│   │   └── retrieval/         chunking, SQLite FTS5, search and evaluation
│   ├── evals/                 versioned retrieval corpus, queries and thresholds
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

Open <http://localhost:3000> and upload a PDF. The UI stores it, extracts every page,
indexes attributable chunks and enables evidence search. Runtime artifacts appear
under `services/api/data/`, which is Git-ignored.

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
| `AKP_MAX_PDF_PAGES`        | `250`                   | Maximum page count accepted for one extraction. Must be positive.     |
| `AKP_CHUNK_SIZE_CHARS`      | `1000`                  | Maximum characters in a page-bounded retrieval chunk.                 |
| `AKP_CHUNK_OVERLAP_CHARS`   | `150`                   | Character overlap between adjacent chunks; must be smaller than chunk size. |
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
cd services/api && uv run python -m ai_knowledge_platform.retrieval.evaluation

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
application errors. Extraction coverage pins page provenance, empty pages, persisted
`processing`, idempotency, encrypted and unreadable PDFs, page limits, missing IDs and
cleanup of incomplete derived data. Tests run against temporary directories and never
write into the project's data directory. Retrieval coverage adds chunk boundaries and
offsets, transactional FTS indexing, idempotency, global and document-scoped search,
textless documents, plain-language query isolation and the fixed evaluation thresholds.

The frontend suite covers upload, extraction, indexing and search at component and API
client boundaries. It holds each network phase open, verifies announcements and form
locks, exercises both retry paths, checks ranked page evidence and retrieval misses, and
shape-checks every payload before rendering it.

## Roadmap

| Milestone | Scope                                                                        | State       |
| --------- | ---------------------------------------------------------------------------- | ----------- |
| 1         | Repository foundation, validated PDF upload, honest ingestion states          | Done        |
| 2         | PDF text extraction with page-level provenance                                | Done        |
| 3         | Chunking and retrieval, with evaluation before any generation                 | Done        |
| 4         | Grounded answers with verifiable citations                                    | Next        |
| 5         | Latency, token, cost and failure observability; feedback capture              | Planned     |

Milestone 4 will generate only from retrieved evidence, attach document/page citations
that resolve to the returned chunks, refuse unsupported answers and evaluate
faithfulness separately from retrieval quality.

## Decision records

- [ADR 1 — Local file storage for the first ingestion slice](docs/adr/0001-local-file-storage-for-the-first-ingestion-slice.md)
- [ADR 2 — The status vocabulary only names states that exist](docs/adr/0002-document-status-vocabulary.md)
- [ADR 3 — Keep page extraction in atomic sidecars for one more milestone](docs/adr/0003-page-extraction-sidecars.md)
- [ADR 4 — SQLite FTS5 for local lexical retrieval](docs/adr/0004-sqlite-fts5-for-local-retrieval.md)

## Project status

This is an active portfolio project, built in public in small vertical slices. It is
not a product and is not deployed anywhere. Milestone 3 is complete and verified
locally; everything described under "Not implemented yet" is genuinely absent.
