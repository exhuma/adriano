/**
 * Turn a registration's `last_error` (a backend-defined JSON shape;
 * see `backend/app/services/polling.py`) into display-ready text.
 * Never falls back to raw JSON (audit finding S3): a failed poll's
 * `last_error` is normally `{"problems": [{"code", "message", ...}]}`
 * from `PollProblem.to_json()`, but older/alternate shapes
 * (`{"source_error": ...}`, `{"message": ...}`, a bare string) are
 * also handled, with a generic, still-readable fallback last.
 */
import type { ConfigErrorCode } from "@/types/sources";

/** One problem entry from a `problems[]` array, display-ready. */
export interface SourceProblemItem {
  /** Human-readable description. */
  message: string;
  /** Stable machine code, shown as secondary text when present. */
  code?: string;
}

/** How a registration's problem should be rendered. */
export type SourceProblemDisplay =
  | { kind: "none" }
  | { kind: "text"; text: string }
  | { kind: "list"; items: SourceProblemItem[] }
  | { kind: "config"; code: ConfigErrorCode | null; text: string };

const FALLBACK_TEXT = "See server logs (details unavailable).";

/** Narrow an unknown value to a plain JSON object, or `null`. */
function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/** Build one list item from an entry of a `problems[]` array. */
function toProblemItem(entry: unknown): SourceProblemItem {
  const record = asRecord(entry);
  const message = record && typeof record.message === "string"
    ? record.message
    : "Unknown problem.";
  const code = record && typeof record.code === "string" ? record.code : undefined;
  return { message, code };
}

/**
 * Describe a registration's `last_error` for display.
 *
 * :param lastError: The raw, backend-shaped error value (or `null`).
 * :returns: How to render it -- never the raw JSON.
 */
export function describeLastError(lastError: unknown): SourceProblemDisplay {
  if (lastError === null || lastError === undefined) {
    return { kind: "none" };
  }
  if (typeof lastError === "string") {
    return lastError.trim() ? { kind: "text", text: lastError } : { kind: "none" };
  }
  const record = asRecord(lastError);
  if (!record) {
    return { kind: "text", text: FALLBACK_TEXT };
  }
  if (Array.isArray(record.problems) && record.problems.length > 0) {
    return { kind: "list", items: record.problems.map(toProblemItem) };
  }
  if (typeof record.source_error === "string") {
    return { kind: "text", text: record.source_error };
  }
  if (typeof record.message === "string") {
    return { kind: "text", text: record.message };
  }
  return { kind: "text", text: FALLBACK_TEXT };
}
