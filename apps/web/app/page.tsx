import styles from "./page.module.css";
import { UploadDocumentForm } from "./upload-document-form";

const IMPLEMENTED = [
  "PDF uploads validated by declared media type and by the %PDF- file signature",
  "A configurable size limit enforced while the upload streams, in bounded chunks",
  "Each accepted file stored under a generated identifier with a metadata sidecar",
  "Bounded text extraction that keeps one-based page provenance and records empty pages",
  "Structured API errors with stable codes that this UI renders as real states",
];

const NOT_IMPLEMENTED = [
  "OCR for scanned pages without a text layer",
  "Chunking, embeddings and retrieval",
  "Answers with verifiable citations",
  "Retrieval and answer evaluations",
  "Latency, token, cost and failure observability",
];

export default function Home() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>AI Knowledge Platform</p>
        <h1 className={styles.title}>Evidence-first knowledge for teams</h1>
        <p className={styles.lede}>
          Ingest trusted documents, ask questions about them, and get grounded answers with
          citations you can verify against the source. This build stores trusted PDFs and extracts
          text page by page, without pretending retrieval exists yet.
        </p>
      </header>

      <UploadDocumentForm />

      <section aria-labelledby="scope-heading" className={styles.scope}>
        <h2 className={styles.scopeHeading} id="scope-heading">
          Current scope
        </h2>
        <div className={styles.scopeColumns}>
          <div>
            <h3 className={styles.scopeTitle}>Working today</h3>
            <ul className={styles.list}>
              {IMPLEMENTED.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className={styles.scopeTitle}>Not built yet</h3>
            <ul className={styles.list}>
              {NOT_IMPLEMENTED.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </main>
  );
}
