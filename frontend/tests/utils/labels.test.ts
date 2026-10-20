/**
 * Ensure every approval/status/issue view-model helper always pairs
 * an icon with text (never colour alone) and produces the exact
 * labels specified for the search and record detail pages.
 */
import { describe, expect, it } from "vitest";

import {
  approvalStateExplanation,
  approvalStateLabel,
  decisionActionLabel,
  displayStatusLabel,
  divergenceLabel,
  erratumStatusLabel,
  erratumTypeLabel,
  issueIndicatorLabel,
  pollStatusLabel,
  recordStateLabel,
} from "@/utils/labels";
import type { DivergenceKind, PolicyStatus } from "@/types/approval";
import type { ApprovalStateCode, DisplayStatus } from "@/types/records";
import type { PollStatus } from "@/types/sources";

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
