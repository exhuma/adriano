<script setup lang="ts">
/**
 * Record detail page's sidebar: everything that is metadata rather
 * than document body (rfc-editor.org/info layout: the document is
 * the main column, metadata moves to the side). Its first card holds
 * the sidebar heading, the approval status and -- for reviewers --
 * the Accept/Reject buttons (docs/ui-review R-01). At `md` and up
 * only that first card is sticky below the app bar (P11-R-13); the
 * info cards below it flow with the page like the main column, so
 * the sidebar can never grow taller than the viewport the way a
 * whole-sidebar sticky region did at 1366x768 -- there is no nested
 * scroll region, so no overflow tracking or extra tab stop is
 * needed. Below `md` the sticky card stacks under the main column as
 * a normal block too (the `position-sticky` class is conditional).
 *
 * `<aside>` carries `h-100`: a sticky element can never stick past
 * the bottom edge of its containing block, which for the summary
 * card (a direct child with no intervening positioned ancestor) is
 * `<aside>` itself. `RecordView`'s `v-row` already stretches both
 * columns to equal height (flexbox's default `align-items: stretch`
 * with the main column's content as the tall side), but `<aside>` is
 * plain block content, so without `h-100` it still only grows to its
 * own cards' height -- shorter than the main column whenever the
 * main column has more content -- and the card would un-stick before
 * the page finished scrolling. `h-100` lets it fill the already-
 * stretched `v-col`, so the card stays stuck through the full scroll.
 */
import { useDisplay } from "vuetify";

import RecordApprovalSummaryCard from
  "@/components/record/RecordApprovalSummaryCard.vue";
import RecordLinksCard from "@/components/record/RecordLinksCard.vue";
import RecordMetadataCard from "@/components/record/RecordMetadataCard.vue";
import RecordProvenanceCard from "@/components/record/RecordProvenanceCard.vue";
import RecordSiblingsCard from "@/components/record/RecordSiblingsCard.vue";
import LegacySignoffCard from "@/components/record/LegacySignoffCard.vue";
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
  /** Title of the record being decided, passed to the decision
   *  dialog so it names the record (docs/ui-review D-02). */
  recordTitle: string;
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
  <aside aria-labelledby="sidebar-heading" class="h-100">
    <RecordApprovalSummaryCard
      heading-id="sidebar-heading"
      :class="{ 'sidebar-summary--sticky position-sticky': mdAndUp }"
      :approval="approval"
      :kind="kind"
      :record-kind="recordKind"
      :record-id="recordId"
      :record-title="recordTitle"
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
  </aside>
</template>

<style scoped>
/* P11-R-13: only the sidebar's first card is sticky, not the whole
   aside, so the info cards below it flow with the page and can never
   be taller than the viewport (the old whole-sidebar sticky region
   was at 1366x768). Vuetify's `position-sticky` utility has no
   offset utility, and the offset must follow the app bar's live
   height, which Vuetify only exposes as `--v-layout-top`; 16px
   leaves the same gap as the column gutter. */
.sidebar-summary--sticky {
  top: calc(var(--v-layout-top) + 16px);
  /* The card already paints its own opaque theme surface background
     (Vuetify's `VCard` default), but still needs to stack above the
     info cards that scroll underneath it as the page scrolls;
     Vuetify has no utility for stacking order. */
  z-index: 1;
}

/* WCAG 2.4.11: a focused control inside an info card below can
   scroll up underneath the sticky summary card above it; give every
   focusable element in the sidebar enough top clearance to land
   below the card instead of partly hidden behind it. Vuetify has no
   scroll-margin utility. 200px covers the summary card's measured
   height (about 150-180px with Accept/Reject shown) plus the sticky
   offset's 16px gap. */
aside :focus-visible {
  scroll-margin-top: calc(var(--v-layout-top) + 200px);
}
</style>
