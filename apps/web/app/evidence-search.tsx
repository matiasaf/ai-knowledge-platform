"use client";

import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { type RetrievalSearch, searchEvidence } from "@/lib/api";
import styles from "./evidence-search.module.css";

type SearchState =
  | { status: "idle" }
  | { status: "searching"; query: string }
  | { status: "results"; search: RetrievalSearch }
  | { status: "error"; message: string };

export function EvidenceSearch() {
  const inputId = useId();
  const hintId = useId();
  const resultsHeadingId = useId();
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ status: "idle" });
  const resultsRef = useRef<HTMLElement>(null);
  const isSearching = state.status === "searching";
  const canSubmit = query.trim().length >= 2 && !isSearching;

  useEffect(() => {
    if (state.status === "results") {
      resultsRef.current?.focus();
    }
  }, [state]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 2 || isSearching) {
      return;
    }

    setState({ status: "searching", query: normalizedQuery });
    const result = await searchEvidence(normalizedQuery);
    if (result.ok) {
      setState({ status: "results", search: result.data });
      return;
    }
    setState({ status: "error", message: result.error.message });
  }

  return (
    <section aria-labelledby="evidence-heading" className={styles.panel}>
      <div className={styles.header}>
        <p className={styles.eyebrow}>Retrieval only</p>
        <h2 className={styles.heading} id="evidence-heading">
          Find source evidence
        </h2>
        <p className={styles.description}>
          Search indexed passages. Results are ranked excerpts, not an AI-generated answer.
        </p>
      </div>

      <form aria-busy={isSearching} className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.label} htmlFor={inputId}>
          Question or keywords
        </label>
        <div className={styles.controls}>
          <input
            aria-describedby={hintId}
            className={styles.input}
            id={inputId}
            maxLength={500}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. Where are leave requests submitted?"
            type="search"
            value={query}
          />
          <button aria-disabled={!canSubmit} className={styles.submit} type="submit">
            {isSearching ? "Searching…" : "Find evidence"}
          </button>
        </div>
        <p className={styles.hint} id={hintId}>
          Searches all documents indexed by this local API.
        </p>
      </form>

      <p aria-live="polite" className={styles.liveRegion} role="status">
        {state.status === "searching" ? `Searching for “${state.query}”…` : ""}
      </p>

      {state.status === "error" && (
        <p className={styles.error} role="alert">
          <strong>Search failed.</strong> {state.message}
        </p>
      )}

      {state.status === "results" && (
        <section
          aria-labelledby={resultsHeadingId}
          className={styles.results}
          ref={resultsRef}
          tabIndex={-1}
        >
          <h3 className={styles.resultsHeading} id={resultsHeadingId}>
            Evidence for “{state.search.query}”
          </h3>
          {state.search.matches.length === 0 ? (
            <p className={styles.empty}>
              No indexed passage matched. This is a retrieval miss; no answer was inferred.
            </p>
          ) : (
            <ol className={styles.matchList}>
              {state.search.matches.map((match) => (
                <li
                  className={styles.match}
                  key={`${match.documentId}-${match.pageNumber}-${match.chunkIndex}`}
                >
                  <div className={styles.matchHeader}>
                    <span className={styles.rank}>#{match.rank}</span>
                    <span>{match.filename}</span>
                    <span className={styles.page}>Page {match.pageNumber}</span>
                  </div>
                  <blockquote className={styles.excerpt}>{match.text}</blockquote>
                  <p className={styles.provenance}>
                    Document <code>{match.documentId}</code> · page {match.pageNumber} · chunk{" "}
                    {match.chunkIndex + 1}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </section>
  );
}
