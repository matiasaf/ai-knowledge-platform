/**
 * Client for the AI Knowledge Platform API.
 *
 * Failures are returned as values rather than thrown: every call site has to render
 * an error state anyway, and a discriminated union makes forgetting one a type error.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Mirrors the only status the API can currently report. */
export type DocumentStatus = "stored";

export interface StoredDocument {
  id: string;
  filename: string;
  byteSize: number;
  contentType: string;
  status: DocumentStatus;
  createdAt: string;
  updatedAt: string;
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
  return document ? { ok: true, data: document } : { ok: false, error: GENERIC_FAILURE };
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

function parseDocument(payload: unknown): StoredDocument | null {
  if (!isRecord(payload)) {
    return null;
  }
  const { id, filename, byte_size, content_type, status, created_at, updated_at } = payload;
  if (
    typeof id !== "string" ||
    typeof filename !== "string" ||
    typeof byte_size !== "number" ||
    typeof content_type !== "string" ||
    status !== "stored" ||
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
