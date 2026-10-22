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
 * status chip becomes the neutral "Blocked" status and the
 * explanation above already states "can't be decided until its
 * problems are fixed" once, so the blocked-reason row below is not
 * repeated for that case; its raw secondary detail is shown only
 * when the issues card above did not already explain the problem
 * (`hasValidationIssues`), never as plain machine-worded text
 * (P11-R-07).
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
  /** Title of the record being decided, passed to the decision
   *  dialog so it names the record. */
  recordTitle: string;
  /** Branch/ref of the record's content, shown in the candidate
   *  erratum chip's "Proposed (ref …)" suffix; omitted falls back
   *  to a plain "Proposed". */
  recordRef?: string;
  /** Whether the record page's issues card already lists validation
   *  problems for this record; when true, the secondary "Details"
   *  line below is skipped for `not_approvable` instead of repeating
   *  what the issues card already explains (P11-R-07). */
  hasValidationIssues?: boolean;
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

/** `not_approvable`'s reader-facing reason is free text with no
 *  code of its own. When the issues card above already lists the
 *  validation problems, showing this raw text again is a machine-
 *  worded duplicate (P11-R-07), so it is kept, never parsed, as a
 *  secondary "Details" fallback only when that card is empty. */
const blockedDetails = computed(() =>
  blockedCode.value === "not_approvable" && !props.hasValidationIssues
    ? props.approval.decide_blocked_reason
    : null,
);

/**
 * The blocked-reason row above is skipped for `not_approvable`: the
 * state explanation paragraph (`approvalStateExplanation`) already
 * renders the exact same "can't be decided until its problems are
 * fixed" sentence for that code, so showing it again would say the
 * same thing twice (P11-R-07).
 */
const showBlockedReason = computed(
  () => blockedCode.value !== "not_approvable",
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
        :record-title="recordTitle"
        :digest="approval.digest"
        @decided="(event) => emit('decided', event)"
        @digest-changed="emit('digest-changed')"
      />
      <div v-else class="mt-3">
        <p
          v-if="showBlockedReason"
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
