/**
 * Ensure the approval-domain view-model helpers always pair an icon
 * with text (never colour alone) and produce the exact labels
 * specified for the record detail page. Split from the former
 * `tests/utils/labels.test.ts` to mirror `src/utils/labels/approval.ts`
 * (module-code-structure-limits).
 */
import { describe, expect, it } from "vitest";

import {
  approvalDisplayLabel,
  approvalStateExplanation,
  approvalStateLabel,
  decideBlockedLabel,
  decisionActionLabel,
  divergenceLabel,
} from "@/utils/labels";
import type {
  DecideBlockedCode,
  DivergenceKind,
  PolicyStatus,
} from "@/types/approval";
import type { ApprovalStateCode } from "@/types/records";

describe("approvalStateLabel", () => {
  it("distinguishes accepted candidates from accepted published " +
    "records", () => {
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
  it("distinguishes an unconfigured policy from an ordinary pending " +
    "review", () => {
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
      expect(
        approvalStateExplanation(state, "configured").length,
      ).toBeGreaterThan(0);
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

  it("overrides the explanation with the 'Blocked' reason when " +
    "not approvable", () => {
    expect(
      approvalStateExplanation("pending", "configured", "decision", false),
    ).toBe("This content can't be decided until its problems are fixed.");
  });

  it("stays the ordinary 'Awaiting review' when approvable defaults " +
    "true", () => {
    expect(approvalStateExplanation("pending", "configured")).toBe(
      "Awaiting review.",
    );
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

  it("defaults to the plain decision wording when recordKind is " +
    "omitted", () => {
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

describe("decideBlockedLabel", () => {
  const codes: DecideBlockedCode[] = [
    "policy_missing",
    "approval_not_required",
    "not_eligible",
    "not_approvable",
    "self_approval",
    "already_decided",
    "anonymous",
  ];

  it.each(codes)("gives a non-empty message for every code: %s", (code) => {
    expect(decideBlockedLabel(code)?.length).toBeGreaterThan(0);
  });

  it("gives the reader-facing 'not_eligible' line the short, muted " +
    "wording", () => {
    expect(decideBlockedLabel("not_eligible")).toBe(
      "Only reviewers can approve this.",
    );
  });

  it("returns null for null (the caller falls back to the raw reason)", () => {
    expect(decideBlockedLabel(null)).toBeNull();
  });
});

describe("approvalDisplayLabel", () => {
  it("shows the neutral 'Blocked' status when content is not " +
    "approvable", () => {
    const label = approvalDisplayLabel(
      { state: "pending", approvable: false },
      "published",
    );
    expect(label.text).toBe("Blocked");
    expect(label.color).toBeUndefined();
    expect(label.icon.length).toBeGreaterThan(0);
  });

  it("overrides 'Blocked' regardless of the underlying state", () => {
    const states: ApprovalStateCode[] = ["pending", "accepted", "rejected"];
    for (const state of states) {
      expect(
        approvalDisplayLabel({ state, approvable: false }, "published").text,
      ).toBe("Blocked");
    }
  });

  it("falls back to the ordinary decision label when approvable", () => {
    const label = approvalDisplayLabel(
      { state: "pending", approvable: true },
      "published",
    );
    expect(label.text).toBe("Pending approval");
  });

  it("falls back to the ordinary erratum label when approvable", () => {
    const label = approvalDisplayLabel(
      { state: "accepted", approvable: true },
      "published",
      "erratum",
    );
    expect(label.text).toBe("Verified");
  });

  it("shows 'Blocked' for an unapprovable erratum too", () => {
    const label = approvalDisplayLabel(
      { state: "pending", approvable: false },
      "published",
      "erratum",
    );
    expect(label.text).toBe("Blocked");
  });
});
