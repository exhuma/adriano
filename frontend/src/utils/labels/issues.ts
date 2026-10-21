/**
 * Validation-issue view-model helpers: the record page's error/
 * warning count indicator, and plain-language headlines for every
 * stable issue code, composed with the backend's own per-instance
 * message. Split from the former
 * `utils/labels.ts` by domain (module-code-structure-limits); see
 * `index.ts`.
 */
import type { IssueCode, IssueCountsOut } from "@/types/records";

import type { StatusLabel } from "./shared";

/**
 * Summarise a record's validation issue counts for display.
 *
 * :param counts: Error and warning counts.
 * :returns: `null` when there are no issues; otherwise an
 *     icon/text/colour triple with an accessible count description.
 */
export function issueIndicatorLabel(
  counts: IssueCountsOut,
): StatusLabel | null {
  if (counts.error === 0 && counts.warning === 0) {
    return null;
  }
  const parts: string[] = [];
  if (counts.error > 0) {
    parts.push(`${counts.error} error${counts.error === 1 ? "" : "s"}`);
  }
  if (counts.warning > 0) {
    parts.push(`${counts.warning} warning${counts.warning === 1 ? "" : "s"}`);
  }
  const text = parts.join(", ");
  if (counts.error > 0) {
    return { icon: "mdi-alert-circle", text, color: "error" };
  }
  return { icon: "mdi-alert", text, color: "warning" };
}

/**
 * Plain-language headline for a stable validation issue code
 * (`IssueOut.code`). The backend's own
 * `message` is kept in full alongside it ({@link validationIssueText}
 * composes the two) -- these headlines summarise *what kind* of
 * problem the code is, while the per-instance detail (which field,
 * which UUID, which heading) only exists in the free-text message
 * the backend sends, which is never parsed to extract it. Every
 * headline is plain-worded (no literal backtick/code-span markers;
 * P11-R-07) even where the field it names looks like code.
 *
 * :param code: The stable issue code.
 * :returns: A short, human headline.
 */
export function issueCodeLabel(code: IssueCode): string {
  const headlines: Record<IssueCode, string> = {
    bad_yaml: "The file's front matter is not valid YAML",
    missing_frontmatter: "The file has no front matter block",
    missing_uuid: "The record has no UUID",
    bad_uuid: "The record's UUID is not valid",
    bad_date: "The record's date is not valid",
    missing_date: "The record has no decision date",
    unknown_field: "The front matter has a field the catalog does not use",
    bad_field_type: "A front-matter field has an unexpected value",
    duplicate_uuid: "Another record already uses this UUID",
    missing_target: "A linked record could not be found",
    ambiguous_target: "A link matches more than one record",
    legacy_alias: "This field is a legacy alias of a newer one",
    legacy_signoff: "This uses the old, unverified sign-off field",
    corrects_on_non_erratum:
      "A corrects field was used outside an erratum, which is no " +
      "longer supported",
    erratum_without_target:
      "This erratum does not say which decision it corrects",
    bad_encoding: "The file is not valid UTF-8 text",
    bad_erratum_type: "The erratum's type is missing or not recognised",
    erratum_missing_corrected_text:
      "The erratum is missing its corrected text",
    erratum_unknown_section_heading:
      "The erratum has a section heading the catalog does not recognise",
    erratum_duplicate_section: "The erratum repeats the same section twice",
    erratum_targets_itself: "An erratum can't correct itself",
    erratum_relationship_ignored:
      "A relationship field on this erratum is ignored",
    erratum_target_is_erratum:
      "This erratum corrects another erratum, which is not supported",
    legacy_erratum_format:
      "This uses the old erratum format, which is no longer supported",
    obsolete_kind_field: "The kind field is no longer needed",
  };
  return headlines[code];
}

/**
 * Compose one validation issue's display text: the plain-language
 * headline followed by the backend's own actionable message, so no
 * per-instance detail (field name, value, target) is ever lost or
 * parsed out of free text.
 *
 * :param code: The stable issue code.
 * :param message: The backend's own message for this issue.
 * :returns: "<headline> — <message>".
 */
export function validationIssueText(code: IssueCode, message: string): string {
  return `${issueCodeLabel(code)} — ${message}`;
}
