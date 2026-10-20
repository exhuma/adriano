/**
 * Ensure the unified-diff line classifier labels header, hunk,
 * added, removed, and context lines correctly, so the diff panel can
 * render per-line +/- prefixes (and colour only as an enhancement)
 * without re-parsing the text itself; and ensure
 * `hasComparableRevision` only reports a comparable revision when
 * the page knows a digest other than the current one (R-08).
 */
import { describe, expect, it } from "vitest";

import { classifyDiffLines, hasComparableRevision } from "@/utils/diff";

describe("classifyDiffLines", () => {
  it("returns an empty array for empty input", () => {
    expect(classifyDiffLines("")).toEqual([]);
  });

  it("classifies header, hunk, added, removed, and context lines", () => {
    const text = [
      "--- a (base)",
      "+++ b (target)",
      "@@ -1,2 +1,2 @@",
      " unchanged line",
      "-old line",
      "+new line",
      "",
    ].join("\n");

    const lines = classifyDiffLines(text);

    expect(lines).toEqual([
      { kind: "header", text: "--- a (base)" },
      { kind: "header", text: "+++ b (target)" },
      { kind: "hunk", text: "@@ -1,2 +1,2 @@" },
      { kind: "context", text: " unchanged line" },
      { kind: "removed", text: "-old line" },
      { kind: "added", text: "+new line" },
    ]);
  });

  it("drops only the single trailing empty line from a final newline", () => {
    const lines = classifyDiffLines("+added\n");
    expect(lines).toEqual([{ kind: "added", text: "+added" }]);
  });
});

describe("hasComparableRevision", () => {
  const none = {
    current: "sha256-v1:cur",
    previous: null,
    history: [],
    others: [],
  };

  it("is false when the page knows no other digest", () => {
    expect(hasComparableRevision(none)).toBe(false);
  });

  it("is false when the only decision is on the current digest", () => {
    expect(
      hasComparableRevision({ ...none, history: ["sha256-v1:cur"] }),
    ).toBe(false);
  });

  it("is true with a previous digest", () => {
    expect(
      hasComparableRevision({ ...none, previous: "sha256-v1:old" }),
    ).toBe(true);
  });

  it("is true with a decision on another digest", () => {
    expect(
      hasComparableRevision({ ...none, history: ["sha256-v1:old"] }),
    ).toBe(true);
  });

  it("is true with a sibling or competing candidate digest", () => {
    expect(
      hasComparableRevision({ ...none, others: ["sha256-v1:other"] }),
    ).toBe(true);
  });
});
