<script setup lang="ts">
/**
 * Shows a technical identifier (a UUID) in its shortened running-text
 * form, with the full value reachable via a hover/focus tooltip and a
 * click-to-copy button (module-ux-principles "Technical identifiers":
 * never show only the shortened form). Shared by `RecordMetadataCard`
 * (the record's own UUID), `RecordStatusBanners`, and `ErratumBody`
 * (an erratum's unresolved target UUID), so the pattern has exactly
 * one implementation.
 */
import { ref } from "vue";

import { shortUuid } from "@/utils/digest";

const props = defineProps<{
  /** Full identifier value to shorten, show in a tooltip, and copy. */
  value: string;
  /** What the identifier identifies, used in the copy button's
   *  accessible name, e.g. "UUID" or "target UUID". */
  label: string;
}>();

const copied = ref(false);

/** Copy the full identifier to the clipboard, with a brief
 *  "Copied!" note. */
async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // Clipboard API unavailable (e.g. insecure context); the full
    // value is already visible in the tooltip, so this is a soft
    // failure.
  }
}
</script>

<template>
  <span class="short-id-copy">
    <code :title="value">{{ shortUuid(value) }}</code>
    <v-btn
      icon="mdi-content-copy"
      size="x-small"
      variant="text"
      :title="value"
      :aria-label="copied ? `Copied full ${label} to clipboard` : `Copy full ${label} to clipboard`"
      @click="copy"
    />
    <span v-if="copied" class="text-success">Copied!</span>
  </span>
</template>

<style scoped>
.short-id-copy {
  display: inline-flex;
  align-items: center;
  gap: 0.125rem;
}
</style>
