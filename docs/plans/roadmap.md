# 24-week roadmap

- Status: proposed
- Date: 2026-10-16
- Starting point: milestone 4 implemented; live acceptance pending
- Document scope: milestone sequence, deliverables, required evidence and the order of
  architectural decisions. It does not replace per-milestone plans or ADRs.

## 1. Expected outcome

At the end of week 24 the repository must be defensible like this:

> An end-to-end knowledge retrieval platform: ingestion with page provenance, hybrid
> retrieval measured against a BM25 baseline, RAG with server-resolved citations,
> automated retrieval and generation evaluations, background processing, latency,
> token and cost observability, authentication and multi-tenancy,
> PostgreSQL/pgvector, containers and an AWS deployment with infrastructure as code.

Every claim in that sentence must be backed by code, tests or metrics in the
repository, and by an ADR that explains the trade-off.

## 2. Roadmap rules

1. **No milestone starts on top of an unaccepted one.** Milestone 4 is accepted in
   week 1.
2. **Plan before code.** Anything listed under "Not implemented yet" in the README
   needs a `docs/plans/milestone-XX.md` or an accepted ADR before it is implemented
   (see `AGENTS.md`).
3. **One variable at a time.** No storage engine change is combined with a retrieval
   strategy change in the same week. Every migration has metric parity with the
   previous state as its acceptance criterion.
4. **Measure before claiming.** Every retrieval or generation improvement is reported
   against a versioned dataset; an improvement without numbers does not count as
   delivered.
5. **Start from what exists.** Before building resilience, queues or security, audit
   what the code already covers and document the gaps.
6. **Every new dependency has an ADR.** Redis, an external queue or a schema validator
   are only added if the ADR shows the problem exists.

Every week produces four things: a concept studied, a code change, evidence (tests,
benchmarks or evals) and communication (an ADR, diagram or document).

## 3. Corrections to a naive plan

- **The retrieval dataset is saturated.** `retrieval_v1` has 2 documents and 4 queries
  with Recall@3 = MRR@3 = 1.0. Comparing BM25, semantic and hybrid retrieval against it
  would prove nothing. `retrieval_v2` is a prerequisite for any embedding work.
- **PostgreSQL has no BM25.** `ts_rank` is a different ranking. Migrating storage and
  adding embeddings at the same time would make metric changes impossible to
  attribute. Embeddings and hybrid retrieval are implemented on the current stack
  first.
- **Feedback belongs to milestone 5.** The README roadmap already groups it with
  observability, and it requires persisted answers.
- **Authentication before public deployment.** An open upload and an endpoint that
  spends OpenAI quota are not exposed without auth and rate limiting. `workspace_id`
  enters the schema during the PostgreSQL migration to avoid a second migration.
- **Resilience and ingestion already have a foundation.** The OpenAI adapter already
  applies timeouts, bounded retries and explicit failures; ingestion is already split
  into three endpoints with explicit states (ADR 2), orchestrated by the client.

## 4. Block 1 — Weeks 1–4: master what exists and close milestone 4 (v0.1)

| Week | Study | Deliverable | Evidence |
|---|---|---|---|
| 1 | FastAPI, async and threads, Pydantic versus dataclasses, ports/adapters, idempotency | `docs/architecture/ingestion-flow.md` and `backend-boundaries.md` with sequence diagrams; milestone 4 acceptance | selected model and `make eval-answers` metrics recorded in `PROGRESS.md`; real browser flow verified |
| 2 | Inverted index, TF-IDF, BM25, Recall@K, MRR, chunking | `retrieval_v2`: more documents and 60–80 queries with paraphrases, exact terms, acronyms and hard negatives; chunk size, overlap and top-k experiment | results table in `docs/experiments/`; BM25 baseline below 1.0 |
| 3 | TypeScript: narrowing, discriminated unions, `unknown`, runtime validation | review of the JSON → validation → types → UI state boundary in `apps/web/lib/api.ts`; ADR if a schema validator is adopted | invalid payload tests |
| 4 | Test pyramid, contract tests, E2E, CI | one or two E2E flows (upload → search → answer) | CI green with the E2E tests |

Exit criterion: milestone 4 accepted and a BM25 baseline measured on `retrieval_v2`.

## 5. Block 2 — Weeks 5–8: serious RAG (v0.2)

| Week | Study | Deliverable | Evidence |
|---|---|---|---|
| 5 | Embeddings, cosine similarity, normalization, cost per token | `Retriever` port and `SemanticRetriever` on the current stack (brute-force search while the corpus is small); ADR | BM25 versus semantic on `retrieval_v2` |
| 6 | Hybrid retrieval, reciprocal rank fusion, metadata filtering, cross-encoders | `HybridRetriever` with RRF; optional reranker behind configuration | BM25 / semantic / hybrid table with quality and latency; justified default strategy |
| 7 | PostgreSQL: MVCC, indexes, `EXPLAIN`, connection pools, HNSW versus IVFFlat | migration to PostgreSQL + pgvector with `workspace_id` in the schema; ADR superseding ADR 4 | metric parity before and after the migration |
| 8 | Faithfulness, citation correctness, context relevance, LLM-as-judge | generation evaluations separate from retrieval evaluations | judge calibrated against manual labels |

Exit criterion: three retrieval strategies compared with real numbers and automated
generation evaluation.

## 6. Block 3 — Weeks 9–12: production AI, milestone 5 (v0.3)

| Week | Study | Deliverable | Evidence |
|---|---|---|---|
| 9 | Structured logging, metrics, traces, OpenTelemetry | per-stage spans (retrieval, rerank, generation); tokens, latency and estimated cost per request | instrumentation tests; documented example trace |
| 10 | Data modeling for feedback | persisted answers (question, chunks, citations, model) and useful / incorrect feedback | milestone 5 closed |
| 11 | HTTP streaming, SSE, backpressure, `AbortController` | answer streaming that validates each claim and its citation as it completes | client cancellation tests and uncited claim tests |
| 12 | Indirect prompt injection, PII, CORS, upload security; 429, backoff with jitter, circuit breakers | `docs/security/threat-model.md`; resilience audit and gap coverage | provider failure tests and malicious PDF content tests |

Exit criterion: every answer has observable cost and latency, feedback is persisted and
a threat model exists.

## 7. Block 4 — Weeks 13–16: distributed backend (v0.4)

| Week | Study | Deliverable | Evidence |
|---|---|---|---|
| 13 | Queues, workers, at-least-once delivery, acknowledgement, visibility timeout | server-side ingestion orchestration: worker and queue in PostgreSQL (`SELECT … FOR UPDATE SKIP LOCKED`); `queued` status through an ADR extending ADR 2 | state transition tests |
| 14 | Idempotency keys, outbox, dead-letter queue, orphaned jobs | idempotency on `POST /documents`; orphaned job recovery | duplicate processing tests and crash-mid-indexing tests |
| 15 | Authentication, authorization, tenant isolation, row-level security | users, workspaces and RLS; per-tenant rate limiting (Redis only if an ADR justifies it) | tests proving a tenant never retrieves another tenant's chunks |
| 16 | Multi-stage Docker, Compose | `docker compose up` with web, api, worker and PostgreSQL | clean startup documented and verified |

Exit criterion: ingestion does not depend on the request lifecycle and tenant isolation
is tested.

## 8. Block 5 — Weeks 17–20: cloud (v0.5)

| Week | Study | Deliverable | Evidence |
|---|---|---|---|
| 17 | S3, RDS, SQS, ECS/Fargate, IAM, Secrets Manager, CloudFront | cloud architecture ADR with a monthly cost estimate and a budget alarm | accepted ADR |
| 18 | Terraform: state, providers, modules, remote state | `infra/` and first deployment, with infrastructure as code from the start | clean `terraform plan`; reachable environment |
| 19 | CI/CD, OIDC, migrations during deployment | deployment pipeline; the queue moves to SQS by changing only the adapter | automated deployment verified |
| 20 | CloudWatch, alarms, load testing | dashboard with requests/min, p50/p95, error rate, retrieval and LLM latency, tokens and cost per request | load test results recorded |

Exit criterion: the system is deployed, reproducible from `infra/` and observable.

## 9. Block 6 — Weeks 21–24: AI product engineering (v1.0)

| Week | Study | Deliverable | Evidence |
|---|---|---|---|
| 21 | Building datasets from real usage | negative feedback becomes new evaluation cases | new dataset version with usage-derived cases |
| 22 | Tool calling, agent loops, state machines, MCP, human-in-the-loop | bounded tools (`search_documents`, `retrieve_document`, `compare_sources`) without turning the application into an agent | tool evals |
| 23 | Benchmarking and hardening | final benchmarks and cost report | results recorded in `docs/experiments/` |
| 24 | System design and technical communication | portfolio README, C4 diagrams (context, containers), ingestion and RAG sequences, deployment architecture, demo | README reviewed against the claims in section 1 |

## 10. Tracking

- Live state (current week, blockers, next action) is kept in `PROGRESS.md`, not in
  this document.
- Every milestone gets its own plan in `docs/plans/` before implementation and a record
  in `docs/progress/` on delivery.
- If a week slips, this document is updated with the new sequence instead of silently
  compressing the scope of the following weeks.
