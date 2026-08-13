/**
 * Client for the AI Knowledge Platform API.
 *
 * Failures are returned as values rather than thrown: every call site has to render
 * an error state anyway, and a discriminated union makes forgetting one a type error.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type DocumentStatus = "stored" | "processing" | "extracted" | "extraction_failed";

export interface ApiDocument {
  id: string;
  filename: string;
  byteSize: number;
  contentType: string;
  status: DocumentStatus;
  createdAt: string;
  updatedAt: string;
}

export type StoredDocument = ApiDocument & { status: "stored" };

export interface ExtractedPage {
  pageNumber: number;
  text: string;
  characterCount: number;
}

export interface DocumentExtraction {
  document: ApiDocument & { status: "extracted" };
  pageCount: number;
  emptyPageCount: number;
  pages: ExtractedPage[];
  extractedAt: string;
}

export interface ApiFailure {
  code: string;
  message: string;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiFailure };

const GENERIC_FAILURE: ApiFailure = {
  code: "unexpected_error",
  message: "The upload could not be completed. Please try again.",
};

const GENERIC_EXTRACTION_FAILURE: ApiFailure = {
  code: "unexpected_error",
  message: "Text extraction could not be completed. The original PDF is still stored.",
};

const NETWORK_FAILURE: ApiFailure = {
  code: "network_error",
  message: "The API could not be reached. Check that it is running and try again.",
};

export async function uploadDocument(file: File): Promise<ApiResult<StoredDocument>> {
  const body = new FormData();
  body.append("file", file);

  let response: Response;
  try {
    // Content-Type is intentionally unset: the browser adds the multipart boundary.
    response = await fetch(`${API_BASE_URL}/documents`, { method: "POST", body });
  } catch {
    return { ok: false, error: NETWORK_FAILURE };
  }

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    return { ok: false, error: parseFailure(payload) ?? GENERIC_FAILURE };
  }

  const document = parseDocument(payload);
  return document?.status === "stored"
    ? { ok: true, data: { ...document, status: "stored" } }
    : { ok: false, error: GENERIC_FAILURE };
}

export async function extractDocument(documentId: string): Promise<ApiResult<DocumentExtraction>> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/extraction`,
      {
        method: "POST",
      },
    );
  } catch {
    return { ok: false, error: NETWORK_FAILURE };
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    return { ok: false, error: parseFailure(payload) ?? GENERIC_EXTRACTION_FAILURE };
  }

  const extraction = parseExtraction(payload);
  return extraction
    ? { ok: true, data: extraction }
    : { ok: false, error: GENERIC_EXTRACTION_FAILURE };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * Only render server text that arrived in the documented envelope; anything else
 * falls back to our own copy so an unexpected response cannot leak into the UI.
 */
function parseFailure(payload: unknown): ApiFailure | null {
  if (!isRecord(payload) || !isRecord(payload.error)) {
    return null;
  }
  const { code, message } = payload.error;
  if (typeof code !== "string" || typeof message !== "string") {
    return null;
  }
  return { code, message };
}

function parseDocument(payload: unknown): ApiDocument | null {
  if (!isRecord(payload)) {
    return null;
  }
  const { id, filename, byte_size, content_type, status, created_at, updated_at } = payload;
  if (
    typeof id !== "string" ||
    typeof filename !== "string" ||
    typeof byte_size !== "number" ||
    typeof content_type !== "string" ||
    !isDocumentStatus(status) ||
    typeof created_at !== "string" ||
    typeof updated_at !== "string"
  ) {
    return null;
  }
  return {
    id,
    filename,
    byteSize: byte_size,
    contentType: content_type,
    status,
    createdAt: created_at,
    updatedAt: updated_at,
  };
}

function parseExtraction(payload: unknown): DocumentExtraction | null {
  if (!isRecord(payload) || !Array.isArray(payload.pages)) {
    return null;
  }
  const { document: rawDocument, page_count, empty_page_count, pages, extracted_at } = payload;
  const document = parseDocument(rawDocument);
  const parsedPages = pages.map(parseExtractedPage);
  if (
    document?.status !== "extracted" ||
    typeof page_count !== "number" ||
    !Number.isInteger(page_count) ||
    page_count < 0 ||
    typeof empty_page_count !== "number" ||
    !Number.isInteger(empty_page_count) ||
    empty_page_count < 0 ||
    empty_page_count > page_count ||
    typeof extracted_at !== "string" ||
    parsedPages.some((page) => page === null) ||
    page_count !== parsedPages.length
  ) {
    return null;
  }

  const validatedPages = parsedPages as ExtractedPage[];
  if (validatedPages.some((page, index) => page.pageNumber !== index + 1)) {
    return null;
  }
  return {
    document: { ...document, status: "extracted" },
    pageCount: page_count,
    emptyPageCount: empty_page_count,
    pages: validatedPages,
    extractedAt: extracted_at,
  };
}

function parseExtractedPage(payload: unknown): ExtractedPage | null {
  if (!isRecord(payload)) {
    return null;
  }
  const { page_number, text, character_count } = payload;
  if (
    typeof page_number !== "number" ||
    !Number.isInteger(page_number) ||
    page_number < 1 ||
    typeof text !== "string" ||
    typeof character_count !== "number" ||
    !Number.isInteger(character_count) ||
    character_count !== text.length
  ) {
    return null;
  }
  return { pageNumber: page_number, text, characterCount: character_count };
}

function isDocumentStatus(value: unknown): value is DocumentStatus {
  return (
    value === "stored" ||
    value === "processing" ||
    value === "extracted" ||
    value === "extraction_failed"
  );
}
