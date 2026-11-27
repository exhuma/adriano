/** Tests for the shared query-string builder. */
import { describe, expect, it } from "vitest";

import { toQueryString } from "@/api/query";

describe("toQueryString", () => {
  it("Ensure empty, null, undefined and false values are dropped", () => {
    expect(
      toQueryString({ a: "", b: undefined, c: null, d: false, e: "x" }),
    ).toBe("?e=x");
  });

  it("Ensure true, zero and numbers are kept as strings", () => {
    expect(toQueryString({ a: true, b: 0, c: 2 })).toBe("?a=true&b=0&c=2");
  });

  it("Ensure no params give an empty string", () => {
    expect(toQueryString({})).toBe("");
  });

  it("Ensure values are URL-encoded", () => {
    expect(toQueryString({ q: "a b/c" })).toBe("?q=a+b%2Fc");
  });
});
