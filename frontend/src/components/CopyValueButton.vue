<script setup lang="ts">
/**
 * Icon button that copies a value to the clipboard and briefly shows
 * "Copied!" (module-ux-principles "Feedback & visibility of system
 * status"). Shared by `ShortIdCopy` (UUIDs), `ApprovalCard` (the
 * indexed digest) and `RecordProvenanceCard` (the file path), so the
 * copy behaviour has one implementation. Its focus-visible ring
 * comes from `App.vue`'s app-wide `.v-btn:focus-visible` rule
 * (P11-R-04), not a local style here.
 */
import { ref } from "vue";

const props = defineProps<{
  /** Exact value written to the clipboard. */
  value: string;
  /** What the value is, used in the accessible name, e.g. "digest"
   *  or "full UUID". */
  label: string;
}>();

const copied = ref(false);

/** Copy `value`, with a brief "Copied!" note on success. */
async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // Clipboard API unavailable (e.g. insecure context); the value
    // is already visible or in a tooltip, so this is a soft failure.
  }
}
</script>

<template>
  <span class="copy-value d-inline-flex align-center ga-1">
    <v-btn
      icon="mdi-content-copy"
      size="x-small"
      variant="text"
      :title="value"
      :aria-label="
        copied ? `Copied ${label} to clipboard` : `Copy ${label} to clipboard`
      "
      @click="copy"
    />
    <span v-if="copied" class="text-success">Copied!</span>
  </span>
</template>
