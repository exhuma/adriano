/**
 * Ensure the validation-issue view-model helpers summarise error/
 * warning counts accessibly and give every stable issue code a
 * distinct, plain-language headline (P11-R-07: never a literal
 * backtick/code-span marker). Split from the former
 * `tests/utils/labels.test.ts` to mirror `src/utils/labels/issues.ts`
 * (module-code-structure-limits).
 */
import { describe, expect, it } from "vitest";

import {
  issueCodeLabel,
  issueIndicatorLabel,
  validationIssueText,
} from "@/utils/labels";
import type { IssueCode } from "@/types/records";

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

describe("issueCodeLabel", () => {
  const codes: IssueCode[] = [
    "bad_yaml",
    "missing_frontmatter",
    "missing_uuid",
    "bad_uuid",
    "bad_date",
    "missing_date",
    "unknown_field",
    "bad_field_type",
    "duplicate_uuid",
    "missing_target",
    "ambiguous_target",
    "legacy_alias",
    "legacy_signoff",
    "corrects_on_non_erratum",
    "erratum_without_target",
    "bad_encoding",
    "bad_erratum_type",
    "erratum_missing_corrected_text",
    "erratum_unknown_section_heading",
    "erratum_duplicate_section",
    "erratum_targets_itself",
    "erratum_relationship_ignored",
    "erratum_target_is_erratum",
    "legacy_erratum_format",
    "obsolete_kind_field",
  ];

  it.each(codes)("gives a non-empty headline for every code: %s", (code) => {
    expect(issueCodeLabel(code).length).toBeGreaterThan(0);
  });

  it("gives every code a distinct headline", () => {
    const headlines = new Set(codes.map((code) => issueCodeLabel(code)));
    expect(headlines.size).toBe(codes.length);
  });

  it("never uses a literal backtick/code-span marker (P11-R-07)", () => {
    for (const code of codes) {
      expect(issueCodeLabel(code)).not.toContain("`");
    }
  });
});

describe("validationIssueText", () => {
  it("prefixes the backend message with the code's plain-language " +
    "headline", () => {
    const text = validationIssueText(
      "obsolete_kind_field",
      "`kind` is no longer used: a document is an erratum when it has " +
        "`erratum-for`. Remove `kind: decision`.",
    );
    expect(text).toContain("Remove `kind: decision`.");
    expect(text.startsWith(issueCodeLabel("obsolete_kind_field"))).toBe(true);
  });
});
