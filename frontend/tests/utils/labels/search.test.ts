/**
 * Ensure the search-result-row view-model helpers keep chip text to
 * 1-2 words, hide the default "Published" chip, and apply the same
 * neutral "Blocked" override as the record page. Split from the
 * former `tests/utils/labels.test.ts` to mirror
 * `src/utils/labels/search.ts` (module-code-structure-limits).
 */
import { describe, expect, it } from "vitest";

import {
  approvalDisplayLabel,
  candidateBranchText,
  searchApprovalStateLabel,
  searchErratumStatusLabel,
  searchRecordStateLabel,
} from "@/utils/labels";
import type { ApprovalStateCode } from "@/types/records";

describe("searchRecordStateLabel", () => {
  it("hides the chip for a published record (the default state)", () => {
    expect(searchRecordStateLabel("published")).toBeNull();
  });

  it("shows a short, uncluttered 'Candidate' chip without the branch", () => {
    const label = searchRecordStateLabel("candidate");
    expect(label?.text).toBe("Candidate");
    expect(label?.color).toBe("info");
  });
});

describe("candidateBranchText", () => {
  it("returns null for a published record", () => {
    expect(candidateBranchText("published", "main")).toBeNull();
  });

  it("returns null for a candidate with no ref", () => {
    expect(candidateBranchText("candidate", undefined)).toBeNull();
  });

  it("formats the branch once for a candidate with a ref", () => {
    expect(candidateBranchText("candidate", "feature-x")).toBe(
      "Branch: feature-x",
    );
  });
});

describe("searchApprovalStateLabel", () => {
  it("keeps 'Pending approval' visible but strips its colour " +
    "(decision 2)", () => {
    const label = searchApprovalStateLabel("pending");
    expect(label.text).toBe("Pending approval");
    expect(label.color).toBeUndefined();
  });

  it("keeps strong colour for issues and rejection", () => {
    expect(searchApprovalStateLabel("rejected").color).toBe("error");
    expect(searchApprovalStateLabel("changed_since_acceptance").color).toBe(
      "warning",
    );
    expect(searchApprovalStateLabel("policy_missing").color).toBe("warning");
  });

  it("drops the candidate/published suffix kept by approvalStateLabel", () => {
    expect(searchApprovalStateLabel("accepted").text).toBe("Accepted");
  });

  it.each([
    ["accepted", "Accepted"],
    ["pending", "Pending approval"],
    ["rejected", "Rejected"],
    ["changed_since_acceptance", "Changed"],
    ["not_required", "Not required"],
    ["policy_missing", "No policy"],
  ] as [ApprovalStateCode, string][])(
    "keeps every chip's visible text to 1-2 words: %s -> %s",
    (state, expected) => {
      const label = searchApprovalStateLabel(state);
      expect(label.text).toBe(expected);
      expect(label.text.split(" ").length).toBeLessThanOrEqual(2);
    },
  );

  it("carries the full meaning in ariaLabel whenever text is shortened", () => {
    expect(searchApprovalStateLabel("changed_since_acceptance").ariaLabel).toBe(
      "Changed since acceptance",
    );
    expect(searchApprovalStateLabel("not_required").ariaLabel).toBe(
      "Approval not required",
    );
    expect(searchApprovalStateLabel("policy_missing").ariaLabel).toBe(
      "Approval policy not configured",
    );
  });

  it("shows the same neutral 'Blocked' as the record page when the " +
    "content is not approvable (R-02)", () => {
    const states: ApprovalStateCode[] = ["pending", "policy_missing"];
    for (const state of states) {
      const label = searchApprovalStateLabel(state, false);
      expect(label).toEqual(
        approvalDisplayLabel({ state, approvable: false }, "published"),
      );
      expect(label.text).toBe("Blocked");
      expect(label.color).toBeUndefined();
    }
  });
});

describe("searchErratumStatusLabel", () => {
  it("keeps 'Reported' (the erratum pending-equivalent) neutral", () => {
    const label = searchErratumStatusLabel("pending");
    expect(label.text).toBe("Reported");
    expect(label.color).toBeUndefined();
  });

  it("drops the 'Proposed (branch …)' suffix kept by " +
    "erratumStatusLabel", () => {
    expect(searchErratumStatusLabel("accepted").text).toBe("Verified");
  });

  it.each([
    ["pending", "Reported"],
    ["accepted", "Verified"],
    ["rejected", "Rejected"],
    ["changed_since_acceptance", "Changed"],
    ["not_required", "Not required"],
  ] as [ApprovalStateCode, string][])(
    "keeps every chip's visible text to 1-2 words: %s -> %s",
    (state, expected) => {
      const label = searchErratumStatusLabel(state);
      expect(label.text).toBe(expected);
      expect(label.text.split(" ").length).toBeLessThanOrEqual(2);
    },
  );

  it("shows the neutral 'Blocked' instead of 'Reported' when the " +
    "content is not approvable (R-02)", () => {
    const label = searchErratumStatusLabel("pending", false);
    expect(label.text).toBe("Blocked");
    expect(label.color).toBeUndefined();
  });

  it("keeps strong colour for issues and rejection only", () => {
    expect(searchErratumStatusLabel("rejected").color).toBe("error");
    expect(searchErratumStatusLabel("changed_since_acceptance").color).toBe(
      "warning",
    );
  });
});
