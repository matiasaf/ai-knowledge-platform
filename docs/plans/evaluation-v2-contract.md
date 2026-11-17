# Evaluation v2 contract

- Status: implemented offline (retrieval); answer and judge scoring pending
- Date: 2026-10-30
- Code: `services/api/src/ai_knowledge_platform/evaluation/`
- Tests: `services/api/tests/test_evaluation_v2.py`
- Roadmap: deliverable 1 in [ROADMAP.md](../../ROADMAP.md)

## Why v2

`retrieval_v1` scores 1.0 on four questions, so it cannot show whether a change helps.
The retrieval and answer v1 datasets also duplicate the same corpus and questions in
two files. v2 keeps one file per dataset for both evaluations and labels relevance in
a way that survives chunking changes. The v1 files stay unchanged as regression sets.

## Dataset file

One JSON file, validated by `evaluation/dataset.py`:

| Field | Meaning |
|---|---|
| `schema_version` | Always `2`. |
| `name` | Lowercase slug; appears in run IDs and reports. |
| `stage` | `draft` or `baseline`. Only a baseline may be quoted as a result. |
| `corpus.provenance`, `corpus.license` | Where the text comes from and the permission to use or publish it. |
| `corpus.documents[]` | `document_id`, `filename` and `pages[]` (`page_number`, `text`). |
| `retrieval` | `chunk_size_chars`, `chunk_overlap_chars`, `k` and optional `thresholds` (`hit_rate_at_k`, `recall_at_k`, `mrr_at_k`). |
| `cases[]` | Questions, described below. |

Each case:

| Field | Meaning |
|---|---|
| `id` | Lowercase slug, unique in the file. |
| `type` | `factual` (one document), `multi_doc` (two or more documents) or `unanswerable`. |
| `language` | `en` or `es`. |
| `tags` | Optional: `adversarial`, `lexical_false_friend`, `paraphrase`. |
| `question` | The text sent to retrieval and generation. |
| `expected_answer` | Reference answer for the judge and human review; `null` when unanswerable. |
| `relevant[]` | Pages that answer the question: `document_id`, `page_number`, optional `span` (`start_offset`, `end_offset` in page text). |
| `required_facts[]` | `id`, `alternatives` (accepted phrasings) and `acceptable_pages`. Used by answer scoring. |
| `forbidden_phrases[]` | Text that must not appear in an answer (injected or false-friend content). |
| `reviewed` | `true` only after a person checked the question, answer and labels against the source pages. |

## Labelling rules enforced by the validator

- Relevance is labelled by document and page, never by chunk ID. A span narrows a
  label to a passage: a retrieved chunk counts only if its offsets overlap the span.
- `unanswerable` cases have no relevant pages, no facts and a `null` expected answer.
- Answerable cases need an expected answer, at least one relevant page and one fact.
- `factual` cases cite one document; `multi_doc` cases cite at least two.
- Every referenced page exists, spans fit inside the page, and IDs are unique.
- Each fact's acceptable pages are listed as relevant, and at least one alternative
  appears verbatim (case-insensitive) on one of those pages. Translations for
  non-English questions are allowed as extra alternatives.
- A `baseline` needs 30–40 cases, at least 5 `unanswerable` and 3 `multi_doc` cases,
  every case reviewed and retrieval thresholds set. These minimums live in code.

## Retrieval metrics

The corpus is chunked with the dataset's settings into a temporary SQLite index and
each question runs through the production `search_chunks`.

- **Hit rate@k**: share of answerable cases with at least one relevant page in the top k.
- **Recall@k**: mean, per case, of relevant pages found / relevant pages labelled.
- **MRR@k**: mean of 1 / rank of the first relevant chunk (0 when none).
- Denominator: answerable cases (`factual` + `multi_doc`), also reported per type.
- **Unanswerable match rate**: share of unanswerable cases that returned any match.
  BM25 has no abstention, so this is reported but never gated; refusal is scored by
  the answer evaluation.
- A search error marks that case as a miss, records it under failures and fails the
  run. Cases are never skipped.
- `threshold_status` is `passed`, `failed` or `not_set`. A dataset without
  thresholds never reports `passed`.

## Run reports

`make eval-offline` (or `python -m ai_knowledge_platform.evaluation [DATASET]`)
writes `<run_id>.json` and `<run_id>.md` to `services/api/evals/results/`, which
git ignores. The run ID is `<UTC timestamp>-<dataset name>-<random hex>`.

The JSON report holds `report_schema_version`, `run` (run ID, mode, start time,
duration, git commit and dirty flag, dataset name, stage, path and SHA-256, model),
`configuration`, `retrieval` (aggregate, per-type, unanswerable and per-case results)
and `failures`. It contains questions and metrics but no page text, secrets or
environment values. `--validate-only` checks the contract and writes nothing.

Exit codes: `0` passed or no thresholds, `1` thresholds failed or a case errored,
`2` invalid dataset.

## Datasets

| File | Stage | Contents |
|---|---|---|
| `evals/v2_fixture.json` | draft | v1 fixture corpus, 14 cases (8 factual, 2 multi_doc, 4 unanswerable). Not reviewed and not a publishable corpus. |

First offline run of the fixture (k=3, chunk 180, overlap 30): Hit rate, Recall and
MRR 0.80 over 10 answerable cases. Lexical retrieval misses the paraphrase and the
Spanish question over English text, which v1 did not test. 2 of 4 unanswerable cases
returned matches. These are draft numbers, not a baseline.

## Not done yet

- A reviewed `baseline` dataset over a publishable corpus (needs the corpus decision).
- Answer scoring, judge rubric and calibration on v2, and live mode in the same
  command. Today live answers still run through `make eval-answers` on `answers_v1`.
