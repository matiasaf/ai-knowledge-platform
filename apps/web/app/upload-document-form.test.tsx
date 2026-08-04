import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiResult, StoredDocument } from "@/lib/api";
import { UploadDocumentForm } from "./upload-document-form";

vi.mock("@/lib/api", () => ({ uploadDocument: vi.fn() }));

// Imported after the mock so the test drives the same function the component calls.
const { uploadDocument } = await import("@/lib/api");
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

function pdfFile(name = "handbook.pdf"): File {
  return new File([new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])], name, {
    type: "application/pdf",
  });
}

/** A promise the test resolves by hand, so the in-flight state can be asserted. */
function deferred(): {
  promise: Promise<ApiResult<StoredDocument>>;
  resolve: (value: ApiResult<StoredDocument>) => void;
} {
  let resolve!: (value: ApiResult<StoredDocument>) => void;
  const promise = new Promise<ApiResult<StoredDocument>>((res) => {
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
  uploadDocumentMock.mockReset();
});

describe("UploadDocumentForm", () => {
  it("starts idle with nothing submittable and no result on screen", () => {
    render(<UploadDocumentForm />);

    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByRole("region", { name: "Stored" })).not.toBeInTheDocument();
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
    const pending = deferred();
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
      expect(screen.getByRole("region", { name: "Stored" })).toBeInTheDocument();
    });
  });

  it("reports the stored document and clears the field for the next upload", async () => {
    uploadDocumentMock.mockResolvedValue({ ok: true, data: STORED_DOCUMENT });
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());
    await userEvent.click(submitButton());

    const result = await screen.findByRole("region", { name: "Stored" });
    expect(result).toHaveTextContent("handbook.pdf");
    expect(result).toHaveTextContent("2.0 KB");
    expect(result).toHaveTextContent(STORED_DOCUMENT.id);

    expect(fileInput().files).toHaveLength(0);
    expect(submitButton()).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("status")).toHaveTextContent("");
  });

  it("moves focus to the result on success so the outcome is the next thing read", async () => {
    uploadDocumentMock.mockResolvedValue({ ok: true, data: STORED_DOCUMENT });
    render(<UploadDocumentForm />);

    await userEvent.upload(fileInput(), pdfFile());
    await userEvent.click(submitButton());

    await waitFor(() => {
      expect(screen.getByRole("region", { name: "Stored" })).toHaveFocus();
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
    expect(screen.queryByRole("region", { name: "Stored" })).not.toBeInTheDocument();
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
});
