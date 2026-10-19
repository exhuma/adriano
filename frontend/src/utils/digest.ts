/**
 * Display helpers for canonical content digests
 * (`sha256-v1:<64 hex>`), mirroring the backend's own
 * `app.services.diff.short_digest` so the short form shown in the UI
 * matches what appears in server-side diff labels.
 */

/** Number of hex characters kept in the shortened form. */
const SHORT_HEX = 12;

/**
 * Shorten a digest string for display, keeping its algorithm prefix.
 *
 * :param digest: Full digest string, e.g. `sha256-v1:<64 hex>`.
 * :returns: `<algorithm>:<first 12 hex>`; the input unchanged when it
 *     has no `:` separator.
 */
export function shortDigest(digest: string): string {
  const separatorIndex = digest.indexOf(":");
  if (separatorIndex === -1) {
    return digest;
  }
  const algorithm = digest.slice(0, separatorIndex);
  const hex = digest.slice(separatorIndex + 1);
  return `${algorithm}:${hex.slice(0, SHORT_HEX)}`;
}
