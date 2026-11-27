/** Tests for the shared ref encoder and the record paths. */
import { describe, expect, it } from "vitest";

import { candidatePath, encodeRefPath } from "@/utils/recordPaths";

describe("encodeRefPath", () => {
  it("Ensure segments are encoded and slashes are kept", () => {
    expect(encodeRefPath("feature/a b#1")).toBe("feature/a%20b%231");
  });
});

describe("candidatePath", () => {
  it("Ensure the ref is encoded as a path remainder", () => {
    expect(candidatePath("u/1", "feature/a b")).toBe(
      "/records/u%2F1/candidates/feature/a%20b",
    );
  });
});
