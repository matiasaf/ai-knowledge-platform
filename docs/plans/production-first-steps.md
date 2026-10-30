# First steps · production roadmap

Date: 2026-10-30. Preparation for the [active roadmap](../../ROADMAP.md), with a cut
on 2026-11-22 and a budget of eight two-hour sessions. This document organizes
pending work; it does not declare its deliverables implemented.

## Verified starting point

| Question | Observed state | Evidence / implication |
|---|---|---|
| Stack | FastAPI, Python, Pydantic; Next.js 16, React 19, TypeScript | `README.md`, lockfiles and `Makefile`; eval and tracing belong to the backend |
| Retrieval / storage | SQLite FTS5/BM25; PDFs and sidecars as the source of truth | ADR 4; no vector store, embeddings or Postgres |
| Generation | OpenAI Responses API adapter behind a port | ADR 5; model pending live acceptance; credentials kept out of the repo |
| Current corpus | Fixtures of two policy documents embedded as text in JSON | `retrieval_v1.json` and `answers_v1.json`; they do not demonstrate provenance or licensing of a public corpus for the demo |
| Streaming | No | ADR 5; TTFT not applicable, total latency is |
| Tests / CI | Pytest, Vitest and an API/web workflow | `.github/workflows/ci.yml`; this preparation only re-runs offline evaluations |
| Access / operations | No auth, rate limit, daily cap, tracing or deploy | `README.md`; PDF size and page count are already limited |
| Retrieval eval | 4 queries, Recall@3 = 1.0 and MRR@3 = 1.0 | `make eval-retrieval`, 10/30; saturated baseline, insufficient for comparing improvements |
| Answer eval | 13 valid cases, including 4 unanswerable and adversarial cases | Offline validation on 10/30; no calibrated judge and no new live results |

There are prior architecture changes in the working tree. They are kept and not
attributed to this preparation. The confidentiality review of the history is still
pending; inspecting the current files does not replace it.

## Execution adjustments

1. Reuse the `retrieval/evaluation.py` and `answers/evaluation.py` modules, which
   already invoke real services with temporary indexes. Do not build another RAG
   pipeline.
2. Keep `retrieval_v1.json` and `answers_v1.json` as regression sets. Create new
   harness-compatible versions; do not move them to `eval/` just to match the example.
3. Label relevance by document and page (with offsets when needed), resolving
   chunks against each configuration. Fixed chunk IDs become invalid when chunk
   size changes and bias the experiment.
4. Define a unified Make command with explicit offline and live modes. Live mode
   needs configuration and costs money; an offline run never counts as live
   acceptance. Store JSON and Markdown with a unique identifier, commit, dataset,
   configuration, model, duration and failures, without secrets or private
   documents. The report path is defined together with the harness contract.
5. Tracing proposal: custom backend instrumentation, no new service; decide its
   persistence and retention in an ADR before implementing it. Do not assume a
   table in the rebuildable index can serve as a durable spend history.
6. Keep a single experiment (first option: top-k) and a single optimization.
   Judge, pricing and limits require versioned configuration and real evidence.
7. The public demo depends on verified access and limits. The spend cap must
   account for concurrent/in-flight requests; summing completed costs after
   responding does not guarantee a maximum. Test denial before calling the provider.
   Backups include PDFs and sidecars; restoring and rebuilding SQLite is part of
   acceptance. Do not introduce Postgres or `pg_dump` without a new decision.

## Initial queue, in order

| Order | Task | Done when | Dependencies |
|---|---|---|---|
| 1 | Confirm a publishable corpus and review history | Origin, license/permissions and review recorded; no confidential material in the artifacts to publish | Owner's confirmation of provenance |
| 2 | Define dataset v2 and report contract | Schema, factual/multi_doc/unanswerable types, stable relevance, metrics and denominators agreed and validated | Diagnosis available; local fixtures allow progress |
| 3 | Write the first 20 questions and complete to 30–40 | Every question reviewed against the sources; at least 5 unanswerable and genuinely multi-document cases | Corpus chosen; human review of expected answers |
| 4 | Extend retrieval and save a baseline | Reproducible Hit rate@k, Recall@k and MRR@k; abstention and false positives reported separately for cases without relevant passages | Dataset v2; do not attribute a 1.0 from the old dataset to an improvement |
| 5 | Close milestone 4 live acceptance | `make eval-answers`, model/snapshot and metrics recorded; one real browser flow | Credentials and budget; blocks live acceptance, not offline tasks |
| 6 | Add judge and calibration | Versioned rubric, 10 answers scored by a person, agreement computed; joint run with JSON and Markdown | Live enabled; human labels, not invented |
| 7 | Choose tracing and run the experiment | New ADR and before/after table with one variable, fixed dataset/config | Baseline and complete evaluation |

For the first 2 h session: 30 min of diagnosis and provenance, 30 min of dataset
contract and tracing proposal, 60 min writing/reviewing the first 20 questions.
If the history review takes longer, record the deviation and keep evaluation as the
priority. The technical diagnosis is already prepared in this document; the 20
questions have not been marked as done.

## Decisions that need input from the owner

- Provenance and permissions of the corpus and history; corpus chosen for the demo.
- Candidate model, local credentials and budget for evaluation/judge.
- VPS and domain, demo mode or login, daily/monthly budget and reset policy.

This input is not needed to design and validate the offline contract. Do not publish
or run paid evaluations as part of this documentation preparation.

## Checkpoints and evidence

- **11/12:** complete evaluation, with live results and calibration. If it is not
  reached, cut deploy; evaluation keeps priority.
- **Before the public link:** verify access, rate limit, spend cap and inputs;
  document restore and configuration kept outside the repo.
- **11/22:** README with real figures and links to ADRs; pending items explicit.
  The roadmap's three decision topics use new numbering starting at `0006`.
- Each session updates `PROGRESS.md` with commands, results and blockers. The
  eight sessions keep their dates in `ROADMAP.md`; actual hours are not invented.

Verification of this preparation (10/30): `make doctor` passed (shell Python
3.13.14, Node 24.22.1; targets 3.12/22), `make eval-retrieval` passed with 4/4 cases,
and `cd services/api && uv run python -m ai_knowledge_platform.answers.evaluation
--validate-only` validated 13 cases. `make check` and live calls were not run;
there are no application code changes in this work.
