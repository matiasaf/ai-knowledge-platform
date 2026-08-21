# AI Knowledge Platform agent guide

This file is the entry point for coding agents. Keep it short and use the linked
documents as the system of record instead of duplicating them here.

## Purpose and current state

Build an evidence-first document knowledge platform: ingest PDFs, preserve page
provenance, retrieve attributable passages, and generate only grounded answers with
verifiable citations.

- Product scope, architecture, setup and configuration: `README.md`
- Current work, blockers and next action: `PROGRESS.md`
- Documentation map: `docs/README.md`
- Decisions and their rationale: `docs/adr/`
- Historical milestone delivery notes: `docs/progress/`

Read `PROGRESS.md` before starting work that may span sessions. Update it before ending
such work so another session can resume without reconstructing state from chat history.

## Stack and layout

- `services/api`: Python 3.12+, FastAPI, Pydantic, pypdf and SQLite FTS5; dependencies
  are locked by `uv.lock`.
- `apps/web`: Node.js 22, Next.js 16, React 19, TypeScript, Biome and Vitest;
  dependencies are locked by `package-lock.json`.
- `Makefile`: canonical local entry points; CI must run the equivalent quality gates.
- `.python-version` and `.nvmrc`: preferred local runtime families.

Within `apps/web`, also follow the generated `apps/web/AGENTS.md`. It points to the
installed Next.js documentation that must be consulted before changing framework code.

## First run

From the repository root:

```bash
make doctor
make install
```

Run the application in two terminals with `make api` and `make web`. Ingestion and
retrieval need no secrets. Grounded generation additionally needs both
`AKP_OPENAI_API_KEY` and `AKP_OPENAI_MODEL`; copy the checked-in `.env.example` files.

## Verification

Run the narrowest relevant checks while iterating, then the complete gate before
claiming the repository is verified.

```bash
make check-api       # API lint, format, types, tests and offline evaluations
make check-web       # web lint, types, tests, build and dependency audit
make check           # every local/CI gate
make eval-retrieval  # deterministic retrieval quality thresholds
make eval-answers    # paid live provider evaluation; requires OpenAI configuration
```

Do not claim live answer acceptance from `make check`: it validates the answer dataset
but deliberately does not call a provider. Record exact commands and outcomes in
`PROGRESS.md` when verification is incomplete or environment-dependent.

## Non-negotiable invariants

- Evidence precedes generation; do not fabricate answers or citations on a retrieval
  miss or provider failure.
- Every chunk and accepted citation retains trusted document, page and offset
  provenance. Citation metadata is resolved server-side, never accepted from a model.
- PDFs and atomic sidecars are the ingestion source of truth; `knowledge.db` is a
  derived, rebuildable index.
- Domain objects remain separate from HTTP schemas. Domain code does not import
  FastAPI, Pydantic, OpenAI or SQLite.
- The frontend runtime-validates API payloads before rendering them.
- Keep ingestion and retrieval usable without provider credentials.
- Preserve stable error envelopes and explicit state transitions. Never smooth a
  failure into a success state.
- Never commit secrets, `.env` files, uploaded documents, generated caches or build
  output.
- Do not add speculative infrastructure or features from the README's “Not implemented
  yet” list without an accepted plan or decision record.

## Change workflow

1. Inspect the relevant ADRs, tests and scoped instructions before editing.
2. Keep changes within one vertical slice and preserve unrelated user changes.
3. Add or update tests at the closest useful boundary.
4. Run focused checks, then `make check` when practical.
5. Update product documentation, an ADR and/or `PROGRESS.md` whenever behavior,
   architecture, status or verification evidence changes.

Prefer executable constraints in tests, type checks, linters and Make targets over new
prose rules. If a rule repeatedly matters, automate it and keep this file as the map.
