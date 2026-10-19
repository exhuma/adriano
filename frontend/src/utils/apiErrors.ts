/**
 * Shared helpers for turning an `ApiError` into user-facing text,
 * for the authorization-specific cases every read/write view needs
 * to handle the same way (module-ux-principles "Write recovery
 * messages for humans").
 */
import { ApiError } from "@/api";

/**
 * Read the `detail` string out of an error body shaped
 * `{detail, code?}`, when present.
 *
 * :param error: An `ApiError` from a failed `api.*` call.
 * :returns: The server-provided detail, or `undefined`.
 */
export function errorDetail(error: ApiError): string | undefined {
  const data = error.data;
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : undefined;
  }
  return undefined;
}

/**
 * Whether *error* is a 403 from a missing permission.
 *
 * :param error: Caught value, typically from an `api.*` call.
 * :returns: `true` for an `ApiError` with `status === 403`.
 */
export function isForbidden(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 403;
}

/**
 * A generic "no access" message naming the missing permission (the
 * backend's own `detail` already does this, e.g. "the 'read'
 * permission is required; ask an administrator for a role that
 * grants it") without naming any specific person.
 *
 * :param error: A 403 `ApiError` (see `isForbidden`).
 * :returns: The message to show.
 */
export function forbiddenText(error: ApiError): string {
  return (
    errorDetail(error) ??
    "You don't have permission to do this. Ask an administrator for a " +
      "role that grants it."
  );
}

/**
 * Whether *error* signals the backend cannot authenticate anyone
 * right now (no auth configured, or the IdP is unreachable).
 *
 * :param error: Caught value, typically from an `api.*` call.
 * :returns: `true` for an `ApiError` with `status === 503`.
 */
export function isAuthUnavailable(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 503;
}
