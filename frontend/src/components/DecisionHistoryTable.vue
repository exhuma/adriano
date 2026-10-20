<script setup lang="ts">
/**
 * Append-only decision history of one record's identity: action,
 * reviewer, timestamp, comment, digest, and provenance for every
 * accept/reject event, oldest first (as the API returns it). The
 * action wording switches to "Verified" for an accepted erratum
 * (RFC report/verify/reject vocabulary) when `recordKind` is
 * "erratum"; the underlying action stays accepted/rejected either
 * way.
 */
import type { DecisionSummaryOut } from "@/types/approval";
import type { RecordKind } from "@/types/records";
import { formatDateTime, formatRelativeTime } from "@/utils/dates";
import { decisionActionLabel } from "@/utils/labels";
import { shortDigest } from "@/utils/digest";

const props = defineProps<{
  /** Every decision event of the record's identity, oldest first. */
  history: DecisionSummaryOut[];
  /** Whether the viewed record is a normal decision or an erratum;
   *  picks the "Accepted" vs "Verified" wording for the accepted
   *  action (RFC report/verify/reject vocabulary). Defaults to
   *  "decision" for callers that have not yet opted in. */
  recordKind?: RecordKind;
}>();

function provenanceText(event: DecisionSummaryOut): string {
  const kind = event.provenance.kind === "candidate" ? "Candidate" : "Published";
  const ref = event.provenance.ref;
  return ref ? `${kind} @ ${ref}` : kind;
}
</script>

<template>
  <v-table v-if="history.length > 0" density="compact" class="history-table">
    <caption class="sr-only">Decision history, oldest first</caption>
    <thead>
      <tr>
        <th scope="col">Action</th>
        <th scope="col">Reviewer</th>
        <th scope="col">When</th>
        <th scope="col">Comment</th>
        <th scope="col">Content</th>
        <th scope="col">Provenance</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="event in history" :key="event.id">
        <td>
          <v-icon
            :icon="decisionActionLabel(event.action, props.recordKind).icon"
            :color="decisionActionLabel(event.action, props.recordKind).color"
            size="small"
            aria-hidden="true"
          />
          {{ decisionActionLabel(event.action, props.recordKind).text }}
        </td>
        <td>
          <span :title="`${event.actor_issuer}|${event.actor_subject}`">
            {{ event.actor_display ?? event.actor_subject }}
          </span>
        </td>
        <td>
          <span :title="formatDateTime(event.created_at) ?? undefined">
            {{ formatRelativeTime(event.created_at) }}
          </span>
        </td>
        <td>{{ event.comment ?? "—" }}</td>
        <td>
          <code :title="event.digest">{{ shortDigest(event.digest) }}</code>
          <span v-if="event.current_digest" class="text-body-small text-medium-emphasis ml-1">
            (current content)
          </span>
          <span v-else class="text-body-small text-medium-emphasis ml-1">
            (earlier revision)
          </span>
        </td>
        <td>{{ provenanceText(event) }}</td>
      </tr>
    </tbody>
  </v-table>
  <p v-else class="text-body-medium text-medium-emphasis">
    No formal decisions recorded yet.
  </p>
</template>

<style scoped>
.history-table :deep(td),
.history-table :deep(th) {
  white-space: normal;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
