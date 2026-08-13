import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiResult, DocumentExtraction, DocumentIndex, StoredDocument } from "@/lib/api";
import { UploadDocumentForm } from "./upload-document-form";

vi.mock("@/lib/api", () => ({
  extractDocument: vi.fn(),
  indexDocument: vi.fn(),
  uploadDocument: vi.fn(),
}));

// Imported after the mock so the test drives the same function the component calls.
const { extractDocument, indexDocument, uploadDocument } = await import("@/lib/api");
const extractDocumentMock = vi.mocked(extractDocument);
const indexDocumentMock = vi.mocked(indexDocument);
const uploadDocumentMock = vi.mocked(uploadDocument);

const STORED_DOCUMENT: StoredDocument = {
  id: "3f6b1c2e-0f5a-4d21-9f4b-1c0f4a2b7d88",
  filename: "handbook.pdf",
  byteSize: 2048,
  contentType: "application/pdf",
  status: "stored",
  createdAt: "2026-08-04T10:00:00Z",
  updatedAt: "2026-08-04T10:00:00Z",
};

const EXTRACTION: DocumentExtraction = {
  document: {
    ...STORED_DOCUMENT,
    status: "extracted",
    updatedAt: "2026-08-04T10:00:01Z",
  },
  pageCount: 2,
  emptyPageCount: 1,
  pages: [
    { pageNumber: 1, text: "Policy alpha", characterCount: 12 },
    { pageNumber: 2, text: "", characterCount: 0 },
  ],
  extractedAt: "2026-08-04T10:00:01Z",
};

const DOCUMENT_INDEX: DocumentIndex = {
  document: {
    ...STORED_DOCUMENT,
    status: "indexed",
    updatedAt: "2026-08-04T10:00:02Z",
  },
  chunkCount: 1,
  indexedAt: "2026-08-04T10:00:02Z",
};

function pdfFile(name = "handbook.pdf"): File {
  return new File([new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])], name, {
    type: "application/pdf",
  });
}

/** A promise the test resolves by hand, so the in-flight state can be asserted. */
function deferred<T>(): {
  promise: Promise<ApiResult<T>>;
  resolve: (value: ApiResult<T>) => void;
} {
  let resolve!: (value: ApiResult<T>) => void;
  const promise = new Promise<ApiResult<T>>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

/** Queried by role alone: the label changes to "Uploading…" while a request is open. */
function submitButton(): HTMLElement {
  return screen.getByRole("button");
}

function fileInput(): HTMLInputElement {
  return screen.getByLabelText(/pdf document/i);
}

beforeEach(() => {
  extractDocumentMock.mockReset();
  extractDocumentMock.mockResolvedValue({ ok: true, data: EXTRACTION });
  indexDocumentMock.mockReset();
  indexDocumentMock.mockResolvedValue({ ok: true, data: DOCUMENT_INDEX });
  uploadDocumentMock.mockReset();
});

describe("UploadDocumentForm", () => {
  it("starts idle with nothing submittable and no result on screen", () => {
    render(<UploadDocumentForm />);

    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByRole("region", { name: "Indexed for retrieval" })).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("becomes submittable once a file is chosen", async () => {
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());

    expect(submitButton()).toHaveAttribute("aria-disabled", "false");
  });

  it("does not call the API when submitted without a file", async () => {
    render(<UploadDocumentForm />);

    await userEvent.click(submitButton());

    expect(uploadDocumentMock).not.toHaveBeenCalled();
  });

  it("announces progress and blocks resubmission while the upload is in flight", async () => {
    const pending = deferred<StoredDocument>();
    uploadDocumentMock.mockReturnValue(pending.promise);
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());
    await userEvent.click(submitButton());

    expect(screen.getByRole("status")).toHaveTextContent("Uploading handbook.pdf");
    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    expect(fileInput()).toBeDisabled();

    // A second click while in flight must not start a second request.
    await userEvent.click(submitButton());
    expect(uploadDocumentMock).toHaveBeenCalledTimes(1);

    pending.resolve({ ok: true, data: STORED_DOCUMENT });
    await waitFor(() => {
      expect(screen.getByRole("region", { name: "Indexed for retrieval" })).toBeInTheDocument();
    });
  });

  it("reports the extracted pages and clears the field for the next upload", async () => {
    uploadDocumentMock.mockResolvedValue({ ok: true, data: STORED_DOCUMENT });
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());
    await userEvent.click(submitButton());

    const result = await screen.findByRole("region", { name: "Indexed for retrieval" });
    expect(result).toHaveTextContent("handbook.pdf");
    expect(result).toHaveTextContent("2.0 KB");
    expect(result).toHaveTextContent(STORED_DOCUMENT.id);
    expect(result).toHaveTextContent("Pages2");
    expect(result).toHaveTextContent("Pages without text1");
    expect(result).toHaveTextContent("Evidence chunks1");
    expect(result).toHaveTextContent("Page 1");
    expect(result).toHaveTextContent("Policy alpha");
    expect(result).toHaveTextContent("No extractable text on this page.");
    expect(extractDocumentMock).toHaveBeenCalledWith(STORED_DOCUMENT.id);
    expect(indexDocumentMock).toHaveBeenCalledWith(STORED_DOCUMENT.id);

    expect(fileInput().files).toHaveLength(0);
    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("status")).toHaveTextContent("");
  });

  it("announces page extraction and keeps the form locked while parsing is in flight", async () => {
    const pending = deferred<DocumentExtraction>();
    uploadDocumentMock.mockResolvedValue({ ok: true, data: STORED_DOCUMENT });
    extractDocumentMock.mockReturnValue(pending.promise);
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());
    await userEvent.click(submitButton());

    expect(screen.getByRole("status")).toHaveTextContent(
      "Extracting text from handbook.pdf, page by page",
    );
    expect(submitButton()).toHaveTextContent("Extracting text");
    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    expect(fileInput()).toBeDisabled();

    pending.resolve({ ok: true, data: EXTRACTION });
    expect(
      await screen.findByRole("region", { name: "Indexed for retrieval" }),
    ).toBeInTheDocument();
  });

  it("announces evidence indexing and keeps the form locked while indexing is in flight", async () => {
    const pending = deferred<DocumentIndex>();
    uploadDocumentMock.mockResolvedValue({ ok: true, data: STORED_DOCUMENT });
    indexDocumentMock.mockReturnValue(pending.promise);
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());
    await userEvent.click(submitButton());

    expect(screen.getByRole("status")).toHaveTextContent(
      "Building searchable evidence from handbook.pdf",
    );
    expect(submitButton()).toHaveTextContent("Indexing evidence");
    expect(fileInput()).toBeDisabled();

    pending.resolve({ ok: true, data: DOCUMENT_INDEX });
    expect(
      await screen.findByRole("region", { name: "Indexed for retrieval" }),
    ).toBeInTheDocument();
  });

  it("moves focus to the result on success so the outcome is the next thing read", async () => {
    uploadDocumentMock.mockResolvedValue({ ok: true, data: STORED_DOCUMENT });
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());
    await userEvent.click(submitButton());

    await waitFor(() => {
      expect(screen.getByRole("region", { name: "Indexed for retrieval" })).toHaveFocus();
    });
  });

  it("renders a failure as an alert and never claims the document was stored", async () => {
    uploadDocumentMock.mockResolvedValue({
      ok: false,
      error: { code: "invalid_pdf", message: "File content is not a PDF." },
    });
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile("spoofed.pdf"));
    await userEvent.click(submitButton());

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("File content is not a PDF.");
    expect(screen.queryByRole("region", { name: "Indexed for retrieval" })).not.toBeInTheDocument();
    expect(extractDocumentMock).not.toHaveBeenCalled();
  });

  it("keeps focus and the chosen file on the form after a failure so it can be retried", async () => {
    uploadDocumentMock.mockResolvedValue({
      ok: false,
      error: { code: "file_too_large", message: "File exceeds the maximum upload size." },
    });
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile("large.pdf"));
    await userEvent.click(submitButton());
    await screen.findByRole("alert");

    expect(submitButton()).toHaveFocus();
    expect(fileInput().files).toHaveLength(1);
    expect(submitButton()).toHaveAttribute("aria-disabled", "false");
  });

  it("keeps an uploaded PDF and offers a retry when only extraction fails", async () => {
    uploadDocumentMock.mockResolvedValue({ ok: true, data: STORED_DOCUMENT });
    extractDocumentMock.mockResolvedValueOnce({
      ok: false,
      error: { code: "encrypted_pdf", message: "Encrypted PDFs require a password." },
    });
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile("protected.pdf"));
    await userEvent.click(submitButton());

    const result = await screen.findByRole("region", { name: "Stored — extraction failed" });
    expect(result).toHaveTextContent(STORED_DOCUMENT.id);
    expect(screen.getByRole("alert")).toHaveTextContent("Encrypted PDFs require a password.");
    expect(fileInput().files).toHaveLength(0);

    extractDocumentMock.mockResolvedValueOnce({ ok: true, data: EXTRACTION });
    await userEvent.click(screen.getByRole("button", { name: "Retry text extraction" }));

    expect(
      await screen.findByRole("region", { name: "Indexed for retrieval" }),
    ).toBeInTheDocument();
    expect(extractDocumentMock).toHaveBeenCalledTimes(2);
  });

  it("keeps extracted pages and retries when only indexing fails", async () => {
    uploadDocumentMock.mockResolvedValue({ ok: true, data: STORED_DOCUMENT });
    indexDocumentMock.mockResolvedValueOnce({
      ok: false,
      error: { code: "unexpected_error", message: "The local index is unavailable." },
    });
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());
    await userEvent.click(submitButton());

    const result = await screen.findByRole("region", {
      name: "Text extracted — indexing failed",
    });
    expect(result).toHaveTextContent(STORED_DOCUMENT.id);
    expect(screen.getByRole("alert")).toHaveTextContent("The local index is unavailable.");

    indexDocumentMock.mockResolvedValueOnce({ ok: true, data: DOCUMENT_INDEX });
    await userEvent.click(screen.getByRole("button", { name: "Retry evidence indexing" }));

    expect(
      await screen.findByRole("region", { name: "Indexed for retrieval" }),
    ).toBeInTheDocument();
    expect(indexDocumentMock).toHaveBeenCalledTimes(2);
  });
});
