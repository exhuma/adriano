<script setup lang="ts">
/**
 * The search page's filter bar: source/project/state/record-type
 * selectors, the sort control, and the "needs approval" switch,
 * extracted from `SearchView.vue` (phases/11-ui-ux-updates.md Task
 * 16, P11-R-17 -- `module-code-structure-limits`' 500-line module
 * limit) along a natural seam: everything here is a pure, stateless
 * filter-bar control, bound to its caller's refs via `v-model:*`.
 * Facet data (`sourceOptions`/`projectOptions`), the sort options
 * list, and the API fetch all stay in `SearchView.vue`, which owns
 * the business logic; this component only renders whatever it is
 * handed (module-vue-vuetify "component design": prefer pure
 * components).
 */
import { computed } from "vue";

import type {
  RecordState,
  RecordTypeFilter,
  SearchSort,
} from "@/types/records";
import type { StateFilter } from "@/composables/useSearchQuery";

/** One labelled option for a `v-select`. */
interface SelectOption<T> {
  title: string;
  value: T;
}

const props = defineProps<{
  /** Current `source` filter value, `""` for "all sources". */
  source: string;
  /** Current `project` filter value, `""` for "all projects". */
  project: string;
  /** Current publication-state filter, `""` for "all". */
  state: StateFilter;
  /** Current `record_type` filter. */
  recordType: RecordTypeFilter;
  /** Current sort order. */
  sort: SearchSort;
  /** Whether the "needs approval" filter is active. */
  needsApproval: boolean;
  /** Source facet options, derived from the loaded catalog facets. */
  sourceOptions: SelectOption<string>[];
  /** Project facet options, narrowed to the current source if any. */
  projectOptions: SelectOption<string>[];
  /** Sort options currently on offer ("Relevance" only with a query). */
  sortItems: SelectOption<SearchSort>[];
  /** Whether loading the facets failed, disabling source/project. */
  facetsFailed: boolean;
  /** The needs-approval info button/tooltip's full hint text. */
  needsApprovalHint: string;
}>();

const emit = defineEmits<{
  /** The source filter changed. */
  "update:source": [value: string];
  /** The project filter changed. */
  "update:project": [value: string];
  /** The publication-state filter changed. */
  "update:state": [value: StateFilter];
  /** The record-type filter changed. */
  "update:recordType": [value: RecordTypeFilter];
  /** The sort order changed. */
  "update:sort": [value: SearchSort];
  /** The needs-approval filter changed. */
  "update:needsApproval": [value: boolean];
}>();

const source = computed({
  get: () => props.source,
  set: (value: string) => emit("update:source", value),
});
const project = computed({
  get: () => props.project,
  set: (value: string) => emit("update:project", value),
});
const state = computed({
  get: () => props.state,
  set: (value: RecordState | "") => emit("update:state", value),
});
const recordType = computed({
  get: () => props.recordType,
  set: (value: RecordTypeFilter) => emit("update:recordType", value),
});
const sort = computed({
  get: () => props.sort,
  set: (value: SearchSort) => emit("update:sort", value),
});
const needsApproval = computed({
  get: () => props.needsApproval,
  set: (value: boolean) => emit("update:needsApproval", value),
});

/**
 * One shared control density for the whole filter bar
 * (phases/11-ui-ux-updates.md Task 4, S-03: "use one density for the
 * whole bar so every control shares a top line") -- a
 * `<v-defaults-provider>` (ladder step 3) rather than a global
 * default, since only this one region needs it.
 */
const filterBarDefaults = {
  VSelect: { density: "compact" },
  VBtnToggle: { density: "compact" },
  VBtn: { density: "compact" },
  VSwitch: { density: "compact" },
} as const;
</script>

<template>
  <!--
    S-03: one `<v-defaults-provider>` density for every control in
    the bar, so they share a top line/height (ladder step 3);
    min/max-width via component props, not CSS, bound each select
    (ladder step 4).
  -->
  <v-defaults-provider :defaults="filterBarDefaults">
    <div class="d-flex flex-wrap align-center ga-3 mt-2">
      <v-select
        v-model="source"
        :items="[{ title: 'All sources', value: '' }, ...sourceOptions]"
        label="Source"
        variant="outlined"
        min-width="140"
        max-width="200"
        :disabled="facetsFailed"
      />
      <v-select
        v-model="project"
        :items="[{ title: 'All projects', value: '' }, ...projectOptions]"
        label="Project"
        variant="outlined"
        min-width="140"
        max-width="200"
        :disabled="facetsFailed"
      />
      <v-btn-toggle
        v-model="state"
        mandatory
        color="primary"
        variant="outlined"
        divided
        aria-label="Filter by publication state"
      >
        <v-btn value="" aria-label="Show all records">All</v-btn>
        <v-btn value="published" aria-label="Show published records only">
          Published
        </v-btn>
        <v-btn value="candidate" aria-label="Show candidate records only">
          Candidate
        </v-btn>
      </v-btn-toggle>

      <v-select
        v-model="recordType"
        :items="[
          { title: 'Decisions', value: 'decision' },
          { title: 'Errata', value: 'erratum' },
          { title: 'Both', value: 'all' },
        ]"
        label="Show"
        variant="outlined"
        min-width="130"
        max-width="170"
      />

      <v-select
        v-model="sort"
        :items="sortItems"
        label="Sort by"
        variant="outlined"
        min-width="200"
        max-width="220"
      />

      <!--
        S-03: the switch's two-line hint moved into a tooltip, with
        `hide-details` so removing it doesn't leave an empty message
        slot behind (G-09). The info button goes in `v-switch`'s own
        `#append` slot (forwarded straight to `VInput`'s
        prepend/control/append layout, per VSwitch's source) rather
        than a hand-rolled flex sibling, so it is always positioned
        after the control+label by Vuetify's own layout, not by
        assumptions about how wide the switch renders.
        `density="default"` overrides the bar's shared compact
        density for this one instance (ladder step 4: "set a prop at
        the call site only when that instance has to differ") --
        `compact` density combined with `size="small"` put this icon
        button's hit target under the 24x24 px minimum (coordinator
        browser check). The button carries its own `aria-label` with
        the full hint text, so it stays accessible whether or not the
        hover/focus tooltip is open; `v-tooltip` with
        `activator="parent"` also wires a hover/focus-triggered
        tooltip onto that same (naturally focusable) button. Decision
        2 / S-04: the switch's `color="primary"`, not `warning` -- a
        deliberate, reversible filter is not a warning.
      -->
      <v-switch
        v-model="needsApproval"
        label="Needs approval"
        color="primary"
        hide-details="auto"
      >
        <template #append>
          <!--
            `<v-icon>` is explicit, not left to `v-btn`'s `icon` prop
            to auto-render: once a `v-btn` with an `icon` prop also
            gets default-slot content (the `v-tooltip` below),
            Vuetify treats that as "custom content supplied" and
            silently stops auto-rendering the prop's icon, leaving an
            empty, invisible button (coordinator browser check: no
            glyph ever painted, at any size).
          -->
          <v-btn
            icon="mdi-information-outline"
            variant="text"
            density="default"
            :aria-label="`Needs approval means: ${needsApprovalHint}`"
          >
            <v-icon icon="mdi-information-outline" aria-hidden="true" />
            <v-tooltip activator="parent" location="top">
              {{ needsApprovalHint }}
            </v-tooltip>
          </v-btn>
        </template>
      </v-switch>
    </div>
  </v-defaults-provider>
</template>
