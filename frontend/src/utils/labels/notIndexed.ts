/**
 * Plain-language labels for the not-indexed list: the origin of an
 * entry and the reason codes an entry can carry. The wording for each
 * reason itself is `issueCodeLabel` (issues.ts); this module only
 * decides which codes are offered as a filter.
 */
import type { IssueCode } from "@/types/records";
import type { NotIndexedItem } from "@/types/notIndexed";

import { issueCodeLabel } from "./issues";

/**
 * Reason codes that keep a document out of the catalog: the ones
 * that explain a missing or unusable UUID, plus the intake refusals.
 * Offered by the list's reason filter.
 */
export const NOT_INDEXED_REASON_CODES: IssueCode[] = [
  "missing_frontmatter",
  "bad_yaml",
  "missing_uuid",
  "bad_uuid",
  "bad_encoding",
  "duplicate_uuid",
  "fetch_failed",
  "uuid_mismatch",
  "published_ref_not_allowed",
  "content_too_large",
];

/** Options for the reason filter's select. */
export function notIndexedReasonOptions(): { title: string; value: IssueCode }[] {
  return NOT_INDEXED_REASON_CODES.map((code) => ({
    title: issueCodeLabel(code),
    value: code,
  }));
}

/**
 * Describe how an entry was found.
 *
 * :param origin: `"poll"` (listed from the repository) or `"push"`
 *     (submitted by a CI job).
 * :returns: A short label.
 */
export function originLabel(origin: NotIndexedItem["origin"]): string {
  return origin === "push" ? "Pushed" : "Polled";
}
