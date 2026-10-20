<script setup lang="ts">
/**
 * Approval card on the record detail page: state + explanation,
 * policy summary, indexed digest (short, with copy), decide
 * controls (or the visible reason decisions are blocked), and the
 * decision history. `DecisionDialog.vue` is the adapter that turns
 * an Accept/Reject click into a submitted decision. Wording switches
 * to the RFC "report → verify/reject" vocabulary when the viewed
 * record is itself an erratum; the underlying decide logic
 * (`useDecision`) is unchanged -- actions stay accepted/rejected
 * either way.
 */
import { ref } from "vue";

import DecisionDialog from "@/components/DecisionDialog.vue";
import DecisionHistoryTable from "@/components/DecisionHistoryTable.vue";
import StatusChip from "@/components/StatusChip.vue";
import type { ApprovalOut, DecisionAction, DecisionSummaryOut } from "@/types/approval";
import type { RecordKind, RecordState } from "@/types/records";
import { shortDigest } from "@/utils/digest";
import {
  approvalStateExplanation,
  approvalStateLabel,
  erratumStatusLabel,
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

const dialogOpen = ref(false);
const dialogAction = ref<DecisionAction>("accepted");
const triggerButton = ref<HTMLElement | null>(null);
const copied = ref(false);

function openDialog(action: DecisionAction, event: MouseEvent): void {
  dialogAction.value = action;
  triggerButton.value = event.currentTarget as HTMLElement;
  dialogOpen.value = true;
}

function onDialogClosed(open: boolean): void {
  dialogOpen.value = open;
  if (!open) {
    // Focus returns to whichever button opened the dialog, so
    // keyboard users land back where they were, not at the top of
    // the page (module-ux-principles accessibility: visible focus).
    triggerButton.value?.focus();
  }
}

async function copyDigest(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.approval.digest);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // Clipboard API unavailable; the digest is already visible and
    // selectable as text, so this is a soft failure.
  }
}

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
</script>

<template>
  <v-card class="mb-4">
    <v-card-title tag="h2" class="text-title-large">Approval</v-card-title>
    <v-card-text>
      <StatusChip
        v-if="recordKind === 'erratum'"
        v-bind="erratumStatusLabel(approval.state, kind, recordRef)"
        class="mb-2"
      />
      <StatusChip
        v-else
        v-bind="approvalStateLabel(approval.state, kind)"
        class="mb-2"
      />
      <p class="text-body-medium">
        {{ approvalStateExplanation(approval.state, approval.policy.status, recordKind) }}
      </p>
      <p class="text-body-medium">{{ policySummaryText(approval) }}</p>

      <p class="text-body-medium mt-2">
        Indexed content digest:
        <code :title="approval.digest">{{ shortDigest(approval.digest) }}</code>
        <v-btn
          icon="mdi-content-copy"
          size="x-small"
          variant="text"
          class="digest-copy-btn"
          :aria-label="copied ? 'Copied digest to clipboard' : 'Copy digest to clipboard'"
          @click="copyDigest"
        />
        <span v-if="copied" class="text-success">Copied!</span>
      </p>

      <div v-if="approval.can_decide" class="mt-3 decide-actions">
        <v-btn
          color="primary"
          variant="flat"
          prepend-icon="mdi-check"
          @click="openDialog('accepted', $event)"
        >
          {{ recordKind === "erratum" ? "Verify erratum" : "Accept" }}
        </v-btn>
        <v-btn
          color="error"
          variant="outlined"
          prepend-icon="mdi-close"
          @click="openDialog('rejected', $event)"
        >
          {{ recordKind === "erratum" ? "Reject erratum" : "Reject" }}
        </v-btn>
      </div>
      <p v-else class="text-body-medium mt-3 decide-blocked">
        <v-icon icon="mdi-information-outline" size="small" aria-hidden="true" />
        {{ approval.decide_blocked_reason }}
      </p>
    </v-card-text>

    <v-divider />
    <v-card-title class="text-title-small">Decision history</v-card-title>
    <v-card-text>
      <DecisionHistoryTable :history="approval.history" :record-kind="recordKind" />
    </v-card-text>

    <DecisionDialog
      :model-value="dialogOpen"
      :record-id="recordId"
      :action="dialogAction"
      :record-kind="recordKind"
      :digest="approval.digest"
      @update:model-value="onDialogClosed"
      @decided="(event) => emit('decided', event)"
      @digest-changed="emit('digest-changed')"
    />
  </v-card>
</template>

<style scoped>
.decide-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.decide-blocked {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

/* docs/ui-review G-08: see the identical rule and justification in
   ShortIdCopy.vue -- same x-small, colourless `variant="text"` icon
   button, same too-faint default focus ring. */
.digest-copy-btn:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}
</style>
