# Documentation map

Use this page to load only the context needed for a task.

## Start here

- Product scope, architecture, setup and verification: `../README.md`
- Agent operating guide and hard constraints: `../AGENTS.md`
- Current resumable state: `../PROGRESS.md`

## Architecture

- `architecture/ingestion-flow.md`: upload, extraction and indexing sequence, **status**
  transitions, guarantees and known gaps.
- `architecture/backend-boundaries.md`: API layers, allowed imports, async/thread
  usage and error mapping. Import rules are checked by
  `services/api/tests/test_architecture_boundaries.py`.

## Architecture decisions

- `adr/0001-local-file-storage-for-the-first-ingestion-slice.md`
- `adr/0002-document-status-vocabulary.md`
- `adr/0003-page-extraction-sidecars.md`
- `adr/0004-sqlite-fts5-for-local-retrieval.md`
- `adr/0005-structured-grounded-answer-pipeline.md`

Read ADRs before changing storage, status vocabulary, extraction persistence, retrieval
or grounded-answer boundaries. Add a new ADR when a durable architectural decision
changes; do not rewrite an accepted decision as if it had never existed.

## Plans and delivery history

- [../ROADMAP.md](../ROADMAP.md): single study and implementation plan, active
  November schedule, dependencies, acceptance criteria and deferred long-term backlog.
- `plans/evaluation-v2-contract.md`: v2 dataset schema, labelling rules, retrieval
  metrics and run report format.
- `../services/api/evals/corpus/nist-csf.md`: provenance, license and rebuild steps for
  the publishable NIST evaluation corpus.
- `plans/`: implementation design and acceptance criteria for bounded milestones.
- `progress/`: immutable-by-default delivery records describing what each completed
  slice actually shipped and verified.

Keep live state out of dated delivery records. Put current work, blockers and the next
action in `../PROGRESS.md`, then add a dated record when a new slice is delivered.
