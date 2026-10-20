/**
 * Ensure every approval/status/issue view-model helper always pairs
 * an icon with text (never colour alone) and produces the exact
 * labels specified for the search and record detail pages.
 */
import { describe, expect, it } from "vitest";

import {
  approvalStateExplanation,
  approvalStateLabel,
  candidateBranchText,
  decisionActionLabel,
  displayStatusLabel,
  divergenceLabel,
  errataHeaderLinkText,
  errataHeadingText,
  erratumStatusLabel,
  erratumTypeLabel,
  issueIndicatorLabel,
  pluralizeErrata,
  pollStatusLabel,
  recordStateLabel,
  searchApprovalStateLabel,
  searchErratumStatusLabel,
  searchRecordStateLabel,
} from "@/utils/labels";
import type { DivergenceKind, PolicyStatus } from "@/types/approval";
import type { ApprovalStateCode, DisplayStatus, ErrataSummaryOut } from "@/types/records";
import type { PollStatus } from "@/types/sources";

function errataSummary(overrides: Partial<ErrataSummaryOut> = {}): ErrataSummaryOut {
  return { total: 0, verified: 0, reported: 0, rejected: 0, changed: 0, proposed: 0, ...overrides };
}

describe("approvalStateLabel", () => {
  it("distinguishes accepted candidates from accepted published records", () => {
    expect(approvalStateLabel("accepted", "candidate").text).toBe(
      "Accepted — candidate",
    );
    expect(approvalStateLabel("accepted", "published").text).toBe(
      "Accepted — published",
    );
  });

  it.each([
    ["pending", "Pending approval"],
    ["rejected", "Rejected"],
    ["changed_since_acceptance", "Changed since acceptance"],
    ["not_required", "Approval not required"],
    ["policy_missing", "Approval policy not configured"],
  ] as [ApprovalStateCode, string][])(
    "labels %s as %s",
    (state, expected) => {
      const label = approvalStateLabel(state, "published");
      expect(label.text).toBe(expected);
      expect(label.icon).toBeTruthy();
    },
  );

  it("every state has an icon, so status is never colour-only", () => {
    const states: ApprovalStateCode[] = [
      "policy_missing",
      "not_required",
      "accepted",
      "rejected",
      "changed_since_acceptance",
      "pending",
    ];
    for (const state of states) {
      const label = approvalStateLabel(state, "published");
      expect(label.icon.length).toBeGreaterThan(0);
      expect(label.text.length).toBeGreaterThan(0);
    }
  });
});

describe("approvalStateExplanation", () => {
  it("distinguishes an unconfigured policy from an ordinary pending review", () => {
    expect(approvalStateExplanation("policy_missing", "missing")).toContain(
      "No approval policy is configured",
    );
    expect(approvalStateExplanation("pending", "configured")).toBe(
      "Awaiting review.",
    );
  });

  it("flags an invalid policy distinctly from a missing one", () => {
    expect(approvalStateExplanation("policy_missing", "invalid")).toContain(
      "invalid",
    );
  });

  it.each([
    ["rejected", "configured", "Rejected for this exact content."],
    [
      "changed_since_acceptance",
      "configured",
      "Changed since acceptance — the accepted version differs from the " +
        "current content.",
    ],
    ["not_required", "configured", "Approval not required by policy."],
    ["accepted", "configured", "Accepted for this exact content."],
  ] as [ApprovalStateCode, PolicyStatus, string][])(
    "explains %s as %s",
    (state, policyStatus, expected) => {
      expect(approvalStateExplanation(state, policyStatus)).toBe(expected);
    },
  );

  it("every state has a non-empty explanation", () => {
    const states: ApprovalStateCode[] = [
      "policy_missing",
      "not_required",
      "accepted",
      "rejected",
      "changed_since_acceptance",
      "pending",
    ];
    for (const state of states) {
      expect(approvalStateExplanation(state, "configured").length).toBeGreaterThan(0);
    }
  });

  it("uses erratum wording when recordKind is 'erratum'", () => {
    expect(approvalStateExplanation("pending", "configured", "erratum")).toBe(
      "This erratum is reported and awaits verification.",
    );
    expect(approvalStateExplanation("accepted", "configured", "erratum")).toBe(
      "This erratum was verified for this exact content.",
    );
    expect(approvalStateExplanation("rejected", "configured", "erratum")).toBe(
      "This erratum was rejected for this exact content.",
    );
  });

  it("still flags a missing policy the same way for an erratum", () => {
    expect(
      approvalStateExplanation("policy_missing", "missing", "erratum"),
    ).toContain("No approval policy is configured");
  });
});

describe("erratumStatusLabel", () => {
  it.each([
    ["pending", "Reported"],
    ["policy_missing", "Reported"],
    ["accepted", "Verified"],
    ["rejected", "Rejected"],
    ["changed_since_acceptance", "Changed since verification"],
    ["not_required", "Published (no review required)"],
  ] as [ApprovalStateCode, string][])(
    "labels a published erratum's %s state as %s",
    (state, expected) => {
      const label = erratumStatusLabel(state, "published");
      expect(label.text).toBe(expected);
      expect(label.icon.length).toBeGreaterThan(0);
    },
  );

  it("appends a 'Proposed (branch …)' suffix for a candidate erratum", () => {
    const label = erratumStatusLabel("pending", "candidate", "feature-x");
    expect(label.text).toBe("Reported — Proposed (branch feature-x)");
  });

  it("falls back to a plain 'Proposed' suffix without a ref", () => {
    const label = erratumStatusLabel("pending", "candidate");
    expect(label.text).toBe("Reported — Proposed");
  });
});

describe("erratumTypeLabel", () => {
  it.each([
    ["technical", "Technical"],
    ["editorial", "Editorial"],
  ] as const)("labels %s as %s", (type, expected) => {
    expect(erratumTypeLabel(type).text).toBe(expected);
  });

  it("labels a missing type as 'Type not set'", () => {
    expect(erratumTypeLabel(null).text).toBe("Type not set");
  });
});

describe("decisionActionLabel", () => {
  it("labels accepted and rejected with distinct icon+text", () => {
    expect(decisionActionLabel("accepted").text).toBe("Accepted");
    expect(decisionActionLabel("rejected").text).toBe("Rejected");
    expect(decisionActionLabel("accepted").icon).not.toBe(
      decisionActionLabel("rejected").icon,
    );
  });

  it("defaults to the plain decision wording when recordKind is omitted", () => {
    expect(decisionActionLabel("accepted").text).toBe("Accepted");
    expect(decisionActionLabel("accepted", "decision").text).toBe(
      "Accepted",
    );
  });

  it("labels an accepted erratum 'Verified' (RFC vocabulary)", () => {
    expect(decisionActionLabel("accepted", "erratum").text).toBe(
      "Verified",
    );
  });

  it("keeps 'Rejected' for an erratum's rejected action", () => {
    expect(decisionActionLabel("rejected", "erratum").text).toBe(
      "Rejected",
    );
  });
});

describe("divergenceLabel", () => {
  it.each([
    "published_not_accepted",
    "published_differs",
  ] as DivergenceKind[])("labels %s with an icon and text", (kind) => {
    const label = divergenceLabel(kind);
    expect(label.icon.length).toBeGreaterThan(0);
    expect(label.text.length).toBeGreaterThan(0);
  });
});

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

describe("pollStatusLabel", () => {
  it.each([
    ["never", "Never polled"],
    ["ok", "OK"],
    ["partial", "Partial"],
    ["failed", "Failed"],
    ["disabled", "Disabled"],
  ] as [PollStatus, string][])("labels %s as %s when not stale", (status, expected) => {
    expect(pollStatusLabel(status, false).text).toBe(expected);
  });

  it("appends a stale marker for a stale non-failed status", () => {
    const label = pollStatusLabel("ok", true);
    expect(label.text).toContain("stale");
    expect(label.color).toBe("warning");
  });

  it("does not duplicate the failure state when stale and failed", () => {
    const label = pollStatusLabel("failed", true);
    expect(label.text).toBe("Failed");
  });
});

describe("issueIndicatorLabel", () => {
  it("returns null when there are no issues", () => {
    expect(issueIndicatorLabel({ error: 0, warning: 0 })).toBeNull();
  });

  it("summarises a single error with an accessible count", () => {
    const label = issueIndicatorLabel({ error: 1, warning: 0 });
    expect(label?.text).toBe("1 error");
    expect(label?.color).toBe("error");
  });

  it("pluralizes multiple warnings and errors together", () => {
    const label = issueIndicatorLabel({ error: 2, warning: 3 });
    expect(label?.text).toBe("2 errors, 3 warnings");
    expect(label?.color).toBe("error");
  });

  it("uses the warning colour when there are only warnings", () => {
    const label = issueIndicatorLabel({ error: 0, warning: 1 });
    expect(label?.text).toBe("1 warning");
    expect(label?.color).toBe("warning");
  });
});

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
  it("keeps 'Pending approval' visible but strips its colour (decision 2)", () => {
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
});

describe("searchErratumStatusLabel", () => {
  it("keeps 'Reported' (the erratum pending-equivalent) neutral", () => {
    const label = searchErratumStatusLabel("pending");
    expect(label.text).toBe("Reported");
    expect(label.color).toBeUndefined();
  });

  it("drops the 'Proposed (branch …)' suffix kept by erratumStatusLabel", () => {
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

  it("keeps strong colour for issues and rejection only", () => {
    expect(searchErratumStatusLabel("rejected").color).toBe("error");
    expect(searchErratumStatusLabel("changed_since_acceptance").color).toBe(
      "warning",
    );
  });
});

describe("pluralizeErrata", () => {
  it("is singular for exactly one", () => {
    expect(pluralizeErrata(1)).toBe("erratum");
  });

  it("is plural for zero or more than one", () => {
    expect(pluralizeErrata(0)).toBe("errata");
    expect(pluralizeErrata(2)).toBe("errata");
  });
});

describe("errataHeaderLinkText", () => {
  it("is null when there are no errata at all", () => {
    expect(errataHeaderLinkText(errataSummary())).toBeNull();
  });

  it("counts published errata, singular for one", () => {
    expect(errataHeaderLinkText(errataSummary({ total: 1 }))).toBe("1 erratum");
  });

  it("counts published errata, plural for more than one", () => {
    expect(errataHeaderLinkText(errataSummary({ total: 2 }))).toBe("2 errata");
  });

  it("falls back to the proposed count when nothing is published yet", () => {
    expect(errataHeaderLinkText(errataSummary({ proposed: 1 }))).toBe(
      "1 proposed erratum",
    );
    expect(errataHeaderLinkText(errataSummary({ proposed: 2 }))).toBe(
      "2 proposed errata",
    );
  });

  it("prefers the published count when both are present", () => {
    expect(errataHeaderLinkText(errataSummary({ total: 1, proposed: 1 }))).toBe(
      "1 erratum",
    );
  });
});

describe("errataHeadingText", () => {
  it("never shows a bare '(0)' -- omits the published half when it is zero", () => {
    expect(errataHeadingText(0, 1)).toBe("Errata — 1 proposed");
  });

  it("omits the proposed half when it is zero", () => {
    expect(errataHeadingText(2, 0)).toBe("Errata — 2 errata");
  });

  it("joins both halves when both counts are positive", () => {
    expect(errataHeadingText(1, 1)).toBe("Errata — 1 erratum · 1 proposed");
  });
});
