/**
 * Pure wording helpers for the record page's provenance and
 * freshness/stale banner. Kept separate from `labels.ts` (icon/text
 * chips) because these return full sentences whose wording depends
 * on record kind, poll outcome and intake, not just an enum value
 * (never claim a candidate or a push-only
 * registration "may not be the current published revision", and
 * never say content "could not be refreshed" when it is merely old).
 */
import type { FreshnessOut, ProvenanceOut, RecordState } from "@/types/records";
import { formatDateTime } from "@/utils/dates";

/**
 * Describe where a record's content came from, worded for the
 * record's kind.
 *
 * :param kind: Published or candidate.
 * :param provenance: Source/project/ref and last-content-change time.
 * :returns: One sentence, never mentioning polling for a candidate.
 */
export function provenanceText(kind: RecordState, provenance: ProvenanceOut): string {
  if (kind === "candidate") {
    const at = formatDateTime(provenance.updated_at) ?? "an unknown time";
    return `Submitted from ref ${provenance.ref} at ${at} ` +
      `(${provenance.source_id} / ${provenance.project}).`;
  }
  return `Published from ${provenance.source_id} / ${provenance.project}.`;
}

/**
 * Build the stale/failed freshness banner text for a record, or
 * `null` when none should show.
 *
 * No banner for a candidate (polling never applies to it) or for a
 * record owned by a push-only registration (`freshness.intake` has
 * no `"poll"`): polling freshness is simply not a concept there.
 * Otherwise, wording distinguishes a failed/partial poll (content is
 * the last good snapshot, currency is actually unknown) from content
 * that is merely older than the freshness threshold (currency is
 * probably fine, just unverified recently).
 *
 * :param kind: Published or candidate.
 * :param provenance: Owning source id, for the failed-poll sentence.
 * :param freshness: The owning registration's freshness.
 * :returns: One sentence, or `null` when no banner applies.
 */
export function freshnessBannerText(
  kind: RecordState,
  provenance: ProvenanceOut,
  freshness: FreshnessOut,
): string | null {
  if (kind === "candidate" || !freshness.intake.includes("poll")) {
    return null;
  }
  if (!freshness.stale) {
    return null;
  }
  if (freshness.last_status === "failed" || freshness.last_status === "partial") {
    const verb = freshness.last_status === "failed" ? "failed" : "was incomplete";
    const at = formatDateTime(freshness.last_attempt_at) ?? "an unknown time";
    return `The last poll of ${provenance.source_id} ${verb} at ${at}; ` +
      "this is the last successfully indexed revision and may not be " +
      "the current published revision.";
  }
  if (!freshness.last_success_at) {
    return `${provenance.source_id} has never been successfully polled; ` +
      "this record's currency relative to the published source is " +
      "unknown.";
  }
  const at = formatDateTime(freshness.last_success_at) ?? "an unknown time";
  return `Last indexed ${at} (older than the freshness threshold); the ` +
    "source may have changed since.";
}
