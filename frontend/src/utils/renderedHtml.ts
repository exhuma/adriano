/**
 * Pure helpers for the record page's server-rendered Markdown HTML.
 * `renderedHtml` is sanitized server-side with `nh3` before storage
 * (see DECISIONS.md "Record schema"), so building a DOM from it to
 * inspect and trim its leading heading is exactly as safe as the
 * `v-html` render that already trusts the same string.
 */

/**
 * Normalize heading text for a whitespace/case-insensitive compare.
 *
 * :param text: Raw heading text.
 * :returns: Collapsed-whitespace, trimmed, lower-cased text.
 */
function normalizeHeading(text: string): string {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

/**
 * Drop a leading `<h1>` from rendered Markdown HTML when its text
 * equals the record's own title, so the title is never shown twice
 * (R-03: the page's own `h1`, in `RecordHeader`, already carries it).
 * Only the first element is inspected and, when it matches, removed
 * from a cloned document -- every other element keeps its original
 * markup untouched, and a non-matching or absent leading heading
 * leaves `html` byte-for-byte unchanged.
 *
 * :param html: Sanitized rendered-Markdown HTML.
 * :param title: The record's own title to compare against.
 * :returns: `html` unchanged, or with its leading duplicate `h1`
 *     removed.
 */
export function stripLeadingTitleHeading(html: string, title: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const first = doc.body.firstElementChild;
  if (
    first === null ||
    first.tagName !== "H1" ||
    normalizeHeading(first.textContent ?? "") !== normalizeHeading(title)
  ) {
    return html;
  }
  first.remove();
  return doc.body.innerHTML;
}
