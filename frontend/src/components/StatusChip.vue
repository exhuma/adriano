<script setup lang="ts">
/**
 * Compact status indicator that always pairs an icon with text, so
 * status is never communicated by colour alone (module-ux-principles
 * "Do not rely on color alone").
 */
defineProps<{
  /** Material Design Icons name, e.g. "mdi-check-circle". */
  icon: string;
  /** Visible label describing the status. */
  text: string;
  /** Vuetify theme colour token, e.g. "success", "error", "warning". */
  color?: string;
  /**
   * Full meaning announced to assistive tech and shown as a hover
   * title, for when `text` has been shortened for space (e.g. "DEV"
   * standing in for "DEV LOGIN"). Falls back to `text` when omitted.
   */
  ariaLabel?: string;
}>();
</script>

<template>
  <v-chip
    :color="color"
    :aria-label="ariaLabel"
    :title="ariaLabel"
  >
    <!-- size/variant come from the global VChip defaults
         (plugins/vuetify.ts) instead of being restated here, so
         every v-chip in the app -- this component's only current
         caller included -- stays in sync automatically. -->

    <v-icon :icon="icon" start aria-hidden="true" />
    {{ text }}
  </v-chip>
</template>
