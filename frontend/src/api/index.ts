/**
 * Central fetch-based HTTP client (module-vue-vuetify "HTTP client").
 *
 * Every API call in the application goes through `api.get` /
 * `api.post` / `api.put` / `api.patch` / `api.delete` so that the
 * session cookie, the CSRF header, the 401 handler, and error
 * shaping live in exactly one place. No component calls `fetch`
 * directly.
 *
 * Authentication is a server-side session (Backend-for-Frontend): the
 * browser holds only an HttpOnly cookie, sent automatically on
 * same-origin requests. The client never sees or stores a token.
 */
import { apiBaseUrl } from "@/config";

/** Error thrown for any non-2xx API response. */
export class ApiError extends Error {
  /** HTTP status code of the failed response. */
  readonly status: number;
  /** Parsed response body, if any (JSON, text, or null). */
  readonly data: unknown;

  constructor(status: number, data: unknown) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

/**
 * Register a global handler invoked whenever a request receives a
 * 401 response, so the application can redirect to login in one
 * place instead of in every call site.
 *
 * :param handler: Callback invoked with no arguments on 401.
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler;
}

type AuthSuccessHandler = () => void;
let authSuccessHandler: AuthSuccessHandler | null = null;

/**
 * Register a handler invoked after any request that previously
 * triggered the unauthorized handler succeeds again, so the
 * application can clear a stale "please sign in" banner.
 *
 * :param handler: Callback invoked with no arguments on recovery.
 */
export function setAuthSuccessHandler(handler: AuthSuccessHandler): void {
  authSuccessHandler = handler;
}

/** Parse a response body as JSON, falling back to text, then null. */
async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.length === 0) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** HTTP methods that change state and so need the CSRF header. */
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Custom header the backend requires on unsafe requests. A
 *  cross-site form or "simple" request cannot set it. */
const CSRF_HEADER = "X-Adriano-CSRF";

/** Per-request options. */
export interface RequestOptions {
  /**
   * Whether this request takes part in the re-authentication loop
   * guard (default `true`): a 401 invokes the unauthorized handler
   * and a success clears the guard. The `/auth/*` session calls
   * opt out, because "the session check succeeded" says nothing
   * about whether the API accepts the session.
   */
  trackAuth?: boolean;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  const trackAuth = options.trackAuth ?? true;
  const headers: Record<string, string> = {};
  if (UNSAFE_METHODS.has(method)) {
    headers[CSRF_HEADER] = "1";
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (trackAuth) {
    if (response.status === 401) {
      unauthorizedHandler?.();
    } else if (response.ok) {
      authSuccessHandler?.();
    }
  }

  // A 403 `csrf_failed` is deliberately not special-cased: it means
  // this client forgot the header (a bug), so it surfaces as an
  // ordinary `ApiError` instead of triggering a sign-in redirect.
  const data = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, data);
  }
  return data as T;
}

/** Fetch-based client with a uniform error and session seam. */
export const api = {
  /**
   * Issue a GET request.
   *
   * :param path: Request path, appended to the configured API base
   *     URL (e.g. ``/api/v1/records``).
   * :param options: Per-request options.
   * :returns: The parsed JSON (or text) response body.
   */
  get: <T>(path: string, options?: RequestOptions): Promise<T> =>
    request<T>("GET", path, undefined, options),

  /**
   * Issue a POST request.
   *
   * :param path: Request path, appended to the configured API base
   *     URL.
   * :param body: Optional JSON-serializable request body.
   * :param options: Per-request options.
   * :returns: The parsed JSON (or text) response body.
   */
  post: <T>(
    path: string,
    body?: unknown,
    options?: RequestOptions,
  ): Promise<T> => request<T>("POST", path, body, options),

  /**
   * Issue a PUT request.
   *
   * :param path: Request path, appended to the configured API base
   *     URL.
   * :param body: Optional JSON-serializable request body.
   * :returns: The parsed JSON (or text) response body.
   */
  put: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>("PUT", path, body),

  /**
   * Issue a PATCH request.
   *
   * :param path: Request path, appended to the configured API base
   *     URL.
   * :param body: Optional JSON-serializable request body.
   * :returns: The parsed JSON (or text) response body.
   */
  patch: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>("PATCH", path, body),

  /**
   * Issue a DELETE request.
   *
   * :param path: Request path, appended to the configured API base
   *     URL.
   * :returns: The parsed JSON (or text) response body.
   */
  delete: <T>(path: string): Promise<T> => request<T>("DELETE", path),
};
