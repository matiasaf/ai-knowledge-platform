# ai-knowledge-platform — Production roadmap

## Integration with this repository · 2026-10-30

**Active plan for November 9–22, 2026.** The contributed roadmap is kept below, with
its eight sessions and its 16 h budget. Preparation starts now; the sessions are not
yet considered done.

The [first-steps plan](docs/plans/production-first-steps.md) adapts names,
dependencies and acceptance criteria to the existing code. Its adjustments take
precedence over the stack, command and file examples in the original text:

- FastAPI + SQLite FTS5/BM25 remain the foundation (ADR 4). No migration to
  PostgreSQL/pgvector or embeddings is scheduled to meet this cut.
- The Python evaluators and datasets in `services/api/evals/` are extended.
  `make` remains the canonical entry point; `npm run eval` is the name proposed in
  the original, not a command available today. The unified command is still pending.
- There is no streaming: TTFT is recorded as not applicable. Total and per-stage
  latency are measured; streaming is not added just to produce that metric.
- Five ADRs already exist. New decisions continue from `0006` without overwriting
  them; the tracing choice still requires a decision.
- Deployment uses the current storage and includes PDFs and sidecars in its
  backups. Access, limits and spend protection are verified **before** exposing
  generation or uploads to the public.
- The [24-week roadmap](docs/plans/roadmap.md) remains a deferred long-term
  proposal. It is not a second active schedule.

Resumable state and verification evidence live in [PROGRESS.md](PROGRESS.md).
The original's open questions remain pending; incorporating it does not certify
corpus provenance, history, a deploy or acceptance with a real model.

---

 
> **From "a demo that works" to "a system that is measured".**
> Period: November 9 to 22, 2026 · 8 sessions of 2 h (16 h total) · hard cut on 11/22.
 
When finished, the repo must have:
 
- **Reproducible evaluation**: `npm run eval` measures retrieval and answers over a fixed dataset.
- **Observability**: every request leaves a trace with per-stage latency, tokens and cost.
- **Live demo**: deployed on the VPS with HTTPS, login or demo mode, rate limit and a daily spend cap.
- **Decision documentation**: README as a case study and 3 ADRs.
---
 
## Contents
 
1. [Project rules](#project-rules)
2. [Target architecture](#target-architecture)
3. [Deliverables map](#deliverables-map)
4. [Schedule](#schedule)
5. [Day-by-day plan](#day-by-day-plan)
6. [Out of scope](#out-of-scope)
7. [Questions this project must be able to answer](#questions-this-project-must-be-able-to-answer)
8. [Open questions](#open-questions)
---
 
## Project rules
 
1. **The order of deliverables is the order of priority.** If time runs out, the bottom items are dropped, never evaluation.
2. **Hard cut on November 22.** Whatever is not done moves to "Next steps" in the README.
3. **Every improvement is measured before and after.** An improvement without a number does not count.
4. **No new frameworks just to learn them.** Use what the repo already has, unless a tool saves hours.
5. **Confidentiality.** No code, prompts or documents from an employer enter the repo. If the repo grew out of that work, review the commit history before making it public.
6. **Cut rule:** if evaluation does not run end to end by the end of week 1, week 2 cuts Deliverable 3, not 1.
---
 
## Target architecture
 
```
                ┌──────────────┐
  User ──────▶  │    Access    │  login / demo mode · rate limit · daily cap
                └──────┬───────┘
                       ▼
            ┌─────────────────────────────────────────────┐
            │                 RAG pipeline                │
            │  embed query → retrieve → (rerank) → LLM    │
            └──────┬───────────────────────────┬──────────┘
                   │                           │
                   ▼                           ▼
           ┌──────────────┐            ┌──────────────┐
           │  Postgres +  │            │    Traces    │  request_id · spans · tokens · cost
           │  pgvector    │            │              │
           └──────────────┘            └──────┬───────┘
                                              ▼
                                      ┌──────────────┐
                                      │   Metrics    │  p50/p95 · TTFT · cost/query · 24 h cost
                                      └──────┬───────┘
                                             │ daily cost
                                             └──────────▶ triggers the cap in Access
 
  npm run eval ──▶ calls the SAME pipeline ──▶ eval/results/<date>.json + summary.md
```
 
- The eval uses the same pipeline as the demo: **what is measured is what runs in production**.
- Traces feed the metrics, and the daily cost triggers the cap in Access.
- Adjust the box names to the real stack after session 1.
---
 
## Deliverables map
 
| # | Deliverable | Hours | Priority | Done when |
|---|---|---|---|---|
| 1 | Evaluation | 6 h | Highest | `npm run eval` runs end to end, writes `eval/results/<date>.json` and a Markdown summary, and the README shows the experiment table. |
| 2 | Observability, cost and latency | 4 h | High | You can say "p95 of X s, TTFT of Y ms, Z cents per query, and with [change] it dropped to W without losing quality according to the eval". |
| 3 | Deploy, authentication and cost protection | 3 h | Medium | There is a working HTTPS link and no way for the demo to spend more than the daily cap. |
| 4 | README as case study and ADRs | 3 h | Medium | Someone who has never seen the repo understands in one minute what it does, how it is measured and what was decided. |
 
### File structure added
 
```
eval/
  dataset.jsonl            # 30–40 questions with expected answer and correct chunks
  results/<date>.json      # output of each run
  results/<date>.md        # readable summary
  calibration.jsonl        # 10 hand-scored answers
config/
  pricing.(json|ts)        # per-model prices, not hardcoded
docs/
  adr/
    001-evaluation.md
    002-experiment.md
    003-observability-and-costs.md
docker-compose.yml
Caddyfile
ROADMAP.md
README.md
```
 
---
 
## Schedule
 
| # | Day | Work | Session output |
|---|---|---|---|
| 1 | Mon 9 | Repo diagnosis · choose tracing approach · first 20 questions | Starting-point table complete |
| 2 | Tue 10 | Finish dataset · retrieval metrics | Hit rate, recall and MRR computed |
| 3 | Wed 11 | Answer metrics with a judge · calibration | `npm run eval` end to end |
| 4 | Thu 12 | Experiment (one variable) · start tracing | Before/after experiment table |
| 5 | Mon 16 | Finish tracing · metrics view | p50/p95, TTFT and cost per query |
| 6 | Tue 17 | Measured optimization · Docker Compose + Caddy | Before/after optimization; app on the VPS |
| 7 | Wed 18 | Login or demo mode · rate limit · daily cap · backups | Public, protected HTTPS link |
| 8 | Thu 19 | README and 3 ADRs | Repo ready to show |
| — | 21–22 | Buffer and wrap-up | Everything published |
 
**Week 1 checkpoint (Thu 12):** does `npm run eval` run end to end? If not → week 2 cuts Deliverable 3.
 
---
 
## Day-by-day plan
 
Each session has: **goal**, **what gets implemented** (checklist), **what gets learned**, **files** and **how to know it is done**.
 
---
 
### Week 1 — Evaluation
 
---
 
### Day 1 · Monday 11/9 — Diagnosis and dataset (part 1)
 
**Goal:** know exactly what you have and start the golden dataset.
 
**Implemented**
 
- [ ] 30-minute diagnosis — complete the starting-point table:
  | Question | Answer | Why it matters |
  |---|---|---|
  | What stack does it use? (Next.js, Node, other) | | Defines where the eval and traces live |
  | What vector store? (pgvector, other) | | Defines whether the VPS runs a single Postgres or more services |
  | Which LLM and embeddings provider? | | Defines how per-request cost is computed |
  | What corpus does it use? Is it public? | | The demo and the eval need publishable documents |
  | Does it have streaming? | | If so, TTFT is measured |
  | Does it have auth, tests or CI? | | Whatever already exists is documented instead of built |
- [ ] Review commit history for confidential material.
- [ ] Decide the tracing approach and **do not change it afterwards**:
  - Option A (recommended): a `traces` table in the same Postgres, with custom spans or the OpenTelemetry API.
  - Option B: self-hosted Langfuse (saves building a UI, but adds a service to operate on the VPS).
- [ ] Define the format of `eval/dataset.jsonl`.
- [ ] Write the first 20 questions by hand.
**Suggested format for each dataset line**
 
```json
{"id": "q001", "type": "factual", "question": "...", "expected_answer": "...", "relevant_ids": ["doc-12#chunk-3"]}
```
 
`type` ∈ `factual` · `multi_doc` · `unanswerable`
 
**Learned**
 
- How to audit an existing RAG system before modifying it.
- What a *golden dataset* is and why it must be fixed and versioned.
- Trade-off between building your own observability vs. adopting a tool.
**Files:** `eval/dataset.jsonl`, diagnosis notes (can go at the end of this ROADMAP).
 
**Done when:** the starting-point table is complete, the tracing approach is chosen and 20 questions are written.
 
---
 
### Day 2 · Tuesday 11/10 — Full dataset and retrieval metrics
 
**Goal:** measure how well the system retrieves, without an LLM, cheaply and deterministically.
 
**Implemented**
 
- [ ] Complete the dataset to 30–40 questions with this mix:
  - Direct factual questions.
  - Questions that need 2 documents (`multi_doc`).
  - **5 questions the corpus cannot answer** (`unanswerable`).
- [ ] Harness script that, for each question, calls the pipeline's real retriever and stores the returned IDs.
- [ ] Implement the metrics:
  | Metric | What it answers |
  |---|---|
  | Hit rate @k | Did at least one correct chunk appear in the top-k? |
  | Recall @k | What proportion of the correct chunks was retrieved? |
  | MRR | How high did the first correct chunk rank? |
- [ ] First run, saving the result as the baseline.
**Learned**
 
- The difference between evaluating **retrieval** and evaluating **generation**, and why it pays to separate them.
- Hit rate vs. recall vs. MRR: what each one captures and when they mislead.
- Why unanswerable questions are part of the dataset.
**Files:** `eval/dataset.jsonl`, `eval/retrieval.(ts|js)`, `eval/results/<date>.json`.
 
**Done when:** hit rate, recall and MRR are computed over the full dataset and a baseline is saved.
 
---
 
### Day 3 · Wednesday 11/11 — Answer metrics with LLM as judge
 
**Goal:** measure answer quality and show that the judge is reliable.
 
**Implemented**
 
- [ ] Written rubric for the judge (in the repo, versioned).
- [ ] Metrics:
  - **Groundedness:** is every claim supported by the retrieved context?
  - **Correctness:** does it match the expected answer? (1–3 scale)
  - **Abstention:** on the 5 unanswerable questions, did it say it didn't know?
- [ ] Calibration: score 10 answers by hand and compute the % agreement with the judge.
- [ ] An `npm run eval` command that runs retrieval + answers and writes:
  - `eval/results/<date>.json`
  - a Markdown summary.
**Learned**
 
- LLM-as-judge: how to write a rubric, typical biases and why it must be calibrated.
- Groundedness vs. correctness: an answer can be correct and unsupported (or the reverse).
- How to evaluate abstention ("I don't know") as desired behavior.
**Files:** `eval/judge.(ts|js)`, `eval/rubric.md`, `eval/calibration.jsonl`, `package.json` (`eval` script).
 
**Done when:** `npm run eval` runs end to end and the judge/human agreement % is computed.
 
---
 
### Day 4 · Thursday 11/12 — Experiment and tracing kickoff
 
**Goal:** make a technical decision based on numbers.
 
**Implemented**
 
- [ ] Choose **a single variable** (from simplest to most complex):
  1. Chunk size.
  2. top-k.
  3. Hybrid search (keyword + vector).
  4. Reranking.
- [ ] Run the eval before and after, with everything else fixed.
- [ ] Before/after table: retrieval metrics, answer metrics and cost.
- [ ] Record the decision made (input for ADR-002).
- [ ] Start tracing: generate a `request_id` and propagate it through every stage.
**Learned**
 
- Experiment design: one variable, same dataset, fair comparison.
- Real trade-offs between quality, latency and cost.
- Context propagation (`request_id`) through a pipeline.
**Files:** `eval/results/` (two runs), notes for `docs/adr/002-experiment.md`, tracing module.
 
**Done when:** the before/after table exists with the decision and its cost.
 
**✅ Week 1 checkpoint:** evaluation runs end to end. If not, week 2 cuts Deliverable 3.
 
---
 
### Week 2 — Observability, deploy and documentation
 
---
 
### Day 5 · Monday 11/16 — Complete traces and metrics view
 
**Goal:** have the latency and cost numbers that come up in any technical conversation.
 
**Implemented**
 
- [ ] Per-request trace with these fields:
  | Field | Detail |
  |---|---|
  | `request_id` | Propagated through every stage and logged |
  | Spans | embed query → retrieve → rerank (if present) → LLM |
  | Latency | Duration per span, total, and TTFT if there is streaming |
  | Tokens | LLM input and output, embedding tokens |
  | Cost | Computed from a per-model price table in config, not hardcoded |
  | Context | top-k used, chunk IDs and prompt version |
- [ ] Price table in `config/pricing`.
- [ ] Metrics view: an `/admin/metrics` page **or** an `npm run stats` script with:
  - p50/p95 of total latency and TTFT.
  - Average cost per query.
  - Cost over the last 24 h.
**Learned**
 
- Spans and traces (OpenTelemetry mental model).
- Percentiles (p50/p95) vs. average: why the average hides the tail.
- TTFT and why it matters more than total latency in streaming interfaces.
- How to compute per-request cost from tokens.
**Files:** `traces` table migration, tracing module, `config/pricing`, `stats` script or `/admin/metrics` route.
 
**Done when:** p50/p95, TTFT and cost per query can be read from real data.
 
---
 
### Day 6 · Tuesday 11/17 — Measured optimization and deploy
 
**Goal:** improve a number without losing quality, and have the app running on the VPS.
 
**Implemented**
 
- [ ] Choose **one** optimization:
  - Answer cache for repeated questions (hash of the normalized query).
  - Reduce top-k or context size.
  - A smaller model for a secondary step (for example, query rewriting).
- [ ] Measure before/after with traces **and** with the eval (quality must not drop).
- [ ] `docker-compose.yml` with the app and Postgres (with pgvector if applicable).
- [ ] Caddy in front for automatic HTTPS with a domain or subdomain.
- [ ] Environment variables outside the repo (`.env.example` yes, `.env` no).
**Learned**
 
- Optimizing with guardrails: latency/cost measured by traces, quality measured by the eval.
- Caching strategies in LLM systems and their risks.
- Docker Compose for a single-node deploy, and a reverse proxy with automatic TLS.
**Files:** `docker-compose.yml`, `Caddyfile`, `.env.example`, the optimization change.
 
**Done when:** there is a before/after optimization table and the app responds on the VPS.
 
---
 
### Day 7 · Wednesday 11/18 — Access, limits and backups
 
**Goal:** make sure the public demo cannot spend more than planned.
 
**Implemented**
 
- [ ] Simple login (GitHub OAuth or magic link with the stack's auth library) **or** an anonymous demo mode with lower limits.
- [ ] Rate limit per user or IP (for example, 20 queries per hour).
- [ ] Daily spend cap: if the day's cost (taken from the traces) exceeds the threshold, the API responds "demo paused until tomorrow".
- [ ] Maximum input size and uploaded file size (if the demo allows uploads).
- [ ] Daily backup of the Postgres volume (cron with `pg_dump`).
**Learned**
 
- Why a public LLM endpoint is a cost risk, not just a security risk.
- Rate limiting (fixed vs. sliding window) and where to apply it.
- Cost circuit breaker using observability as the source of truth.
- Basic operations: backups and restore.
**Files:** rate limit and cap middleware, auth configuration, backup script/cron.
 
**Done when:** there is a public, protected HTTPS link.
 
---
 
### Day 8 · Thursday 11/19 — README as case study and ADRs
 
**Goal:** make the repo explain itself, in 60 seconds or in 10 minutes.
 
**Implemented**
 
- [ ] README with this structure:
  1. One line on what it is + link to the demo.
  2. Architecture diagram (the one in this roadmap, adapted to the real stack).
  3. Results: eval table, experiment table, p50/p95, TTFT and cost per query.
  4. Decisions and trade-offs: 3 bullets linking to the ADRs.
  5. How to run it locally in 3 commands.
  6. Next steps: what was left out by the cut.
- [ ] ADRs in `docs/adr/` (half a page each: context, decision, alternatives, consequences):
  - **ADR-001:** how the system is evaluated (metrics, LLM as judge and its calibration).
  - **ADR-002:** the experiment decision, with its numbers.
  - **ADR-003:** how cost is observed and protected (traces, rate limit, daily cap).
- [ ] Ask someone who has not seen the repo to read it.
**Learned**
 
- Documenting decisions with ADRs.
- Communicating technical results with numbers, for technical and non-technical readers.
**Files:** `README.md`, `docs/adr/001-evaluation.md`, `docs/adr/002-experiment.md`, `docs/adr/003-observability-and-costs.md`.
 
**Done when:** someone who has never seen the repo understands in one minute what it does, how it is measured and what was decided.
 
---
 
### Saturday 21 and Sunday 22/11 — Buffer and wrap-up
 
- [ ] Finish whatever is left from days 1–8 (in priority order).
- [ ] Move everything that did not make it to the README's "Next steps".
- [ ] Verify that the demo, the eval and the metrics work from scratch (clone, start, run).
- [ ] Publish.
---
 
## Out of scope
 
Not included in these two weeks. Goes to "Next steps" in the README.
 
- Agents, LangGraph, MCP or tool calling.
- Fine-tuning or custom models.
- Multi-tenancy, roles and fine-grained permissions.
- UI redesign.
- Kubernetes, Terraform or infrastructure beyond Docker Compose.
- Courses or certifications associated with the project.
- More than one experiment or more than one optimization.
---
 
## Questions this project must be able to answer
 
By 11/22, each one must have an answer backed by the repo's own numbers.
 
| Question | Comes from |
|---|---|
| How do you evaluate retrieval quality? | Day 2 · hit rate, recall, MRR |
| How do you know the LLM-as-judge is reliable? | Day 3 · calibration against hand-scored answers |
| How do you handle questions the corpus can't answer? | Day 3 · abstention metric |
| Tell me about a change you made and how you measured it. | Day 4 · experiment and ADR-002 |
| What are your latency and cost per query? How did you reduce them? | Days 5–6 · traces and optimization |
| How do you debug a bad answer in production? | Day 5 · trace with chunks, prompt version and spans |
| How do you protect a public LLM endpoint from abuse and runaway cost? | Day 7 · rate limit and daily cap |
| RAG vs fine-tuning: when would you choose each? | The complete system as an example |
 
---
 
## Open questions
 
- [ ] Is the repo public and free of employer code or data?
- [ ] What public corpus does the demo use? If it has none, choose a small, stable one (for example, the documentation of a well-known open source project).
- [ ] What domain or subdomain will the demo use on the VPS?
- [ ] What is the acceptable monthly spend cap for the demo?
- [ ] Does the repo already have auth, tests or CI? (Answered on Day 1.)
---
 
## Progress log
 
| Day | Date | Actual hours | Done | Pending / notes |
|---|---|---|---|---|
| 1 | 11/09 | | | |
| 2 | 11/10 | | | |
| 3 | 11/11 | | | |
| 4 | 11/12 | | | |
| 5 | 11/16 | | | |
| 6 | 11/17 | | | |
| 7 | 11/18 | | | |
| 8 | 11/19 | | | |
| — | 11/21–22 | | | |
| **Total** | | **/ 16 h** | | |
