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
}>();
</script>

<template>
  <v-chip :color="color" size="small" variant="tonal">
    <v-icon :icon="icon" start aria-hidden="true" />
    {{ text }}
  </v-chip>
</template>
