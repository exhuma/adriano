/**
 * Ensure a registration's `last_error` is always turned into
 * readable text, never raw JSON (audit finding S3): a `problems[]`
 * array becomes a list of messages with their code as secondary
 * text, `source_error`/`message` shapes are read directly, and any
 * other shape falls back to a generic, still-readable sentence.
 */
import { describe, expect, it } from "vitest";

import { describeLastError } from "@/utils/sourceErrors";

describe("describeLastError", () => {
  it("returns none for null or undefined", () => {
    expect(describeLastError(null)).toEqual({ kind: "none" });
    expect(describeLastError(undefined)).toEqual({ kind: "none" });
  });

  it("reads a bare string as text", () => {
    expect(describeLastError("disk full")).toEqual({
      kind: "text",
      text: "disk full",
    });
  });

  it("turns a problems[] array into a list with code as secondary text", () => {
    const result = describeLastError({
      problems: [
        { code: "source_error", message: "fake source is down" },
        { code: "fetch_failed", message: "could not fetch", path: "a.md" },
      ],
    });
    expect(result).toEqual({
      kind: "list",
      items: [
        { message: "fake source is down", code: "source_error" },
        { message: "could not fetch", code: "fetch_failed" },
      ],
    });
  });

  it("reads a source_error field directly", () => {
    expect(describeLastError({ source_error: "connection refused" })).toEqual({
      kind: "text",
      text: "connection refused",
    });
  });

  it("reads a message field directly", () => {
    expect(describeLastError({ message: "boom" })).toEqual({
      kind: "text",
      text: "boom",
    });
  });

  it("never renders raw JSON for an unrecognised shape", () => {
    const result = describeLastError({ weird: { nested: [1, 2, 3] } });
    expect(result.kind).toBe("text");
    expect(result).toEqual({
      kind: "text",
      text: "See server logs (details unavailable).",
    });
    if (result.kind === "text") {
      expect(result.text).not.toContain("{");
      expect(result.text).not.toContain("weird");
    }
  });

  it("falls back for a non-object, non-string value", () => {
    expect(describeLastError(42)).toEqual({
      kind: "text",
      text: "See server logs (details unavailable).",
    });
  });
});
