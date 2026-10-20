<script setup lang="ts">
/**
 * Record detail page's sidebar: everything that is metadata rather
 * than document body, composed from the existing (now
 * sidebar-restyled) cards plus a compact approval summary linking to
 * the main column's approval card (rfc-editor.org/info layout: the
 * document is the main column, metadata moves to the side). Purely
 * presentational -- all data comes straight from the record detail
 * the parent view already loaded.
 */
import StatusChip from "@/components/StatusChip.vue";
import RecordLinksCard from "@/components/record/RecordLinksCard.vue";
import RecordMetadataCard from "@/components/record/RecordMetadataCard.vue";
import RecordProvenanceCard from "@/components/record/RecordProvenanceCard.vue";
import RecordSiblingsCard from "@/components/record/RecordSiblingsCard.vue";
import LegacySignoffCard from "@/components/record/LegacySignoffCard.vue";
import type {
  ApprovalStateCode,
  FreshnessOut,
  InboundLinkOut,
  OutboundLinkOut,
  ProvenanceOut,
  RecordKind,
  RecordState,
  SiblingOut,
} from "@/types/records";
import { approvalStateLabel, erratumStatusLabel } from "@/utils/labels";

defineProps<{
  /** Whether this record is a normal decision or an erratum; picks
   *  the sidebar's own title. */
  recordKind: RecordKind;
  /** Published or candidate; used (with `approvalState`) to pick the
   *  right "accepted" wording for the approval summary chip. */
  kind: RecordState;
  /** Approval state of the record's current content, for the
   *  summary chip. */
  approvalState: ApprovalStateCode;
  /** Canonical ADR UUID, or `null`/absent when the file has none. */
  adrUuid: string | null;
  /** Authored decision date, `YYYY-MM-DD`. */
  decisionDate: string | null;
  /** Whether `decisionDate` was inferred from the filename. */
  decisionDateInferred: boolean;
  /** Where this record's content came from. */
  provenance: ProvenanceOut;
  /** Freshness of the owning registration. */
  freshness: FreshnessOut;
  /** Outbound `updates`/`obsoletes` links. An erratum's own
   *  `corrects` link is replaced by `erratum_for` (shown in the
   *  status banner) and never appears here. */
  outboundLinks: OutboundLinkOut[];
  /** Other records linking to this one. */
  inboundLinks: InboundLinkOut[];
  /** Other published/candidate rows sharing this record's identity. */
  siblings: SiblingOut[];
  /** Unverified legacy `signed-off-by` entries from the document. */
  legacySignoffEntries: string[];
}>();
</script>

<template>
  <aside aria-labelledby="sidebar-heading">
    <h2 id="sidebar-heading" class="text-title-large mb-2">
      {{ recordKind === "erratum" ? "About this erratum" : "About this decision" }}
    </h2>

    <v-card class="mb-3" density="compact">
      <v-card-text class="d-flex align-center justify-space-between flex-wrap ga-2">
        <StatusChip
          v-if="recordKind === 'erratum'"
          v-bind="erratumStatusLabel(approvalState, kind, provenance.ref)"
        />
        <StatusChip v-else v-bind="approvalStateLabel(approvalState, kind)" />
        <a href="#approval" class="text-body-medium">View approval</a>
      </v-card-text>
    </v-card>

    <RecordMetadataCard
      :adr-uuid="adrUuid"
      :decision-date="decisionDate"
      :decision-date-inferred="decisionDateInferred"
      :record-kind="recordKind"
    />

    <RecordProvenanceCard :provenance="provenance" :freshness="freshness" />

    <RecordLinksCard :outbound-links="outboundLinks" :inbound-links="inboundLinks" />

    <RecordSiblingsCard :siblings="siblings" />

    <LegacySignoffCard :entries="legacySignoffEntries" />
  </aside>
</template>
