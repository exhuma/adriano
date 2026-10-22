/**
 * Ensure the erratum view-model helpers use the RFC-style report/
 * verify/reject vocabulary and never render a bare "(0)" errata
 * count. Split from the former `tests/utils/labels.test.ts` to
 * mirror `src/utils/labels/errata.ts` (module-code-structure-limits).
 */
import { describe, expect, it } from "vitest";

import {
  errataHeaderLinkText,
  errataHeadingText,
  erratumStatusLabel,
  erratumTypeLabel,
  pluralizeErrata,
} from "@/utils/labels";
import type { ApprovalStateCode, ErrataSummaryOut } from "@/types/records";

function errataSummary(
  overrides: Partial<ErrataSummaryOut> = {},
): ErrataSummaryOut {
  return {
    total: 0,
    verified: 0,
    reported: 0,
    rejected: 0,
    changed: 0,
    proposed: 0,
    ...overrides,
  };
}

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

  it("appends a 'Proposed (ref …)' suffix for a candidate erratum", () => {
    const label = erratumStatusLabel("pending", "candidate", "feature-x");
    expect(label.text).toBe("Reported — Proposed (ref feature-x)");
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
  it("never shows a bare '(0)' -- omits the published half when it " +
    "is zero", () => {
    expect(errataHeadingText(0, 1)).toBe("Errata — 1 proposed");
  });

  it("omits the proposed half when it is zero", () => {
    expect(errataHeadingText(2, 0)).toBe("Errata — 2 errata");
  });

  it("joins both halves when both counts are positive", () => {
    expect(errataHeadingText(1, 1)).toBe("Errata — 1 erratum · 1 proposed");
  });
});
