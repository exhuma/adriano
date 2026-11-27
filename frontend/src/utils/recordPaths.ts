/**
 * Router paths of the record pages. An ADR is addressed by its UUID
 * alone (`/records/:uuid`); a candidate row adds the ref it was read
 * from (`/records/:uuid/candidates/:ref`). A ref is a git ref and may
 * contain slashes, so it is kept as a path remainder, each segment
 * encoded.
 */
import type { RecordState } from "@/types/records";

/** Encode a ref for a URL path: segments encoded, slashes kept. */
export function encodeRefPath(ref: string): string {
  return ref.split("/").map(encodeURIComponent).join("/");
}

/**
 * Path of the page of one ADR's candidate row.
 *
 * :param adrUuid: The ADR's UUID.
 * :param ref: The ref the candidate was read from (slashes allowed).
 * :returns: The router path.
 */
export function candidatePath(adrUuid: string, ref: string): string {
  return `/records/${encodeURIComponent(adrUuid)}/candidates/${encodeRefPath(ref)}`;
}

/**
 * Path of the page of an ADR, or of one of its rows.
 *
 * :param adrUuid: The ADR's UUID.
 * :param row: The row to open: a candidate opens its own page; a
 *     published row, or no row, opens the ADR page (which shows the
 *     published row, else the newest candidate).
 * :returns: The router path.
 */
export function recordPath(
  adrUuid: string,
  row?: { kind: RecordState; ref: string },
): string {
  if (row?.kind === "candidate") {
    return candidatePath(adrUuid, row.ref);
  }
  return `/records/${encodeURIComponent(adrUuid)}`;
}
