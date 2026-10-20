/**
 * Display helpers for shortening machine identifiers in running text
 * (module-ux-principles "Technical identifiers"): content digests
 * (`sha256-v1:<64 hex>`, mirroring the backend's own
 * `app.services.diff.short_digest`) and record UUIDs. Both keep the
 * full value reachable via tooltip/copy at the call site; this
 * module only shortens the displayed text.
 */

/** Number of hex characters kept in the shortened digest form. */
const SHORT_HEX = 12;

/** Number of characters kept in a shortened UUID. */
const SHORT_UUID_CHARS = 8;

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

/**
 * Shorten a UUID for display in running text. The caller must keep
 * the full value reachable (tooltip and copy-to-clipboard), never
 * showing only this short form.
 *
 * :param uuid: Full UUID string.
 * :returns: The UUID's first 8 characters.
 */
export function shortUuid(uuid: string): string {
  return uuid.slice(0, SHORT_UUID_CHARS);
}
