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
