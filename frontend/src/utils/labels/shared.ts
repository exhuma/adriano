/**
 * Types and constants shared across the `utils/labels/*` modules
 * (module-code-structure-limits: the former single `labels.ts` grew
 * past the 500-line module limit and was split by domain -- approval,
 * records, errata, search, sources, issues -- with this module
 * holding what more than one of those domains needs. Re-exported
 * through `index.ts` so `@/utils/labels` imports keep working.
 */

/** An icon + text + colour triple rendered as a `StatusChip`. */
export interface StatusLabel {
  /** Material Design Icons name. */
  icon: string;
  /** Visible label text. */
  text: string;
  /** Vuetify theme colour token, or `undefined` for a neutral chip. */
  color?: string;
  /**
   * Full meaning announced to assistive tech when `text` has been
   * shortened for space (`StatusChip`'s `ariaLabel` prop); falls
   * back to `text` when omitted, so it stays optional here.
   */
  ariaLabel?: string;
}

/**
 * Neutral status for content that cannot be decided at all because
 * of a content problem (R-02), e.g. a missing/invalid `uuid` or
 * invalid encoding (`ApprovalOut.approvable === false`). The icon is
 * error-ish (an alert glyph) but the chip carries no colour: text
 * and icon carry the meaning, not an error-red fill
 * (phases/11-ui-ux-updates.md: "a neutral chip with an error-ish
 * icon [...] not the error colour as the only signal"). Shared by
 * `approval.ts` and `search.ts`, which both apply this override.
 */
export const BLOCKED_STATUS_LABEL: StatusLabel = {
  icon: "mdi-alert-circle-outline",
  text: "Blocked",
  ariaLabel: "Blocked — this content cannot be decided",
};

/** Explanation sentence paired with {@link BLOCKED_STATUS_LABEL},
 *  shared by `approval.ts`'s `approvalStateExplanation` (the main
 *  column's explanation paragraph) and `decideBlockedLabel` (the
 *  blocked-reason line), so both read identically. */
export const BLOCKED_EXPLANATION =
  "This content can't be decided until its problems are fixed.";
