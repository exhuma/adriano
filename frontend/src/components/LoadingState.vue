<script setup lang="ts">
/**
 * Deliberate loading placeholder for a section of content
 * (module-ux-principles "Feedback & visibility of system status").
 * Announced to assistive tech via `role="status"`.
 */
defineProps<{
  /** Visible and screen-reader text describing what is loading. */
  text?: string;
}>();
</script>

<template>
  <div
    class="loading-state d-flex flex-column align-center text-center
      ga-3 py-8 px-4"
    role="status"
  >
    <v-progress-circular indeterminate color="primary" size="32" />
    <p class="text-body-medium text-medium-emphasis">
      {{ text ?? "Loading…" }}
    </p>
  </div>
</template>

