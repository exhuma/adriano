/** Tests for the shared URL-query readers. */
import { describe, expect, it } from "vitest";

import { readPage, readString } from "@/composables/urlQuery";

describe("readString", () => {
  it("Ensure strings pass through and anything else reads as empty", () => {
    expect(readString("a")).toBe("a");
    expect(readString(["a"])).toBe("");
    expect(readString(undefined)).toBe("");
    expect(readString(null)).toBe("");
  });
});

describe("readPage", () => {
  it("Ensure valid pages parse and invalid ones fall back to 1", () => {
    expect(readPage("3")).toBe(3);
    expect(readPage("0")).toBe(1);
    expect(readPage("-2")).toBe(1);
    expect(readPage("abc")).toBe(1);
    expect(readPage(undefined)).toBe(1);
  });
});
