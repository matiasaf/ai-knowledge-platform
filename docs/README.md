# Documentation map

Use this page to load only the context needed for a task.

## Start here

- Product scope, architecture, setup and verification: `../README.md`
- Agent operating guide and hard constraints: `../AGENTS.md`
- Current resumable state: `../PROGRESS.md`

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

- `plans/roadmap.md`: 24-week milestone sequence, deliverables and required evidence.
- `plans/`: implementation design and acceptance criteria for bounded milestones.
- `progress/`: immutable-by-default delivery records describing what each completed
  slice actually shipped and verified.

Keep live state out of dated delivery records. Put current work, blockers and the next
action in `../PROGRESS.md`, then add a dated record when a new slice is delivered.
