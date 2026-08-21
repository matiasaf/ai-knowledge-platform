"use client";

import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import {
  answerQuestion,
  documentSourceUrl,
  type GroundedAnswer as GroundedAnswerResult,
} from "@/lib/api";
import styles from "./grounded-answer.module.css";

type AnswerState =
  | { status: "idle" }
  | { status: "answering"; question: string }
  | { status: "result"; answer: GroundedAnswerResult }
  | { status: "error"; message: string };

export function GroundedAnswer() {
  const inputId = useId();
  const hintId = useId();
  const resultHeadingId = useId();
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<AnswerState>({ status: "idle" });
  const resultRef = useRef<HTMLElement>(null);
  const isAnswering = state.status === "answering";
  const canSubmit = question.trim().length >= 2 && !isAnswering;

  useEffect(() => {
    if (state.status === "result") {
      resultRef.current?.focus();
    }
  }, [state]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuestion = question.trim();
    if (normalizedQuestion.length < 2 || isAnswering) {
      return;
    }

    setState({ status: "answering", question: normalizedQuestion });
    const result = await answerQuestion(normalizedQuestion);
    if (result.ok) {
      setState({ status: "result", answer: result.data });
      return;
    }
    setState({ status: "error", message: result.error.message });
  }

  return (
    <section aria-labelledby="answer-heading" className={styles.panel}>
      <div className={styles.header}>
        <p className={styles.eyebrow}>Grounded generation</p>
        <h2 className={styles.heading} id="answer-heading">
          Ask the indexed knowledge base
        </h2>
        <p className={styles.description}>
          Answers are generated only from retrieved passages. Every accepted claim links back to its
          source PDF.
        </p>
      </div>

      <form aria-busy={isAnswering} className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.label} htmlFor={inputId}>
          Question
        </label>
        <div className={styles.controls}>
          <input
            aria-describedby={hintId}
            className={styles.input}
            id={inputId}
            maxLength={500}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. How soon must a lost device be reported?"
            type="text"
            value={question}
          />
          <button aria-disabled={!canSubmit} className={styles.submit} type="submit">
            {isAnswering ? "Checking…" : "Get grounded answer"}
          </button>
        </div>
        <p className={styles.hint} id={hintId}>
          The question and up to five retrieved passages are sent to the configured provider.
        </p>
      </form>

      <p aria-live="polite" className={styles.liveRegion} role="status">
        {state.status === "answering"
          ? `Finding evidence and checking an answer for “${state.question}”…`
          : ""}
      </p>

      {state.status === "error" && (
        <p className={styles.error} role="alert">
          <strong>Answer failed.</strong> {state.message}
        </p>
      )}

      {state.status === "result" && (
        <section
          aria-labelledby={resultHeadingId}
          className={styles.result}
          ref={resultRef}
          tabIndex={-1}
        >
          <h3 className={styles.resultHeading} id={resultHeadingId}>
            Answer to “{state.answer.question}”
          </h3>
          <AnswerResult answer={state.answer} />
        </section>
      )}
    </section>
  );
}

function AnswerResult({ answer }: { answer: GroundedAnswerResult }) {
  if (answer.outcome === "insufficient_evidence") {
    return (
      <p className={styles.nonAnswer}>
        The indexed passages do not provide enough evidence to answer. Try different wording or
        index another source.
      </p>
    );
  }
  if (answer.outcome === "safety_refused") {
    return (
      <p className={styles.nonAnswer}>
        The generation provider declined this request for safety reasons. No answer was produced.
      </p>
    );
  }

  return (
    <>
      <div className={styles.claims}>
        {answer.claims.map((claim) => (
          <p key={claim.text}>
            {claim.text}{" "}
            <span className={styles.citationMarkers}>
              {claim.citationIds.map((citationId) => (
                <a
                  aria-label={`Source ${citationId.slice(1)}`}
                  href={`#citation-${citationId}`}
                  key={citationId}
                >
                  [{citationId.slice(1)}]
                </a>
              ))}
            </span>
          </p>
        ))}
      </div>

      <h4 className={styles.sourcesHeading}>Sources</h4>
      <ol className={styles.sources}>
        {answer.citations.map((citation) => (
          <li className={styles.source} id={`citation-${citation.id}`} key={citation.id}>
            <div className={styles.sourceHeader}>
              <span className={styles.sourceId}>[{citation.id.slice(1)}]</span>
              <span>{citation.filename}</span>
              <span className={styles.page}>Page {citation.pageNumber}</span>
            </div>
            <blockquote className={styles.excerpt}>{citation.excerpt}</blockquote>
            <a
              aria-label={`Open ${citation.filename}, page ${citation.pageNumber}, in the source PDF`}
              className={styles.sourceLink}
              href={documentSourceUrl(citation)}
              rel="noreferrer"
              target="_blank"
            >
              Open source PDF
            </a>
          </li>
        ))}
      </ol>
    </>
  );
}
