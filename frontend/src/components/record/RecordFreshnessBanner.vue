<script setup lang="ts">
/**
 * Record detail page status banners: the "content changed while
 * reviewing" notice and the polling-freshness warning. Combined here
 * because both are dismissed/shown notices about whether the content
 * being viewed is current (compare `DivergenceBanner`, which combines
 * two related but independent warnings the same way). The
 * superseded-by note moved to `RecordStatusBanners`, which shows it
 * as a prominent obsoleted/updated banner instead of a small
 * paragraph (rfc-editor.org/info layout).
 */
defineProps<{
  /** Whether the content changed while the caller was reviewing it. */
  digestChanged: boolean;
  /** Polling-freshness warning text, or `null` to hide the banner. */
  freshnessText: string | null;
}>();

defineEmits<{
  /** Caller dismissed the "content changed" banner. */
  "close-digest-changed": [];
}>();
</script>

<template>
  <v-alert
    v-if="digestChanged"
    type="warning"
    variant="tonal"
    icon="mdi-refresh-alert"
    closable
    class="mb-4"
    @click:close="$emit('close-digest-changed')"
  >
    The content changed while you were reviewing; review the new
    revision before deciding.
  </v-alert>

  <v-alert
    v-if="freshnessText"
    type="warning"
    variant="tonal"
    icon="mdi-clock-alert-outline"
    class="mb-4"
  >
    {{ freshnessText }}
  </v-alert>
</template>
