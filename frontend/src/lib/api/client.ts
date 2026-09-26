import { ApiError, errorFromResponse, networkError } from "./errors";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

/**
 * Endpoints that must never trigger the refresh-and-retry dance: refreshing in
 * response to a failed login would hide the real error, and refreshing in response to
 * a failed refresh would loop.
 */
const NO_RETRY_PATHS = ["/auth/login", "/auth/refresh", "/auth/logout", "/auth/signup"];

type QueryValue = string | number | boolean | null | undefined;
export type Query = Record<string, QueryValue | QueryValue[]>;

interface RequestOptions {
  query?: Query;
  signal?: AbortSignal;
  /** Set internally to stop a refreshed request from refreshing again. */
  retried?: boolean;
}

/**
 * Build a query string, dropping empty values so `?q=` never reaches the server, and
 * repeating the key for arrays (`?status=ready&status=waiting`), which is what FastAPI
 * expects for a repeatable Query parameter.
 */
export function buildQuery(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    const values = Array.isArray(value) ? value : [value];
    for (const item of values) {
      if (item === null || item === undefined || item === "") continue;
      params.append(key, String(item));
    }
  }
  const search = params.toString();
  return search ? `?${search}` : "";
}

/**
 * One in-flight refresh at a time. Several requests can fail with 401 at the same
 * moment; without this they would each rotate the refresh token, and the backend
 * treats a reused refresh token as theft and revokes every session.
 */
let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      return response.ok;
    } catch {
      return false;
    } finally {
      // Cleared in a microtask so every caller awaiting this attempt sees the result.
      queueMicrotask(() => {
        refreshInFlight = null;
      });
    }
  })();
  return refreshInFlight;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}${buildQuery(options.query)}`, {
      method,
      // The session lives in httpOnly cookies, so every call must carry them.
      credentials: "include",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: options.signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw networkError();
  }

  if (response.status === 401 && !options.retried && !NO_RETRY_PATHS.includes(path)) {
    // The access token lasts 15 minutes. Rotate it once, transparently, and retry.
    if (await refreshSession()) {
      return request<T>(method, path, body, { ...options, retried: true });
    }
  }

  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}

/**
 * The typed HTTP surface every resource module is built on. Nothing above this layer
 * calls `fetch` directly, so cookies, error shape and token refresh are handled once.
 */
export const http = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>("GET", path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, body, options),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, body, options),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>("DELETE", path, undefined, options),
};

export { ApiError };
