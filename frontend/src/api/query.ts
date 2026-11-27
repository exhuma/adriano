/** Query-string building shared by the API modules. */

/** Build a query string from a params object, dropping empty and
 *  `false` values so the URL stays minimal. */
export function toQueryString(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params as Record<string, unknown>)) {
    if (value === undefined || value === null || value === "" || value === false) {
      continue;
    }
    search.set(key, String(value));
  }
  const text = search.toString();
  return text.length > 0 ? `?${text}` : "";
}
