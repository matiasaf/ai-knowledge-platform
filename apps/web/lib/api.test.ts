import { afterEach, describe, expect, it, vi } from "vitest";
import { extractDocument, uploadDocument } from "@/lib/api";

const STORED_RESPONSE = {
  id: "3f6b1c2e-0f5a-4d21-9f4b-1c0f4a2b7d88",
  filename: "handbook.pdf",
  byte_size: 2048,
  content_type: "application/pdf",
  status: "stored",
  created_at: "2026-08-04T10:00:00Z",
  updated_at: "2026-08-04T10:00:00Z",
};

const EXTRACTION_RESPONSE = {
  document: {
    ...STORED_RESPONSE,
    status: "extracted",
    updated_at: "2026-08-04T10:00:01Z",
  },
  page_count: 2,
  empty_page_count: 1,
  pages: [
    { page_number: 1, text: "Policy alpha\n", character_count: 13 },
    { page_number: 2, text: "", character_count: 0 },
  ],
  extracted_at: "2026-08-04T10:00:01Z",
};

function pdfFile(name = "handbook.pdf"): File {
  return new File([new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])], name, {
    type: "application/pdf",
  });
}

function mockFetch(body: unknown, status: number): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async () =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("uploadDocument", () => {
  it("maps a stored document onto the client-side shape", async () => {
    mockFetch(STORED_RESPONSE, 201);

    const result = await uploadDocument(pdfFile());

    expect(result).toEqual({
      ok: true,
      data: {
        id: STORED_RESPONSE.id,
        filename: "handbook.pdf",
        byteSize: 2048,
        contentType: "application/pdf",
        status: "stored",
        createdAt: STORED_RESPONSE.created_at,
        updatedAt: STORED_RESPONSE.updated_at,
      },
    });
  });

  it("posts multipart form data without setting Content-Type by hand", async () => {
    const fetchMock = mockFetch(STORED_RESPONSE, 201);

    await uploadDocument(pdfFile());

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/documents$/);
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    // The browser must generate the multipart boundary; supplying the header breaks it.
    expect(init.headers).toBeUndefined();
  });

  it("surfaces the code and message from the API error envelope", async () => {
    mockFetch({ error: { code: "invalid_pdf", message: "File content is not a PDF." } }, 422);

    const result = await uploadDocument(pdfFile("spoofed.pdf"));

    expect(result).toEqual({
      ok: false,
      error: { code: "invalid_pdf", message: "File content is not a PDF." },
    });
  });

  it("falls back to its own copy when a failure payload is not the documented envelope", async () => {
    mockFetch({ detail: "<script>alert(1)</script>" }, 500);

    const result = await uploadDocument(pdfFile());

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe("unexpected_error");
      expect(result.error.message).not.toContain("script");
    }
  });

  it("rejects a success payload whose shape does not match the contract", async () => {
    mockFetch({ ...STORED_RESPONSE, byte_size: "2048" }, 201);

    const result = await uploadDocument(pdfFile());

    expect(result.ok).toBe(false);
  });

  it("reports a network failure when the request never completes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );

    const result = await uploadDocument(pdfFile());

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe("network_error");
    }
  });
});

describe("extractDocument", () => {
  it("maps page text and its one-based provenance onto the client shape", async () => {
    const fetchMock = mockFetch(EXTRACTION_RESPONSE, 200);

    const result = await extractDocument(STORED_RESPONSE.id);

    expect(result).toEqual({
      ok: true,
      data: {
        document: {
          id: STORED_RESPONSE.id,
          filename: "handbook.pdf",
          byteSize: 2048,
          contentType: "application/pdf",
          status: "extracted",
          createdAt: STORED_RESPONSE.created_at,
          updatedAt: EXTRACTION_RESPONSE.document.updated_at,
        },
        pageCount: 2,
        emptyPageCount: 1,
        pages: [
          { pageNumber: 1, text: "Policy alpha\n", characterCount: 13 },
          { pageNumber: 2, text: "", characterCount: 0 },
        ],
        extractedAt: EXTRACTION_RESPONSE.extracted_at,
      },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(new RegExp(`/documents/${STORED_RESPONSE.id}/extraction$`)),
      { method: "POST" },
    );
  });

  it("surfaces an extraction error while ignoring undocumented failure shapes", async () => {
    mockFetch({ error: { code: "encrypted_pdf", message: "A password is required." } }, 422);
    expect(await extractDocument(STORED_RESPONSE.id)).toEqual({
      ok: false,
      error: { code: "encrypted_pdf", message: "A password is required." },
    });

    mockFetch({ detail: "parser internals" }, 500);
    const malformed = await extractDocument(STORED_RESPONSE.id);
    expect(malformed.ok).toBe(false);
    if (!malformed.ok) {
      expect(malformed.error.message).not.toContain("parser internals");
    }
  });

  it("rejects page arrays whose provenance or character count is inconsistent", async () => {
    mockFetch(
      {
        ...EXTRACTION_RESPONSE,
        pages: [{ page_number: 2, text: "Policy alpha", character_count: 999 }],
        page_count: 1,
      },
      200,
    );

    const result = await extractDocument(STORED_RESPONSE.id);

    expect(result.ok).toBe(false);
  });
});
