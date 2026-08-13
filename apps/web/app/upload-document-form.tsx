"use client";

import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import {
  type DocumentExtraction,
  extractDocument,
  type StoredDocument,
  uploadDocument,
} from "@/lib/api";
import styles from "./upload-document-form.module.css";

type UploadState =
  | { status: "idle" }
  | { status: "uploading"; filename: string }
  | { status: "processing"; document: StoredDocument }
  | { status: "extracted"; extraction: DocumentExtraction }
  | { status: "upload-error"; message: string }
  | { status: "extraction-error"; document: StoredDocument; message: string };

export function UploadDocumentForm() {
  const fileInputId = useId();
  const hintId = useId();
  const resultHeadingId = useId();
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const isWorking = state.status === "uploading" || state.status === "processing";

  useEffect(() => {
    // Focus moves forward only on success, where the result is the next thing to read.
    // Failures keep focus on the form so a different file can be chosen immediately;
    // role="alert" announces them without stealing the caret.
    if (state.status === "extracted") {
      resultRef.current?.focus();
    }
  }, [state]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedFile === null || isWorking) {
      return;
    }

    setState({ status: "uploading", filename: selectedFile.name });
    const result = await uploadDocument(selectedFile);

    if (result.ok) {
      setSelectedFile(null);
      if (fileInputRef.current !== null) {
        fileInputRef.current.value = "";
      }
      await runExtraction(result.data);
      return;
    }
    setState({ status: "upload-error", message: result.error.message });
  }

  async function runExtraction(document: StoredDocument) {
    setState({ status: "processing", document });
    const result = await extractDocument(document.id);
    if (result.ok) {
      setState({ status: "extracted", extraction: result.data });
      return;
    }
    setState({ status: "extraction-error", document, message: result.error.message });
  }

  async function handleExtractionRetry() {
    if (state.status === "extraction-error") {
      await runExtraction(state.document);
    }
  }

  return (
    <section aria-labelledby="upload-heading" className={styles.panel}>
      <h2 className={styles.heading} id="upload-heading">
        Add a source document
      </h2>

      <form aria-busy={isWorking} className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={fileInputId}>
            PDF document
          </label>
          <input
            accept="application/pdf,.pdf"
            aria-describedby={hintId}
            className={styles.input}
            disabled={isWorking}
            id={fileInputId}
            name="file"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            ref={fileInputRef}
            type="file"
          />
          <p className={styles.hint} id={hintId}>
            PDF only. The API validates the file signature and rejects anything above its configured
            limits, 10 MB and 250 pages by default.
          </p>
        </div>

        {/*
          aria-disabled rather than disabled: the button is the element that holds focus
          when a submit starts, and disabling a focused element drops focus to the body.
          Screen readers still announce it as unavailable, and handleSubmit is the guard.
        */}
        <button
          aria-disabled={selectedFile === null || isWorking}
          className={styles.submit}
          type="submit"
        >
          {state.status === "uploading"
            ? "Uploading…"
            : state.status === "processing"
              ? "Extracting text…"
              : "Upload document"}
        </button>
      </form>

      <p aria-live="polite" className={styles.liveRegion} role="status">
        {state.status === "uploading"
          ? `Uploading ${state.filename}…`
          : state.status === "processing"
            ? `Extracting text from ${state.document.filename}, page by page…`
            : ""}
      </p>

      {state.status === "upload-error" && (
        <p className={styles.error} role="alert">
          <span className={styles.resultLabel}>Upload failed</span>
          {state.message}
        </p>
      )}

      {state.status === "extraction-error" && (
        <section aria-labelledby={resultHeadingId} className={styles.result}>
          <h3 className={styles.resultLabel} id={resultHeadingId}>
            Stored — extraction failed
          </h3>
          <DocumentDetails document={state.document} />
          <p className={styles.extractionError} role="alert">
            {state.message}
          </p>
          <button className={styles.secondaryAction} onClick={handleExtractionRetry} type="button">
            Retry text extraction
          </button>
        </section>
      )}

      {state.status === "extracted" && (
        // A named region so that receiving focus announces what this is, rather than
        // reading out the first line of content with no context.
        <section
          aria-labelledby={resultHeadingId}
          className={styles.result}
          ref={resultRef}
          tabIndex={-1}
        >
          <h3 className={styles.resultLabel} id={resultHeadingId}>
            Text extracted
          </h3>
          <DocumentDetails document={state.extraction.document} />
          <dl className={styles.extractionSummary}>
            <div>
              <dt>Pages</dt>
              <dd>{state.extraction.pageCount}</dd>
            </div>
            <div>
              <dt>Pages without text</dt>
              <dd>{state.extraction.emptyPageCount}</dd>
            </div>
          </dl>
          {state.extraction.pages.length > 0 && (
            <div className={styles.previews}>
              <h4 className={styles.previewHeading}>Page provenance preview</h4>
              <ol className={styles.pageList}>
                {state.extraction.pages.slice(0, 3).map((page) => (
                  <li className={styles.page} key={page.pageNumber}>
                    <span className={styles.pageLabel}>Page {page.pageNumber}</span>
                    <pre className={styles.pageText}>
                      {page.text.trim() ? page.text : "No extractable text on this page."}
                    </pre>
                  </li>
                ))}
              </ol>
            </div>
          )}
          <p className={styles.resultNote}>
            The original PDF is unchanged. Extracted text is stored with its page number; it has not
            been chunked or indexed yet.
          </p>
        </section>
      )}
    </section>
  );
}

function DocumentDetails({
  document,
}: {
  document: StoredDocument | DocumentExtraction["document"];
}) {
  return (
    <dl className={styles.details}>
      <dt>File</dt>
      <dd>{document.filename}</dd>
      <dt>Size</dt>
      <dd>{formatBytes(document.byteSize)}</dd>
      <dt>Document ID</dt>
      <dd className={styles.identifier}>{document.id}</dd>
    </dl>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const kilobytes = bytes / 1024;
  if (kilobytes < 1024) {
    return `${kilobytes.toFixed(1)} KB`;
  }
  return `${(kilobytes / 1024).toFixed(1)} MB`;
}
