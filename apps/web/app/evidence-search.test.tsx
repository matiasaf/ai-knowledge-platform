import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiResult, RetrievalSearch } from "@/lib/api";
import { EvidenceSearch } from "./evidence-search";

vi.mock("@/lib/api", () => ({ searchEvidence: vi.fn() }));

const { searchEvidence } = await import("@/lib/api");
const searchEvidenceMock = vi.mocked(searchEvidence);

const SEARCH_RESULT: RetrievalSearch = {
  query: "annual leave",
  matchCount: 1,
  matches: [
    {
      rank: 1,
      documentId: "3f6b1c2e-0f5a-4d21-9f4b-1c0f4a2b7d88",
      filename: "handbook.pdf",
      pageNumber: 2,
      chunkIndex: 0,
      text: "Leave requests are submitted in the people portal.",
      startOffset: 80,
      endOffset: 130,
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

function queryInput(): HTMLInputElement {
  return screen.getByRole("searchbox", { name: "Question or keywords" });
}

function submitButton(): HTMLElement {
  return screen.getByRole("button", { name: /find evidence|searching/i });
}

beforeEach(() => {
  searchEvidenceMock.mockReset();
});

describe("EvidenceSearch", () => {
  it("starts empty and does not submit a one-character query", async () => {
    render(<EvidenceSearch />);

    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    await userEvent.type(queryInput(), "a");
    await userEvent.click(submitButton());

    expect(searchEvidenceMock).not.toHaveBeenCalled();
  });

  it("renders ranked excerpts with document and page provenance", async () => {
    searchEvidenceMock.mockResolvedValue({ ok: true, data: SEARCH_RESULT });
    render(<EvidenceSearch />);

    await userEvent.type(queryInput(), "  annual leave  ");
    await userEvent.click(submitButton());

    const results = await screen.findByRole("region", { name: "Evidence for “annual leave”" });
    expect(results).toHaveTextContent("#1");
    expect(results).toHaveTextContent("handbook.pdf");
    expect(results).toHaveTextContent("Page 2");
    expect(results).toHaveTextContent("Leave requests are submitted in the people portal.");
    expect(results).toHaveTextContent("3f6b1c2e-0f5a-4d21-9f4b-1c0f4a2b7d88");
    expect(results).toHaveFocus();
    expect(searchEvidenceMock).toHaveBeenCalledWith("annual leave");
  });

  it("announces progress and refuses duplicate searches in flight", async () => {
    const pending = deferred<RetrievalSearch>();
    searchEvidenceMock.mockReturnValue(pending.promise);
    render(<EvidenceSearch />);

    await userEvent.type(queryInput(), "security policy");
    await userEvent.click(submitButton());

    expect(screen.getByRole("status")).toHaveTextContent("Searching for “security policy”");
    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(submitButton());
    expect(searchEvidenceMock).toHaveBeenCalledTimes(1);

    pending.resolve({ ok: true, data: { query: "security policy", matchCount: 0, matches: [] } });
    await waitFor(() => {
      expect(screen.getByText(/retrieval miss/i)).toBeInTheDocument();
    });
  });

  it("renders API failures as an alert", async () => {
    searchEvidenceMock.mockResolvedValue({
      ok: false,
      error: { code: "network_error", message: "The API could not be reached." },
    });
    render(<EvidenceSearch />);

    await userEvent.type(queryInput(), "security policy");
    await userEvent.click(submitButton());

    expect(await screen.findByRole("alert")).toHaveTextContent("The API could not be reached.");
  });
});
