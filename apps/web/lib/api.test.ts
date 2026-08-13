import { afterEach, describe, expect, it, vi } from "vitest";
import { extractDocument, indexDocument, searchEvidence, uploadDocument } from "@/lib/api";

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

const INDEX_RESPONSE = {
  document: {
    ...STORED_RESPONSE,
    status: "indexed",
    updated_at: "2026-08-04T10:00:02Z",
  },
  chunk_count: 1,
  indexed_at: "2026-08-04T10:00:02Z",
};

const SEARCH_RESPONSE = {
  query: "annual leave",
  match_count: 1,
  matches: [
    {
      rank: 1,
      document_id: STORED_RESPONSE.id,
      filename: "handbook.pdf",
      page_number: 2,
      chunk_index: 0,
      text: "Policy alpha",
      start_offset: 10,
      end_offset: 22,
    },
  ],
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

describe("indexDocument", () => {
  it("maps indexed document metadata and posts without a request body", async () => {
    const fetchMock = mockFetch(INDEX_RESPONSE, 200);

    const result = await indexDocument(STORED_RESPONSE.id);

    expect(result).toEqual({
      ok: true,
      data: {
        document: {
          id: STORED_RESPONSE.id,
          filename: "handbook.pdf",
          byteSize: 2048,
          contentType: "application/pdf",
          status: "indexed",
          createdAt: STORED_RESPONSE.created_at,
          updatedAt: INDEX_RESPONSE.document.updated_at,
        },
        chunkCount: 1,
        indexedAt: INDEX_RESPONSE.indexed_at,
      },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(new RegExp(`/documents/${STORED_RESPONSE.id}/index$`)),
      { method: "POST" },
    );
  });

  it("rejects index metadata whose document is not indexed", async () => {
    mockFetch({ ...INDEX_RESPONSE, document: EXTRACTION_RESPONSE.document }, 200);

    expect((await indexDocument(STORED_RESPONSE.id)).ok).toBe(false);
  });
});

describe("searchEvidence", () => {
  it("posts plain language and maps ranked page evidence", async () => {
    const fetchMock = mockFetch(SEARCH_RESPONSE, 200);

    const result = await searchEvidence("annual leave", 3);

    expect(result).toEqual({
      ok: true,
      data: {
        query: "annual leave",
        matchCount: 1,
        matches: [
          {
            rank: 1,
            documentId: STORED_RESPONSE.id,
            filename: "handbook.pdf",
            pageNumber: 2,
            chunkIndex: 0,
            text: "Policy alpha",
            startOffset: 10,
            endOffset: 22,
          },
        ],
      },
    });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual({ query: "annual leave", limit: 3 });
  });

  it("rejects inconsistent result ranks and match counts", async () => {
    mockFetch(
      {
        ...SEARCH_RESPONSE,
        match_count: 2,
        matches: [{ ...SEARCH_RESPONSE.matches[0], rank: 2 }],
      },
      200,
    );

    expect((await searchEvidence("annual leave")).ok).toBe(false);
  });

  it("surfaces the documented search error envelope", async () => {
    mockFetch({ error: { code: "search_query_empty", message: "Use a letter or number." } }, 422);

    expect(await searchEvidence("--")).toEqual({
      ok: false,
      error: { code: "search_query_empty", message: "Use a letter or number." },
    });
  });
});
