# Study and implementation plan

Updated: 2026-11-16.

This file is the single source for the project's next steps: what to study, what to
build, in what order, and what evidence marks each item as done. It combines the
production plan, its adaptations to this repository, and the long-term learning
proposal.

Active work targets **9–22 November 2026**, with eight two-hour sessions (16 h). The
budget is a scope constraint, not a guarantee that every deliverable will be
completed. Preparation can start before the 9th.

[PROGRESS.md](PROGRESS.md) holds the resumable state, blockers and verification
results. Tasks and their sequence are maintained here; ADRs and milestone technical
plans keep their contracts and decisions.

## Starting point

| Area | Verified / pending state |
|---|---|
| Ingestion | Milestones 1–3 complete: PDF, per-page extraction, chunks with provenance and lexical search |
| Answers | Milestone 4 implemented; acceptance with a real provider pending |
| Stack | FastAPI, Python, Pydantic; Next.js 16, React 19, TypeScript |
| Storage | PDFs and sidecars as the source of truth; SQLite FTS5/BM25 as a rebuildable index |
| Retrieval evaluation | `retrieval_v1`: 2 documents, 4 queries, Recall@3 = MRR@3 = 1.0; saturated baseline |
| Answer evaluation | `answers_v1`: 13 valid cases; no new live metrics and no calibrated judge |
| Architecture | Ingestion and backend-boundary diagrams documented; imports verified by tests |
| Operations | No streaming, auth, rate limit, spend cap, tracing or deployment |
| Public corpus | The current fixtures do not establish provenance or permission for a publishable corpus |

Prior evidence from 30 October: `make doctor`, `make eval-retrieval` and offline
validation of `answers_v1` passed. This does not establish live acceptance or a
retrieval improvement. Commands and their limits are recorded in `PROGRESS.md`.

## Order and working rules

1. Prioritize reproducible evaluation, then observability, a protected demo and
   documentation of results. If time runs short, cut deployment before evaluation.
2. Study each topic while executing its task and close it with your own evidence: a
   test, an explanation of the flow, a measurement or a documented decision.
3. Keep FastAPI, SQLite/FTS5 and the existing Python evaluators. Do not add
   frameworks, embeddings, Postgres or infrastructure to complete this cut.
4. Compare a single variable per experiment and a single optimization, with the
   dataset and all other configuration fixed. An improvement requires before/after
   measurements.
5. Keep offline results separate from live acceptance. `make check` does not call
   the provider.
6. Review the corpus and history before publishing. Never include employer
   material, secrets or documents without permission.
7. Record new decisions starting at ADR `0006`; do not replace the existing five.
8. Before exposing generation or uploads, verify access, limits and spend
   protection. A service running on a VPS is not an accepted public demo.

## Next action and dependencies

- [ ] Confirm a publishable corpus and record its origin, license/permissions and the
  history review. Inspecting the current files does not replace reviewing commits.
  Corpus selected and documented on 2026-11-16 (three public-domain NIST publications,
  [provenance](services/api/evals/corpus/nist-csf.md)); an automated history scan found
  no documents, binaries or secrets. Owner sign-off on the history review is pending.
- [x] Define and validate the v2 dataset and report contract with the existing Python
  harness. Done offline for retrieval on 2026-10-30: see the
  [v2 contract](docs/plans/evaluation-v2-contract.md) and `make eval-offline`.
- [ ] Write the first 20 questions against the reviewed sources; grow to 30–40, with
  at least five unanswerable and genuinely multi-document cases. Drafted on 2026-11-16:
  35 cases in `services/api/evals/v2_nist_csf.json`; human review pending.
- [ ] Configure `AKP_OPENAI_API_KEY`, `AKP_OPENAI_MODEL` and a budget outside the
  repository to compare models and evaluate answers/judge.

Credentials block live acceptance, but contracts, validators and offline retrieval
evaluation can continue without them. Corpus selection blocks the final labels and
any artifacts meant for publication.

## Active schedule: learn, implement and demonstrate

Dates are in November 2026. Each session is 2 h and includes applied study; no
courses or certifications are added to the budget. The technical diagnosis is
already prepared; other tasks are not considered done just because they appear in
this schedule.

| Session | Study | Implement | Closing evidence |
|---|---|---|---|
| 1 · Mon 9 | Auditing a RAG system, golden datasets, ports/adapters; custom tracing vs. an external tool | Review provenance and history; define the v2 contract and a tracing proposal; write 20 questions | Provenance recorded, contract validated and questions reviewed; explicit tracing decision before instrumenting |
| 2 · Tue 10 | Inverted index, BM25, chunking; Hit rate, Recall and MRR; hard negatives | Complete 30–40 questions; extend the retrieval evaluator; save a baseline | Reproducible metrics, explicit denominators and per-case results |
| 3 · Wed 11 | Groundedness vs. correctness; abstention; LLM-as-judge biases and calibration | Close milestone 4 live acceptance; write the judge rubric; hand-label 10 answers; joint offline/live command and reports | Model/snapshot and metrics recorded; real browser flow; human/judge agreement computed; JSON and Markdown for the run |
| 4 · Thu 12 | Experiment design and context propagation | Compare one variable (first option: top-k); start `request_id` and spans | Before/after table with quality and cost; documented decision; evaluation checkpoint |
| 5 · Mon 16 | Spans, p50/p95 percentiles, tokens and cost calculation | Complete tracing; versioned pricing configuration; metrics script or restricted view | Total/per-stage latency, cost per query and last-24 h spend on real data; TTFT not applicable |
| 6 · Tue 17 | Optimizing with evaluation; Docker Compose and an HTTPS proxy | One measured optimization (first option: reduce context/top-k); prepare Compose and Caddy for the current stack | Before/after quality, latency and cost table; VPS start-up without premature public exposure |
| 7 · Wed 18 | Access, rate limiting, spend-cap concurrency; backup/restore | Login or restricted demo mode; query/input limits; budget reservation; backup of PDFs and sidecars | Denial before calling the provider when the budget is exhausted, even under concurrency; restore and index rebuild tested; protected HTTPS |
| 8 · Thu 19 | ADRs and communicating technical results | README as a case study; ADRs for evaluation, experiment and observability/cost | README with real figures and links; review by someone outside the project pending until done |
| Wrap-up · 21–22 | Reproducibility and scope review | Resolve pending items by priority; test from a clean install; document what was cut | Reproducible evaluation and metrics; demo only if it meets the controls; pending items and limitations explicit |

**Checkpoint: 12 November.** If the joint evaluation does not run end to end with live
results and calibration, week-two deployment is cut.
Outcome: not met (no credentials, no reviewed corpus by 12 November). Deliverable 3
(protected demo) is cut from this window and moves to the deferred backlog.
**Final cut: 22 November.** Whatever is not done moves to the deferred backlog; tasks
are not silently compressed and hours or metrics are not invented.

## Deliverable contracts

### 1. Reproducible evaluation · highest priority · indicative budget 6 h

- [ ] Reuse `retrieval/evaluation.py`, `answers/evaluation.py` and
  `services/api/evals/`; keep the v1 datasets as regression sets.
- [ ] Version a v2 dataset with `factual`, `multi_doc` and `unanswerable` questions,
  expected facts and relevance by document/page (offsets where needed). Resolve
  chunks for each configuration: fixed chunk IDs invalidate chunking changes.
- [ ] Measure Hit rate@k, Recall@k and MRR@k. Report abstention and false positives
  separately for cases without relevant passages; make denominators and per-case
  results explicit.
- [ ] Measure groundedness, correctness (1–3 scale), abstention and the existing
  milestone 4 citation/fact gates. Keep human review of support and adversarial cases.
- [ ] Version the rubric and calibrate the judge against 10 answers scored by a
  person; compute agreement. Do not use the generator as the sole judge of itself.
- [ ] Define a joint Make command with explicit offline and live modes.
  `make eval-offline` covers the offline v2 retrieval part; **live mode does not
  exist yet**.
- [ ] Store JSON and a Markdown summary per run, with a unique ID, commit, dataset,
  configuration, model/snapshot, duration and failures. Define the path with the
  contract; exclude secrets and private material.
- [ ] Run `make eval-answers`, record the model comparison/selection and complete a
  real flow: upload → extract → index → answer → open citation in the PDF; also check
  an unanswerable question and console errors.

Done: reproducible end-to-end evaluation, v2 baseline, live metrics and calibration
recorded. An offline schema validation does not satisfy this.

### 2. Observability and experiment · high priority · indicative budget 4 h

- [x] Decide trace persistence and retention through an ADR; initial proposal:
  custom backend instrumentation without a new service. Do not assume the
  rebuildable SQLite index can hold a durable spend history.
  [ADR 0006](docs/adr/0006-in-process-request-tracing.md), 2026-11-16.
- [ ] Propagate `request_id`; measure retrieval and generation, plus any other stages
  that actually exist. Record failures, latencies, tokens, cost, top-k, chunks and
  prompt version without storing secrets or unnecessary private content.
  Done on 2026-11-16 except cost, which waits for versioned prices.
- [ ] Version per-model prices with their date/reference when implementing costs.
- [ ] Expose metrics through a script or restricted view: total and per-stage p50/p95,
  average cost per query and last-24 h spend. There is no streaming: TTFT is N/A.
- [ ] Compare one variable with the full evaluation and record the decision. Do not
  add hybrid search or reranking to this cut just to manufacture an experiment.
- [ ] Measure one optimization with traces and evaluation without degrading the
  quality gates. A cache or model change must justify invalidation/scope first.

Done: before/after tables and metrics taken from real runs, with comparable
configuration and an explained decision.

### 3. Protected demo · conditional on the checkpoint · indicative budget 3 h

- [ ] Confirm the VPS, domain/subdomain, login or demo mode, daily/monthly budget and
  limit reset policy.
- [ ] Prepare Compose with web/API and the current persistent storage; Caddy for
  HTTPS. Real variables outside the repository; `.env.example` documented.
- [ ] Implement access, per-identity/IP rate limiting and input limits; also check the
  existing PDF size and page-count limits.
- [ ] Reserve budget before provider calls, including concurrent/in-flight requests.
  Summing spend after completion does not guarantee a daily maximum.
- [ ] Test rejection before calling the provider and an explicit response when the
  quota is exhausted.
- [ ] Automate backups of PDFs/sidecars and verify restore and SQLite rebuild. Do not
  use `pg_dump`: there is no PostgreSQL in this cut.

Done: an HTTPS link with tested controls and documented recovery. If the checkpoint
or a pre-publication control fails, the demo stays pending.

### 4. Document decisions and results · indicative budget 3 h

- [ ] README: purpose, real architecture, local setup, evaluation results,
  experiment, latency and cost, demo if it exists, and limitations.
- [ ] New ADRs from `0006`: evaluation/calibration, experiment decision and
  observability/spend protection, cross-linked where relevant.
- [ ] External review of the README and verification from a clean install.
- [ ] Update `PROGRESS.md` each session with commands, results and blockers; record
  actual hours only when they are known.

Done: every quality, performance or deployment claim has accessible evidence.

## Study guide over the current code

Review these fundamentals when a task depends on them, without starting a separate
implementation track:

| Topic | Reading or practice in the repository | Sign of understanding |
|---|---|---|
| FastAPI, async/threads, idempotency, dataclasses/Pydantic, ports/adapters | [Ingestion flow](docs/architecture/ingestion-flow.md), [backend boundaries](docs/architecture/backend-boundaries.md), ADRs 2–5 | Explain states, retries and responsibilities by following a real request |
| BM25 and retrieval evaluation | ADR 4, chunking and the retrieval evaluator | Explain why v1's 1.0 does not prove an improvement and how Recall differs from MRR |
| TypeScript and trust boundaries | `apps/web/lib/api.ts`, tests and `apps/web/AGENTS.md` | Follow JSON → `unknown` validation → types/unions → UI state; identify invalid payloads |
| Testing and CI | `Makefile`, pytest/Vitest tests and `.github/workflows/ci.yml` | Choose a domain, contract or UI test for a specific failure; distinguish offline/live |
| Grounding and safety | ADR 5 and the [milestone 4 contract](docs/plans/milestone-04-grounded-answers.md) | Explain a valid citation vs. a supported claim, abstention and indirect injection |

## Deferred study and implementation backlog

The former 24-week proposal is folded in here as an **indicative post-cut sequence**,
with no committed dates and no automatic authorization to start infrastructure.
Before each milestone: review the need, write a plan/ADR and define acceptance
criteria. Anything already advanced in November is verified and reused.

| Order | Study | Possible implementation | Required evidence |
|---|---|---|---|
| 1 | Hard datasets, paraphrases, acronyms and negatives; test pyramid, contracts and E2E | Grow v2 to 60–80 queries if needed; review frontend validation; 1–2 E2E flows | Milestone 4 accepted; dataset useful for comparison; invalid-payload and E2E tests in CI |
| 2 | Embeddings, cosine similarity, normalization and cost | `Retriever` port and semantic search on the current stack; brute force if the corpus is small | ADR and BM25/semantic comparison on a fixed dataset |
| 3 | Hybrid retrieval, RRF, filters and cross-encoders | `HybridRetriever`; reranker only if justified | BM25/semantic/hybrid table with quality, latency and a justified default |
| 4 | PostgreSQL, MVCC, indexes, EXPLAIN, pools, HNSW/IVFFlat | Migrate to PostgreSQL/pgvector with `workspace_id`, separate from the strategy change | ADR superseding ADR 4 and metric parity before/after |
| 5 | Semantic evaluation, feedback modeling and traceability | Reuse November evals/traces; persist answers and useful/incorrect feedback | Calibrated judge; cost/latency per answer; explicit closure of milestone 5 |
| 6 | SSE, backpressure, AbortController | Streaming that validates every claim/citation before showing it | Cancellation tests and rejection of uncited claims; new decision on ADR 5 |
| 7 | Indirect injection, PII, CORS, uploads; 429, backoff and circuit breakers | Threat model and resilience audit of what is already implemented | Provider-failure and adversarial-PDF tests; gaps documented |
| 8 | Queues, workers, at-least-once, acknowledgements and visibility timeout | Backend orchestration; PostgreSQL queue with `FOR UPDATE SKIP LOCKED`; `queued` state via ADR | Transition tests; ingestion independent of the HTTP cycle |
| 9 | Idempotency keys, outbox, dead letters and orphaned jobs | Upload idempotency and job recovery | Tests for duplicates and crashes during indexing |
| 10 | Authentication, authorization, isolation and RLS | Users/workspaces and per-tenant limits; Redis only if an ADR justifies it | Tests that prevent retrieving another tenant's chunks |
| 11 | Multi-stage Docker and service operations | Extend Compose to web/API/worker/PostgreSQL if already accepted | Clean start-up and recovery verified |
| 12 | AWS: S3, RDS, SQS, ECS/Fargate, IAM, Secrets Manager, CloudFront | Cloud ADR with a monthly estimate and a budget alarm | Decision accepted before deploying |
| 13 | Terraform, remote state, CI/CD, OIDC and migrations | `infra/`, reproducible deployment and an SQS adapter if appropriate | Reviewed Terraform plan, reachable environment and verified pipeline |
| 14 | CloudWatch, alarms and load testing | Dashboard for traffic, errors, retrieval/LLM, tokens, cost and percentiles | Load test and alarm response recorded |
| 15 | Datasets derived from real usage; tool calling, MCP and human-in-the-loop | Turn negative feedback into cases; bounded tools to search/retrieve/compare | Versioned dataset and tool evals; no turning the app into an agent without a decision |
| 16 | Benchmarking, system design and communication | Hardening, final benchmarks, C4/sequence/deployment diagrams and demo | Quality/cost report and README checked against real capabilities |

Outside the November cut: agents/LangGraph/MCP, fine-tuning, multi-tenancy, UI
redesign, Kubernetes/Terraform and additional cloud. Courses, certifications, more
than one experiment or more than one optimization are also not scheduled in those 16 h.

## Verify and record progress

Commands available today, from the repository root:

```bash
make doctor
make eval-retrieval
make eval-offline
(cd services/api && uv run python -m ai_knowledge_platform.answers.evaluation --validate-only)
make check
# Requires credentials/model and budget; makes paid calls:
make eval-answers
```

While implementing, run the focused checks first (`make check-api` or
`make check-web`) and then the full gate before claiming full verification. Record
real results and blockers in `PROGRESS.md`; do not mark tasks in this plan complete
without their evidence. Historical delivery records remain in `docs/progress/`.
