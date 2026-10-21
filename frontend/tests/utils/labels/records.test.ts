/**
 * Ensure the record-identity view-model helpers label published/
 * candidate state and the derived lifecycle status. Split from the
 * former `tests/utils/labels.test.ts` to mirror
 * `src/utils/labels/records.ts` (module-code-structure-limits).
 */
import { describe, expect, it } from "vitest";

import { displayStatusLabel, recordStateLabel } from "@/utils/labels";
import type { DisplayStatus } from "@/types/records";

describe("recordStateLabel", () => {
  it("labels published records without a ref", () => {
    expect(recordStateLabel("published").text).toBe("Published");
  });

  it("includes the ref for a candidate", () => {
    expect(recordStateLabel("candidate", "feature-branch").text).toBe(
      "Candidate (feature-branch)",
    );
  });

  it("falls back to a plain label when no ref is given", () => {
    expect(recordStateLabel("candidate").text).toBe("Candidate");
  });
});

describe("displayStatusLabel", () => {
  it.each([
    ["active", "Active"],
    ["updated", "Updated"],
    ["obsoleted", "Obsoleted"],
  ] as [DisplayStatus, string][])("labels %s as %s", (status, expected) => {
    const label = displayStatusLabel(status);
    expect(label.text).toBe(expected);
    expect(label.icon).toBeTruthy();
  });
});
