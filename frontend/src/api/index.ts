/**
 * Central fetch-based HTTP client (module-vue-vuetify "HTTP client").
 *
 * Every API call in the application goes through `api.get` /
 * `api.post` / `api.put` / `api.delete` so that authentication
 * headers, the 401 handler, and error shaping live in exactly one
 * place. No component calls `fetch` directly.
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

/** Supplies the bearer token to attach to outgoing API requests. */
export interface TokenProvider {
  /**
   * Returns the current access token, or `null` when
   * unauthenticated.
   *
   * May be asynchronous: the OIDC-backed provider calls
   * `UserManager.getUser()`, which returns a `Promise` (it may read
   * through to storage). A synchronous provider (e.g. one that holds
   * a plain in-memory token, such as the dev-login provider) may
   * still return the value directly -- callers always `await` the
   * result either way.
   */
  getToken(): string | null | Promise<string | null>;
}

/** Default provider: no authentication is wired up yet. */
const noopTokenProvider: TokenProvider = {
  getToken: () => null,
};

let tokenProvider: TokenProvider = noopTokenProvider;

/**
 * Install the active token provider.
 *
 * Real tokens arrive in a later phase (OIDC, `oidc-client-ts`); until
 * then the default provider always returns `null` and no
 * `Authorization` header is sent. Tokens are kept in memory by the
 * provider, never in `localStorage`.
 *
 * :param provider: Implementation to use for subsequent requests.
 */
export function setTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
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

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = await tokenProvider.getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401) {
    unauthorizedHandler?.();
  } else if (response.ok) {
    authSuccessHandler?.();
  }

  const data = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, data);
  }
  return data as T;
}

/** Fetch-based client with a uniform error and auth seam. */
export const api = {
  /**
   * Issue a GET request.
   *
   * :param path: Request path, appended to the configured API base
   *     URL (e.g. ``/api/v1/records``).
   * :returns: The parsed JSON (or text) response body.
   */
  get: <T>(path: string): Promise<T> => request<T>("GET", path),

  /**
   * Issue a POST request.
   *
   * :param path: Request path, appended to the configured API base
   *     URL.
   * :param body: Optional JSON-serializable request body.
   * :returns: The parsed JSON (or text) response body.
   */
  post: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>("POST", path, body),

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
   * Issue a DELETE request.
   *
   * :param path: Request path, appended to the configured API base
   *     URL.
   * :returns: The parsed JSON (or text) response body.
   */
  delete: <T>(path: string): Promise<T> => request<T>("DELETE", path),
};
