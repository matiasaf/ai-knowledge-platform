# Day 1 — Foundation and a real upload path

Date: 2026-08-04

## Goal

Stand up a repository that can carry the rest of the project, and ship one honest
vertical slice: a PDF travels from a browser form to validated storage on disk, and
the interface reports exactly what happened — nothing more.

## Completed

Repository

- Monorepo with only the directories currently in use: `apps/web`, `services/api`,
  `docs/adr`, `docs/progress`.
- `.gitignore` covering build output, dependencies, caches and the runtime data
  directory; `.editorconfig`; environment examples without secrets.
- `Makefile` exposing the same gates CI runs, so local and CI drift is visible.
- GitHub Actions workflow with separate backend and frontend jobs.

Backend (`services/api`)

- Typed settings via pydantic-settings; relative paths resolve against the service
  root rather than the shell's working directory.
- `GET /health`.
- `POST /documents` accepting `multipart/form-data`, validating the declared media
  type and the `%PDF-` signature, enforcing a configurable size limit while streaming
  in 64 KiB chunks.
- Storage that writes to a `.part` file and renames into place only after validation,
  removing every artifact if any step fails.
- Domain `Document` (frozen dataclass) kept separate from the HTTP response schema.
- JSON metadata sidecar per document; no repository abstraction.
- One error envelope for every failure path, including framework validation errors,
  with stable machine-readable codes.
- CORS restricted to the configured frontend origin.

Frontend (`apps/web`)

- Next.js App Router shell with a restrained visual language and no component library.
- Upload form wired to the real endpoint through `FormData`, with the multipart
  `Content-Type` left to the browser.
- Explicit `idle | uploading | stored | error` state machine.
- Accessible labels, described-by hints, a polite live region for progress,
  `role="alert"` for failures, and focus moved to the result only on success.
- The submit button uses `aria-disabled` rather than `disabled`, because disabling the
  element that currently holds focus drops focus to the document body; the submit
  handler is the guard.
- The result panel is a named `<section>`, so moving focus to it announces what the
  region is instead of reading the first line of content with no context.
- Vitest and Testing Library cover the state machine and the API client at two
  separate boundaries, including the in-flight state that manual testing could not
  hold open long enough to observe.
- API responses are shape-checked before rendering, so an unexpected payload falls
  back to our own copy instead of leaking through the UI.

## Verified

Executed successfully on this machine:

- `uv sync`, `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy` (strict), `uv run pytest` (10 passed).
- `npm ci` from a clean `node_modules`, `npm run lint` (Biome), `npm run typecheck`,
  `npm run test` (Vitest, 14 passed), `npm run build` (Next 16.3.0 production build),
  `npm audit --audit-level=high` (0 vulnerabilities).
- `actionlint` on the CI workflow: no issues.
- Live API smoke test with `curl`: health, a 201 upload, a 415 rejection, a 422
  spoofed-PDF rejection, and a CORS preflight returning the configured origin.
- Browser run of the real UI against the real API: successful upload rendering
  filename, size and document ID, and a rejected upload rendering the error state.
- `git diff --check` and a tracked-file review for secrets, absolute paths and
  generated artifacts.

## Pending

- No end-to-end test drives a real browser against a running API. Both sides are
  covered independently, so a contract drift between them would pass CI. The cheapest
  guard would be a contract test that asserts the API response shape the client parses.
- No `GET /documents` or `GET /documents/{id}`; the current storage layout cannot
  serve a listing efficiently and none is claimed.

## Next action

Bounded PDF text extraction with page-level provenance.

Scope it as: extract text per page for an already-stored document, persist the result
alongside the PDF with the page number attached to every extracted span, and add a
`processing` and `extracted` status only once that code exists. Cover encrypted PDFs,
scanned pages with no text layer, and page-count limits explicitly — a page that
yields nothing must be recorded as empty, not silently dropped, because provenance is
what later citations will be built on.

Deliberately not next: chunking, embeddings, a vector store or any model call. Text
with trustworthy page provenance is the prerequisite for all of them.
