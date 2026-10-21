<script setup lang="ts">
/**
 * Icon button that copies a value to the clipboard and briefly shows
 * "Copied!" (module-ux-principles "Feedback & visibility of system
 * status"). Shared by `ShortIdCopy` (UUIDs), `ApprovalCard` (the
 * indexed digest) and `RecordProvenanceCard` (the file path), so the
 * copy behaviour has one implementation. Its focus-visible ring
 * comes from `App.vue`'s app-wide `.v-btn:focus-visible` rule
 * (P11-R-04), not a local style here.
 *
 * The visible "Copied!" text alone is not announced to assistive
 * tech (P11-R-21): a `v-if`-toggled node carries no `aria-live`, and
 * even if it did, a live region usually has to already exist in the
 * DOM before its text changes to be picked up reliably. A permanent,
 * screen-reader-only `aria-live="polite"` region carries the
 * announcement instead; the visible text stays `aria-hidden` so nothing
 * is announced twice.
 */
import { onBeforeUnmount, ref } from "vue";

const props = defineProps<{
  /** Exact value written to the clipboard. */
  value: string;
  /** What the value is, used in the accessible name, e.g. "digest"
   *  or "full UUID". */
  label: string;
}>();

const copied = ref(false);
/** Text of the screen-reader-only live region; empty outside the
 *  "just copied" window so the next copy -- even of the same value --
 *  is still a change assistive tech picks up. */
const liveMessage = ref("");
let hideTimer: ReturnType<typeof setTimeout> | null = null;

/** Clear any pending "hide the confirmation" timer. Idempotent, so
 *  it is safe to call both before starting a new timer and on
 *  unmount. */
function clearHideTimer(): void {
  if (hideTimer !== null) {
    clearTimeout(hideTimer);
    hideTimer = null;
  }
}

/** Copy `value`, with a brief "Copied!" note on success, announced
 *  through the live region. */
async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.value);
    copied.value = true;
    liveMessage.value = `${props.label} copied to clipboard.`;
    clearHideTimer();
    hideTimer = setTimeout(() => {
      copied.value = false;
      liveMessage.value = "";
      hideTimer = null;
    }, 2000);
  } catch {
    // Clipboard API unavailable (e.g. insecure context); the value
    // is already visible or in a tooltip, so this is a soft failure.
  }
}

// A pending timer otherwise fires after the component is gone,
// touching refs nothing reads any more (P11-R-21).
onBeforeUnmount(clearHideTimer);
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
    <span v-if="copied" class="text-success" aria-hidden="true">Copied!</span>
    <span class="d-sr-only" role="status" aria-live="polite">
      {{ liveMessage }}
    </span>
  </span>
</template>
