<script setup lang="ts">
/**
 * The record sidebar's first card (docs/ui-review R-01, R-06): the
 * sidebar's own `h2`, the one-line approval status, a link to the
 * main column's full approval card, and -- when the caller can
 * decide -- the Accept/Reject buttons (`DecideButtons`, shared with
 * `ApprovalCard`). Carrying the sidebar heading inside this card puts
 * the sidebar's top edge on the same line as the main column's first
 * card. Why decisions are blocked is explained once, in the main
 * column's approval card, not repeated here.
 */
import { computed } from "vue";

import DecideButtons from "@/components/DecideButtons.vue";
import StatusChip from "@/components/StatusChip.vue";
import type { ApprovalOut, DecisionSummaryOut } from "@/types/approval";
import type { RecordKind, RecordState } from "@/types/records";
import { approvalDisplayLabel } from "@/utils/labels";

const props = defineProps<{
  /** Approval state of the record's current content. */
  approval: ApprovalOut;
  /** Published or candidate; picks the "accepted" wording. */
  kind: RecordState;
  /** Decision or erratum; picks the heading and status vocabulary. */
  recordKind: RecordKind;
  /** Record id, for the decision dialog's submission. */
  recordId: string;
  /** Title of the record being decided, passed to the decision
   *  dialog so it names the record (docs/ui-review D-02). */
  recordTitle: string;
  /** Branch/ref of the content, for the candidate erratum chip. */
  recordRef: string;
  /** Element id of the heading, which labels the whole sidebar. */
  headingId: string;
}>();

const emit = defineEmits<{
  /** A decision was recorded; the page should reload the record. */
  decided: [event: DecisionSummaryOut];
  /** The content changed while a decision was pending. */
  "digest-changed": [];
}>();

/** The sidebar heading, worded for a decision or an erratum. */
const heading = computed(() =>
  props.recordKind === "erratum" ? "About this erratum" : "About this decision",
);

/** The one status shown in the sidebar, including the neutral
 *  "Blocked" override when the content itself cannot be decided
 *  (docs/ui-review R-02; see `approvalDisplayLabel`). */
const statusLabel = computed(() =>
  approvalDisplayLabel(
    props.approval,
    props.kind,
    props.recordKind,
    props.recordRef,
  ),
);
</script>

<template>
  <v-card class="mb-3" density="compact">
    <v-card-title :id="headingId" tag="h2" class="text-title-large">
      {{ heading }}
    </v-card-title>
    <v-card-text class="d-flex flex-column ga-3">
      <div class="d-flex align-center justify-space-between flex-wrap ga-2">
        <StatusChip v-bind="statusLabel" />
        <a href="#approval" class="text-body-medium">Approval details</a>
      </div>
      <DecideButtons
        v-if="approval.can_decide"
        :record-id="recordId"
        :record-kind="recordKind"
        :record-title="recordTitle"
        :digest="approval.digest"
        @decided="(event) => emit('decided', event)"
        @digest-changed="emit('digest-changed')"
      />
    </v-card-text>
  </v-card>
</template>
