/**
 * Pure helper classifying the lines of a `difflib`-style unified
 * diff for accessible rendering: a per-line kind so the view can
 * prefix and (optionally) colour each line without re-parsing the
 * text, and never relying on colour alone (module-ux-principles "Do
 * not rely on color alone").
 */

/** What one rendered diff line represents. */
export type DiffLineKind = "header" | "hunk" | "added" | "removed" | "context";

/** One line of a unified diff, classified for rendering. */
export interface DiffLine {
  /** Kind of line (drives the +/- prefix and optional colour). */
  kind: DiffLineKind;
  /** The line's exact text, including its leading +/-/space marker. */
  text: string;
}

/**
 * Classify each line of a unified diff.
 *
 * :param unifiedDiff: `difflib` unified diff text (may be empty).
 * :returns: One classified entry per line (empty when the input is
 *     empty).
 */
export function classifyDiffLines(unifiedDiff: string): DiffLine[] {
  if (unifiedDiff.length === 0) {
    return [];
  }
  const lines = unifiedDiff.split("\n");
  // A trailing "\n" produces one trailing empty element; drop it so
  // it does not render as a blank context line.
  if (lines.length > 0 && lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines.map((text) => ({ kind: classifyLine(text), text }));
}

function classifyLine(text: string): DiffLineKind {
  if (text.startsWith("--- ") || text.startsWith("+++ ")) {
    return "header";
  }
  if (text.startsWith("@@")) {
    return "hunk";
  }
  if (text.startsWith("+")) {
    return "added";
  }
  if (text.startsWith("-")) {
    return "removed";
  }
  return "context";
}

/** The digests a record page knows about, for `hasComparableRevision`. */
export interface KnownDigests {
  /** The record's current digest. */
  current: string;
  /** The record's previous stored digest, if any. */
  previous: string | null;
  /** Digests from the identity's decision history. */
  history: readonly string[];
  /** Digests of identity siblings and competing candidates. */
  others: readonly string[];
}

/**
 * Whether the page knows any revision other than the current one, so
 * a diff has something to compare against (docs/ui-review R-08: the
 * Diff card is hidden otherwise). Mirrors the server's default base
 * (last decided digest other than the current one, else the previous
 * digest) and also counts siblings and competing candidates, which
 * the Diff card offers as alternative bases.
 *
 * :param digests: The digests known to the page.
 * :returns: `true` when at least one digest differs from `current`.
 */
export function hasComparableRevision(digests: KnownDigests): boolean {
  const all = [
    digests.previous,
    ...digests.history,
    ...digests.others,
  ];
  return all.some((digest) => digest !== null && digest !== digests.current);
}
