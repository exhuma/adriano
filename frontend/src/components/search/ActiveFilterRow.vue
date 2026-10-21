<script setup lang="ts">
/**
 * The search page's persistent active-filter row (S-04): one
 * closable `v-chip` per active filter mode inside a
 * `role="status" aria-live="polite"` region, per the
 * `module-vue-vuetify` mode-indicator rules. Which filters are
 * active, their order, and their label/icon/colour is decided by
 * `utils/activeFilters.ts` (a plain TypeScript module, per
 * `module-interaction-core`); this component only renders whatever
 * it is handed. Extracted from `SearchView.vue`.
 *
 * P11-R-05: the "Clear filters" action clears only the filters this
 * row's chips represent -- never the free-text query or the sort
 * order, and it is shown only once there is at least one chip to
 * clear (`chips.length > 0`), not whenever any filter-ish thing,
 * including the query text, is set. It also sits outside the
 * `role="status"` region: it is a persistent action beside the live
 * region, not part of the content that region announces.
 */
import type { ActiveFilterChip, FilterKey } from "@/utils/activeFilters";

defineProps<{
  /** Active filter chips, in their fixed display order; empty when
   *  no filter mode is active. */
  chips: ActiveFilterChip[];
}>();

const emit = defineEmits<{
  /** The named chip's close button was activated. */
  "clear-filter": [key: FilterKey];
  /** "Clear filters" was activated. */
  "clear-filters": [];
}>();

/**
 * This row's own `v-chip` size, larger than the app-wide "small"
 * default (`plugins/vuetify.ts`) so each chip has enough padding
 * around its close button for the 24x24 px target fix below
 * (P11-R-12) to read as part of the chip rather than crowding its
 * label -- scoped via `<v-defaults-provider>` (ladder step 3) since
 * only this one region needs a larger chip.
 */
const chipRowDefaults = { VChip: { size: "default" } } as const;
</script>

<template>
  <div class="d-flex flex-wrap align-center ga-2" :class="{ 'mt-3': chips.length > 0 }">
    <div role="status" aria-live="polite" class="d-flex flex-wrap align-center ga-2">
      <v-defaults-provider :defaults="chipRowDefaults">
        <v-chip
          v-for="chip in chips"
          :key="chip.key"
          :color="chip.color"
          :prepend-icon="chip.icon"
          closable
          :close-label="`Remove filter: ${chip.label}`"
          @click:close="emit('clear-filter', chip.key)"
        >
          {{ chip.label }}
        </v-chip>
      </v-defaults-provider>
    </div>

    <v-btn
      v-if="chips.length > 0"
      variant="text"
      prepend-icon="mdi-filter-remove-outline"
      @click="emit('clear-filters')"
    >
      Clear filters
    </v-btn>
  </div>
</template>

<style scoped>
/*
 * P11-R-12: a closable `v-chip`'s close button is a fixed 18x18 px
 * box in Vuetify ($chip-close-size in
 * vuetify/lib/components/VChip/_variables.scss) -- independent of
 * the VChip `size` prop above, which only resizes the chip's own
 * font/height/padding, never this child button's own
 * max-height/max-width. No theme colour, component default, or
 * utility class reaches that Vuetify-internal child element's box
 * size, and reaching the SASS variable itself would mean switching
 * the whole app off Vuetify's precompiled CSS (`import
 * "vuetify/styles"` in plugins/vuetify.ts) onto a full SASS-source
 * build for one target-size fix. This scoped override (ladder step
 * 6, last resort) grows the clickable box to the 24x24 px minimum
 * (module-ux-principles Fitt's law / WCAG 2.5.5 target size);
 * `justify-content: center` keeps the (still 18px) icon glyph
 * centred in the now-larger box.
 */
:deep(.v-chip__close) {
  min-width: 24px;
  min-height: 24px;
  justify-content: center;
}
</style>
