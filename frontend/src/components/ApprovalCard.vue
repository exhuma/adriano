<script setup lang="ts">
/**
 * Approval card on the record detail page: state + explanation,
 * policy summary, indexed digest (short, with copy), decide
 * controls (or the visible reason decisions are blocked), and the
 * decision history. `DecideButtons.vue` (shared with the sidebar's
 * summary card) holds the Accept/Reject buttons and their dialog.
 * Wording switches to the RFC "report → verify/reject" vocabulary
 * when the viewed record is itself an erratum; the decide logic
 * (`useDecision`) is unchanged -- actions stay accepted/rejected
 * either way. When content cannot be decided at all (R-02), the
 * status chip becomes the neutral "Blocked" status and the "why you
 * can't decide" line uses plain-language copy for the blocker code
 * instead of the raw `decide_blocked_reason` text (R-10).
 */
import { computed } from "vue";

import CopyValueButton from "@/components/CopyValueButton.vue";
import DecideButtons from "@/components/DecideButtons.vue";
import DecisionHistoryTable from "@/components/DecisionHistoryTable.vue";
import StatusChip from "@/components/StatusChip.vue";
import type {
  ApprovalOut,
  DecideBlockedCode,
  DecisionSummaryOut,
} from "@/types/approval";
import type { RecordKind, RecordState } from "@/types/records";
import { shortDigest } from "@/utils/digest";
import {
  approvalDisplayLabel,
  approvalStateExplanation,
  decideBlockedLabel,
} from "@/utils/labels";

const props = defineProps<{
  /** Approval state of the record's current content. */
  approval: ApprovalOut;
  /** Whether the viewed row is published or a candidate (only used
   *  to pick between the two "accepted" labels). */
  kind: RecordState;
  /** Whether the viewed record is a normal decision or an erratum;
   *  picks the "Accept/Reject" vs "Verify erratum/Reject erratum"
   *  wording, and the erratum ("Reported"/"Verified"/…) status chip
   *  vocabulary. */
  recordKind: RecordKind;
  /** Record id, for the decision dialog's submission. */
  recordId: string;
  /** Branch/ref of the record's content, shown in the candidate
   *  erratum chip's "Proposed (branch …)" suffix; omitted falls back
   *  to a plain "Proposed". */
  recordRef?: string;
}>();

const emit = defineEmits<{
  /** A decision was recorded; the parent should reload the record. */
  decided: [event: DecisionSummaryOut];
  /** The content changed while a decision was pending. */
  "digest-changed": [];
}>();

function policySummaryText(approval: ApprovalOut): string {
  const policy = approval.policy;
  if (policy.status === "missing") {
    return "No approval policy is configured; decisions are blocked " +
      "until one is.";
  }
  if (policy.status === "invalid") {
    return "The configured approval policy is invalid; decisions are " +
      "blocked until it is fixed.";
  }
  const selfApproval = policy.allow_self_approval
    ? "self-approval is allowed"
    : "self-approval is not allowed";
  return `Policy "${policy.id}" (version ${policy.version}) — approval ` +
    `is ${policy.required ? "required" : "not required"}; ${selfApproval}.`;
}

/** The blocker code, narrowed to the frontend's own closed union
 *  (the OpenAPI schema types it as a plain string -- see
 *  `types/approval.ts`). */
const blockedCode = computed(
  () => props.approval.decide_blocked_code as DecideBlockedCode | null,
);

/** Plain-language reason decisions are blocked (R-10), falling back
 *  to the raw backend text only for an unrecognised code. */
const blockedText = computed(
  () =>
    decideBlockedLabel(blockedCode.value) ??
    props.approval.decide_blocked_reason,
);

/** For a reader (`not_eligible`), the blocked line is muted -- "a
 *  muted 'Only reviewers can approve' style line is enough" (Task
 *  8) -- rather than drawing the same attention as an actionable
 *  blocker. */
const blockedIsMuted = computed(() => blockedCode.value === "not_eligible");

/** `not_approvable`'s reader-facing reason (e.g. "the record has no
 *  valid `uuid`") is free text with no code of its own; it is kept,
 *  never parsed, in a secondary "Details" position alongside the
 *  plain-language headline above (Task 8). */
const blockedDetails = computed(() =>
  blockedCode.value === "not_approvable"
    ? props.approval.decide_blocked_reason
    : null,
);
</script>

<template>
  <v-card class="mb-4">
    <v-card-title tag="h2" class="text-title-large">Approval</v-card-title>
    <v-card-text>
      <StatusChip
        v-bind="approvalDisplayLabel(approval, kind, recordKind, recordRef)"
        class="mb-2"
      />
      <p class="text-body-medium">
        {{
          approvalStateExplanation(
            approval.state,
            approval.policy.status,
            recordKind,
            approval.approvable,
          )
        }}
      </p>
      <p class="text-body-medium">{{ policySummaryText(approval) }}</p>

      <p class="text-body-medium mt-2">
        Indexed content digest:
        <code :title="approval.digest">{{ shortDigest(approval.digest) }}</code>
        <CopyValueButton :value="approval.digest" label="digest" />
      </p>

      <DecideButtons
        v-if="approval.can_decide"
        class="mt-3"
        :record-id="recordId"
        :record-kind="recordKind"
        :digest="approval.digest"
        @decided="(event) => emit('decided', event)"
        @digest-changed="emit('digest-changed')"
      />
      <div v-else class="mt-3">
        <p
          class="text-body-medium d-flex align-center ga-1"
          :class="{ 'text-medium-emphasis': blockedIsMuted }"
        >
          <v-icon
            icon="mdi-information-outline"
            size="small"
            aria-hidden="true"
          />
          {{ blockedText }}
        </p>
        <p
          v-if="blockedDetails"
          class="text-body-small text-medium-emphasis ml-5"
        >
          Details: {{ blockedDetails }}
        </p>
      </div>
    </v-card-text>

    <v-divider />
    <v-card-title tag="h3" class="text-title-small">
      Decision history
    </v-card-title>
    <v-card-text>
      <DecisionHistoryTable :history="approval.history" :record-kind="recordKind" />
    </v-card-text>
  </v-card>
</template>
