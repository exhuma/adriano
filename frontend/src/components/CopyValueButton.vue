<script setup lang="ts">
/**
 * Icon button that copies a value to the clipboard and briefly shows
 * "Copied!" (module-ux-principles "Feedback & visibility of system
 * status"). Shared by `ShortIdCopy` (UUIDs), `ApprovalCard` (the
 * indexed digest) and `RecordProvenanceCard` (the file path), so the
 * copy behaviour and its focus ring have one implementation.
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

<style scoped>
/* docs/ui-review G-08: Vuetify's own focus ring for a `variant="text"`
   icon button draws `currentColor` at 25% opacity (see
   `VBtn.css`'s `::after`), which the review measured at ~1.2:1 for
   this x-small, colourless copy button -- no prop or default reaches
   that opacity, so an explicit, opaque outline is the last resort
   (ladder step 6), built from the theme's `primary` colour. */
.copy-value :deep(.v-btn:focus-visible) {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}
</style>
