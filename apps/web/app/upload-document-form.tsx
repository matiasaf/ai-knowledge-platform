"use client";

import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { type StoredDocument, uploadDocument } from "@/lib/api";
import styles from "./upload-document-form.module.css";

/**
 * The states the ingestion slice can actually be in. There is deliberately no
 * "processing" or "ready" member: nothing parses or indexes the file yet.
 */
type UploadState =
  | { status: "idle" }
  | { status: "uploading"; filename: string }
  | { status: "stored"; document: StoredDocument }
  | { status: "error"; message: string };

export function UploadDocumentForm() {
  const fileInputId = useId();
  const hintId = useId();
  const resultHeadingId = useId();
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const isUploading = state.status === "uploading";

  useEffect(() => {
    // Focus moves forward only on success, where the result is the next thing to read.
    // Failures keep focus on the form so a different file can be chosen immediately;
    // role="alert" announces them without stealing the caret.
    if (state.status === "stored") {
      resultRef.current?.focus();
    }
  }, [state]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedFile === null || isUploading) {
      return;
    }

    setState({ status: "uploading", filename: selectedFile.name });
    const result = await uploadDocument(selectedFile);

    if (result.ok) {
      setState({ status: "stored", document: result.data });
      setSelectedFile(null);
      if (fileInputRef.current !== null) {
        fileInputRef.current.value = "";
      }
      return;
    }
    setState({ status: "error", message: result.error.message });
  }

  return (
    <section aria-labelledby="upload-heading" className={styles.panel}>
      <h2 className={styles.heading} id="upload-heading">
        Add a source document
      </h2>

      <form aria-busy={isUploading} className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={fileInputId}>
            PDF document
          </label>
          <input
            accept="application/pdf,.pdf"
            aria-describedby={hintId}
            className={styles.input}
            disabled={isUploading}
            id={fileInputId}
            name="file"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            ref={fileInputRef}
            type="file"
          />
          <p className={styles.hint} id={hintId}>
            PDF only. The API validates the file signature and rejects anything above its configured
            size limit, 10 MB by default.
          </p>
        </div>

        {/*
          aria-disabled rather than disabled: the button is the element that holds focus
          when a submit starts, and disabling a focused element drops focus to the body.
          Screen readers still announce it as unavailable, and handleSubmit is the guard.
        */}
        <button
          aria-disabled={selectedFile === null || isUploading}
          className={styles.submit}
          type="submit"
        >
          {isUploading ? "Uploading…" : "Upload document"}
        </button>
      </form>

      <p aria-live="polite" className={styles.liveRegion} role="status">
        {isUploading ? `Uploading ${state.filename}…` : ""}
      </p>

      {state.status === "error" && (
        <p className={styles.error} role="alert">
          <span className={styles.resultLabel}>Upload failed</span>
          {state.message}
        </p>
      )}

      {state.status === "stored" && (
        // A named region so that receiving focus announces what this is, rather than
        // reading out the first line of content with no context.
        <section
          aria-labelledby={resultHeadingId}
          className={styles.result}
          ref={resultRef}
          tabIndex={-1}
        >
          <h3 className={styles.resultLabel} id={resultHeadingId}>
            Stored
          </h3>
          <dl className={styles.details}>
            <dt>File</dt>
            <dd>{state.document.filename}</dd>
            <dt>Size</dt>
            <dd>{formatBytes(state.document.byteSize)}</dd>
            <dt>Document ID</dt>
            <dd className={styles.identifier}>{state.document.id}</dd>
          </dl>
          <p className={styles.resultNote}>
            The file is saved and unmodified. It has not been parsed, chunked or indexed yet.
          </p>
        </section>
      )}
    </section>
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
