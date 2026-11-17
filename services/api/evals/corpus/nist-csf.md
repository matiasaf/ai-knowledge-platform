# NIST CSF evaluation corpus

- Dataset: `evals/v2_nist_csf.json` (stage `draft`, 35 cases, none reviewed yet)
- Generator: `evals/corpus/build_v2_nist_csf.py`
- Selected and downloaded: 2026-11-16

This is the publishable corpus for the v2 evaluation baseline (ROADMAP deliverable 1).
It replaces the synthetic v1 fixture corpus for any result meant to be quoted.

## Sources

| Document ID | File | Publication | Pages | SHA-256 of the downloaded PDF |
|---|---|---|---|---|
| `a1f0c2d4-0001-…c5f2` | `NIST.CSWP.29.pdf` | NIST CSWP 29, *The NIST Cybersecurity Framework (CSF) 2.0*, 26 February 2024. <https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf> | 32 | `3c31f46fee98cac0c4323453e5109291a213b4de7fef8c058af9bf67f717433c` |
| `a1f0c2d4-0002-…1300` | `NIST.SP.1300.pdf` | NIST SP 1300, *NIST Cybersecurity Framework 2.0: Small Business Quick-Start Guide*, February 2024. <https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1300.pdf> | 9 | `1e77c1bd63d1e15c48c870b7c17b7c9a2edf6bd5103b0940e72828515c9f1881` |
| `a1f0c2d4-0003-…1271` | `NIST.SP.1271.pdf` | NIST SP 1271, *Getting Started with the NIST Cybersecurity Framework: A Quick Start Guide*, August 2021. <https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1271.pdf> | 3 | `f3b4436626b87fceb12cde8dd29da7432254821e3e2753103fe3500dd1f6e17d` |

SP 1271 describes CSF 1.1 (five Functions) while the other two describe CSF 2.0 (six
Functions, adding Govern). The version conflict is deliberate: it gives the dataset a
realistic contradictory-source case (`md-function-count`).

## License and permission

All three are works of the U.S. federal government prepared by NIST. Under
17 U.S.C. 105 they are not subject to copyright protection in the United States, so
they may be reproduced and published here. Attribution to NIST is kept, and no NIST
endorsement of this project is implied. Outside the United States, NIST may assert
copyright; the repository uses the text for evaluation only. The cases do not rely on
third-party figures or logos.

The PDFs themselves are not committed (uploaded documents and generated data stay out of
the repository). The dataset embeds the extracted page text, which is what the evaluator
indexes. Empty pages are omitted, so page numbers remain the PDF's physical page numbers.

## Reproducing the dataset

```bash
mkdir -p /tmp/nist-csf
curl -L -o /tmp/nist-csf/NIST.CSWP.29.pdf https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf
curl -L -o /tmp/nist-csf/NIST.SP.1300.pdf https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1300.pdf
curl -L -o /tmp/nist-csf/NIST.SP.1271.pdf https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1271.pdf
cd services/api
uv run python evals/corpus/build_v2_nist_csf.py /tmp/nist-csf
uv run python -m ai_knowledge_platform.evaluation evals/v2_nist_csf.json --validate-only
```

The generator refuses a PDF whose SHA-256 differs from the table above. If NIST
republishes a file, update the digest deliberately and re-review the affected labels.

## Review status

Every case is `reviewed: false`. Before the dataset can become a `baseline`, a person
must check each question, reference answer, relevant page and fact against the PDF
page, then flip `reviewed` in the generator, set retrieval thresholds and change the
stage. Fact alternatives are verified verbatim against page text by the validator; the
reference answers and relevance judgements are not machine-checked.

Selection notes:

- U.S. Federal Trade Commission business guides were the first choice for a second
  publisher, but `ftc.gov` rejected automated downloads on 2026-11-16, so they were
  not used.
- Spanish questions (`sb-mfa-es`, `gs-logs-es`) deliberately query English text to
  measure the lexical retriever's cross-language gap.
