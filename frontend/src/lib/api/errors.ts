import type { ApiErrorBody, ApiErrorDetail, ApiErrorResponse } from "@/types/api";

/**
 * Every failing request from the API arrives in one shape, so the client needs one
 * error type. `fieldErrors` flattens `details` into something a form can index by
 * field name without each page repeating the loop.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetail[];
  readonly requestId: string | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? [];
    this.requestId = body.request_id ?? null;
  }

  /** Field name to message, for inline form errors. First message per field wins. */
  get fieldErrors(): Record<string, string> {
    const errors: Record<string, string> = {};
    for (const detail of this.details) {
      if (!(detail.field in errors)) errors[detail.field] = detail.message;
    }
    return errors;
  }

  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** True when the user can fix this by changing their input. */
  get isUserFixable(): boolean {
    return this.status >= 400 && this.status < 500 && this.status !== 401;
  }
}

const NETWORK_MESSAGE =
  "Cannot reach the server. Check that the API is running on the configured address.";

export function networkError(): ApiError {
  return new ApiError(0, {
    code: "NETWORK_ERROR",
    message: NETWORK_MESSAGE,
    details: [],
    request_id: null,
  });
}

/**
 * Build an ApiError from a failed response, falling back to a generic body when the
 * server returned something that is not our error envelope (a proxy error page, say).
 */
export async function errorFromResponse(response: Response): Promise<ApiError> {
  let body: ApiErrorBody = {
    code: "UNEXPECTED_ERROR",
    message: `Request failed (${response.status}).`,
    details: [],
    request_id: response.headers.get("X-Request-ID"),
  };
  try {
    const parsed = (await response.json()) as Partial<ApiErrorResponse>;
    if (parsed.error?.code) body = { ...body, ...parsed.error };
  } catch {
    // Keep the fallback: a body that is not JSON tells us nothing more.
  }
  return new ApiError(response.status, body);
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/** A message safe to show a user, whatever was thrown. */
export function messageOf(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
