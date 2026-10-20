<script setup lang="ts">
/**
 * Record detail page's sidebar: everything that is metadata rather
 * than document body (rfc-editor.org/info layout: the document is
 * the main column, metadata moves to the side). Its first card holds
 * the sidebar heading, the approval status and -- for reviewers --
 * the Accept/Reject buttons (docs/ui-review R-01). At `md` and up the
 * whole sidebar is sticky below the app bar and capped to the
 * viewport height, scrolling on its own when taller, so the decision
 * actions stay in reach while the main column scrolls and no card is
 * ever pushed out of reach below the fold. Below `md` it stacks
 * under the main column as a normal block.
 */
import { ref } from "vue";
import { useDisplay } from "vuetify";

import RecordApprovalSummaryCard from
  "@/components/record/RecordApprovalSummaryCard.vue";
import RecordLinksCard from "@/components/record/RecordLinksCard.vue";
import RecordMetadataCard from "@/components/record/RecordMetadataCard.vue";
import RecordProvenanceCard from "@/components/record/RecordProvenanceCard.vue";
import RecordSiblingsCard from "@/components/record/RecordSiblingsCard.vue";
import LegacySignoffCard from "@/components/record/LegacySignoffCard.vue";
import { useScrollOverflow } from "@/composables/useScrollOverflow";
import type { ApprovalOut, DecisionSummaryOut } from "@/types/approval";
import type {
  FreshnessOut,
  InboundLinkOut,
  OutboundLinkOut,
  ProvenanceOut,
  RecordKind,
  RecordState,
  SiblingOut,
} from "@/types/records";

defineProps<{
  /** Whether this record is a normal decision or an erratum; picks
   *  the sidebar's own title. */
  recordKind: RecordKind;
  /** Published or candidate; picks the "accepted" wording. */
  kind: RecordState;
  /** Record id, for the sidebar's decision dialog. */
  recordId: string;
  /** Approval state of the record's current content (status chip,
   *  `can_decide`, digest to decide). */
  approval: ApprovalOut;
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

const emit = defineEmits<{
  /** A decision was recorded from the sidebar's buttons. */
  decided: [event: DecisionSummaryOut];
  /** The content changed while a sidebar decision was pending. */
  "digest-changed": [];
}>();

const { mdAndUp } = useDisplay();
const asideEl = ref<HTMLElement | null>(null);
const contentEl = ref<HTMLElement | null>(null);
const overflows = useScrollOverflow(asideEl, contentEl);

/**
 * Scoped defaults for the info cards under the sidebar `h2` (ladder
 * step 3): card titles are `h3` headings at the sidebar card-title
 * size (docs/ui-review G-05, DECISIONS.md type scale; `ma-0`
 * restates the global card-title default this object replaces); list
 * rows are label/value pairs whose label (`VListItemTitle`) reads
 * below the card title and above its value, which Vuetify's own list
 * defaults invert (title 16px/400, subtitle 14px/400); `lines: false`
 * drops Vuetify's one-line clamp so long values (paths, link titles)
 * wrap instead of ending in an ellipsis (R-09). Scoped here, not global,
 * because other `VListItemTitle` uses (e.g. `RecordIssuesList`) are
 * plain sentences, and the summary card above carries the `h2`.
 */
const infoCardDefaults = {
  VCardTitle: { tag: "h3", class: "text-title-medium ma-0" },
  VList: { density: "compact", lines: false },
  VListItemTitle: { class: "text-label-large" },
  VListItemSubtitle: { class: "text-body-medium" },
} as const;
</script>

<template>
  <aside
    ref="asideEl"
    aria-labelledby="sidebar-heading"
    :class="{
      'record-sidebar--sticky position-sticky overflow-y-auto': mdAndUp,
    }"
    :tabindex="mdAndUp && overflows ? 0 : undefined"
  >
    <div ref="contentEl">
      <RecordApprovalSummaryCard
        heading-id="sidebar-heading"
        :approval="approval"
        :kind="kind"
        :record-kind="recordKind"
        :record-id="recordId"
        :record-ref="provenance.ref"
        @decided="(event) => emit('decided', event)"
        @digest-changed="emit('digest-changed')"
      />

      <v-defaults-provider :defaults="infoCardDefaults">
        <RecordMetadataCard
          :adr-uuid="adrUuid"
          :decision-date="decisionDate"
          :decision-date-inferred="decisionDateInferred"
          :record-kind="recordKind"
        />

        <RecordProvenanceCard :provenance="provenance" :freshness="freshness" />

        <RecordLinksCard
          :outbound-links="outboundLinks"
          :inbound-links="inboundLinks"
        />

        <RecordSiblingsCard :siblings="siblings" />

        <LegacySignoffCard :entries="legacySignoffEntries" />
      </v-defaults-provider>
    </div>
  </aside>
</template>

<style scoped>
/* docs/ui-review R-01: Vuetify's `position-sticky` has no offset
   utility, and the offset must follow the app bar's live height,
   which Vuetify only exposes as `--v-layout-top` (set on `v-main`);
   16px leaves the same gap as the column gutter. The max-height keeps
   the sticky sidebar inside the viewport so its lower cards scroll
   within it (`overflow-y-auto`) instead of being unreachable. */
.record-sidebar--sticky {
  top: calc(var(--v-layout-top) + 16px);
  max-height: calc(100vh - var(--v-layout-top) - 32px);
}
</style>
