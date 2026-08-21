import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiResult, GroundedAnswer as GroundedAnswerResult } from "@/lib/api";
import { GroundedAnswer } from "./grounded-answer";

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, answerQuestion: vi.fn() };
});

const { answerQuestion } = await import("@/lib/api");
const answerQuestionMock = vi.mocked(answerQuestion);

const ANSWER: GroundedAnswerResult = {
  question: "How soon must a lost device be reported?",
  outcome: "answered",
  claims: [
    {
      text: "A lost device must be reported within one hour.",
      citationIds: ["C1"],
    },
  ],
  citations: [
    {
      id: "C1",
      documentId: "22222222-2222-4222-8222-222222222222",
      filename: "security-runbook.pdf",
      pageNumber: 1,
      chunkIndex: 0,
      startOffset: 0,
      endOffset: 58,
      excerpt: "A lost company device must be reported within one hour.",
      sourcePath: "/documents/22222222-2222-4222-8222-222222222222/content",
    },
  ],
};

function deferred<T>(): {
  promise: Promise<ApiResult<T>>;
  resolve: (result: ApiResult<T>) => void;
} {
  let resolve!: (result: ApiResult<T>) => void;
  const promise = new Promise<ApiResult<T>>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
}

function questionInput(): HTMLInputElement {
  return screen.getByRole("textbox", { name: "Question" });
}

function submitButton(): HTMLElement {
  return screen.getByRole("button", { name: /get grounded answer|checking/i });
}

beforeEach(() => {
  answerQuestionMock.mockReset();
});

describe("GroundedAnswer", () => {
  it("does not submit a one-character question", async () => {
    render(<GroundedAnswer />);

    await userEvent.type(questionInput(), "a");
    await userEvent.click(submitButton());

    expect(answerQuestionMock).not.toHaveBeenCalled();
    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
  });

  it("renders claims, accessible citation markers and a page-addressed source", async () => {
    answerQuestionMock.mockResolvedValue({ ok: true, data: ANSWER });
    render(<GroundedAnswer />);

    await userEvent.type(questionInput(), `  ${ANSWER.question}  `);
    await userEvent.click(submitButton());

    const result = await screen.findByRole("region", {
      name: `Answer to “${ANSWER.question}”`,
    });
    expect(result).toHaveTextContent("reported within one hour");
    expect(screen.getByRole("link", { name: "Source 1" })).toHaveAttribute("href", "#citation-C1");
    expect(
      screen.getByRole("link", {
        name: "Open security-runbook.pdf, page 1, in the source PDF",
      }),
    ).toHaveAttribute("href", expect.stringMatching(/\/content#page=1$/));
    expect(result).toHaveFocus();
    expect(answerQuestionMock).toHaveBeenCalledWith(ANSWER.question);
  });

  it("announces pending work and prevents a duplicate request", async () => {
    const pending = deferred<GroundedAnswerResult>();
    answerQuestionMock.mockReturnValue(pending.promise);
    render(<GroundedAnswer />);

    await userEvent.type(questionInput(), "What is the policy?");
    await userEvent.click(submitButton());

    expect(screen.getByRole("status")).toHaveTextContent("Finding evidence and checking an answer");
    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(submitButton());
    expect(answerQuestionMock).toHaveBeenCalledTimes(1);

    pending.resolve({
      ok: true,
      data: {
        question: "What is the policy?",
        outcome: "insufficient_evidence",
        claims: [],
        citations: [],
      },
    });
    await waitFor(() => {
      expect(screen.getByText(/do not provide enough evidence/i)).toBeInTheDocument();
    });
  });

  it("renders safety refusal without pretending it is insufficient evidence", async () => {
    answerQuestionMock.mockResolvedValue({
      ok: true,
      data: {
        question: "Question?",
        outcome: "safety_refused",
        claims: [],
        citations: [],
      },
    });
    render(<GroundedAnswer />);

    await userEvent.type(questionInput(), "Question?");
    await userEvent.click(submitButton());

    expect(
      await screen.findByText(/declined this request for safety reasons/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/do not provide enough evidence/i)).not.toBeInTheDocument();
  });

  it("shows configuration and network failures as an alert", async () => {
    answerQuestionMock.mockResolvedValue({
      ok: false,
      error: {
        code: "generation_not_configured",
        message: "Answer generation is not configured for this API.",
      },
    });
    render(<GroundedAnswer />);

    await userEvent.type(questionInput(), "What is the policy?");
    await userEvent.click(submitButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Answer generation is not configured",
    );
    expect(questionInput()).toHaveValue("What is the policy?");
  });
});
