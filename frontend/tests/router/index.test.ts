/**
 * Ensure the record routes address an ADR by UUID alone and a
 * candidate by UUID plus ref, and that a ref containing slashes
 * round-trips through the candidate route.
 */
import { describe, expect, it } from "vitest";

import router from "@/router";
import { candidatePath, recordPath } from "@/utils/recordPaths";

const UUID = "22222222-2222-2222-2222-222222222222";

describe("record routes", () => {
  it("routes /records/:uuid to the ADR page", () => {
    const resolved = router.resolve(`/records/${UUID}`);

    expect(resolved.name).toBe("record");
    expect(resolved.params.uuid).toBe(UUID);
  });

  it("routes a candidate path to the candidate page with the ref intact", () => {
    const resolved = router.resolve(`/records/${UUID}/candidates/feature/x`);

    expect(resolved.name).toBe("record-candidate");
    expect(resolved.params.uuid).toBe(UUID);
    expect(resolved.params.ref).toBe("feature/x");
  });

  it("round-trips a ref with slashes and reserved characters", () => {
    const path = candidatePath(UUID, "feature/a b#1");
    const resolved = router.resolve(path);

    expect(path).toBe(`/records/${UUID}/candidates/feature/a%20b%231`);
    expect(resolved.params.ref).toBe("feature/a b#1");
  });

  it("opens a candidate on its own page and a published row on the ADR page", () => {
    expect(recordPath(UUID, { kind: "candidate", ref: "feature/x" })).toBe(
      `/records/${UUID}/candidates/feature/x`,
    );
    expect(recordPath(UUID, { kind: "published", ref: "main" })).toBe(
      `/records/${UUID}`,
    );
    expect(recordPath(UUID)).toBe(`/records/${UUID}`);
  });
});
