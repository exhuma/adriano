<script setup lang="ts">
/**
 * Compact status indicator that always pairs an icon with text, so
 * status is never communicated by colour alone (module-ux-principles
 * "Do not rely on color alone").
 */
import { computed } from "vue";

const props = defineProps<{
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

/** Whether `text` was shortened and the full meaning needs to be
 *  exposed separately (P11-R-15). `v-chip` renders as a plain
 *  `<span>` by default (no implicit ARIA role), and `aria-label` has
 *  no defined mapping on a generic, non-interactive element -- axe's
 *  `aria-prohibited-attr` rule flags exactly this. Instead, when the
 *  two differ, the short visible text is hidden from assistive tech
 *  and the full text is read from ordinary (visually hidden) content,
 *  which every element exposes regardless of role. */
const needsFullText = computed(
  () => props.ariaLabel !== undefined && props.ariaLabel !== props.text,
);
</script>

<template>
  <v-chip :color="color" :title="ariaLabel ?? text">
    <!-- size/variant come from the global VChip defaults
         (plugins/vuetify.ts) instead of being restated here, so
         every v-chip in the app -- this component's only current
         caller included -- stays in sync automatically. -->

    <v-icon :icon="icon" start aria-hidden="true" />
    <span :aria-hidden="needsFullText ? 'true' : undefined">{{ text }}</span>
    <span v-if="needsFullText" class="d-sr-only">{{ ariaLabel }}</span>
  </v-chip>
</template>
