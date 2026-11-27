<script setup lang="ts">
/**
 * The not-indexed list's filter bar: source, project, reason and
 * origin. Pure and stateless -- bound to the caller's refs with
 * `v-model:*`; the options are passed in. One shared control density
 * for the bar via `<v-defaults-provider>` (Vuetify-first ladder
 * step 3), like the search page's filter bar.
 */
import { computed } from "vue";

import type { OriginFilter } from "@/composables/useNotIndexedQuery";

/** One labelled option for a `v-select`. */
interface SelectOption<T> {
  title: string;
  value: T;
}

const props = defineProps<{
  /** Current `source` filter, `""` for all registrations. */
  source: string;
  /** Current `project` filter, `""` for all projects. */
  project: string;
  /** Current `reason` filter (an issue code), `""` for all. */
  reason: string;
  /** Current `origin` filter, `""` for both intakes. */
  origin: OriginFilter;
  /** Registrations to offer. */
  sourceOptions: SelectOption<string>[];
  /** Reasons to offer. */
  reasonOptions: SelectOption<string>[];
}>();

const emit = defineEmits<{
  "update:source": [value: string];
  "update:project": [value: string];
  "update:reason": [value: string];
  "update:origin": [value: OriginFilter];
}>();

const source = computed({
  get: () => props.source,
  set: (value: string) => emit("update:source", value ?? ""),
});
const project = computed({
  get: () => props.project,
  set: (value: string) => emit("update:project", value ?? ""),
});
const reason = computed({
  get: () => props.reason,
  set: (value: string) => emit("update:reason", value ?? ""),
});
const origin = computed({
  get: () => props.origin,
  set: (value: OriginFilter) => emit("update:origin", value ?? ""),
});

const filterBarDefaults = {
  VSelect: { density: "compact", variant: "outlined" },
  VTextField: { density: "compact", variant: "outlined" },
} as const;
</script>

<template>
  <v-defaults-provider :defaults="filterBarDefaults">
    <div class="d-flex flex-wrap align-center ga-3 mt-2">
      <v-select
        v-model="source"
        :items="[{ title: 'All sources', value: '' }, ...sourceOptions]"
        label="Source"
        min-width="160"
        max-width="220"
      />
      <v-text-field
        v-model="project"
        label="Project"
        clearable
        min-width="160"
        max-width="240"
      />
      <v-select
        v-model="reason"
        :items="[{ title: 'All reasons', value: '' }, ...reasonOptions]"
        label="Reason"
        min-width="220"
        max-width="360"
      />
      <v-select
        v-model="origin"
        :items="[
          { title: 'Polled or pushed', value: '' },
          { title: 'Polled', value: 'poll' },
          { title: 'Pushed', value: 'push' },
        ]"
        label="Found by"
        min-width="170"
        max-width="220"
      />
    </div>
  </v-defaults-provider>
</template>
