<script setup lang="ts">
/**
 * One search-result row: title on line 1, source/project, short
 * status and issue chips on line 2. Extracted from `SearchView.vue` (Task 16,
 * P11-R-17 --
 * `module-code-structure-limits`' 500-line module limit) along a
 * natural seam: everything a row needs to render itself comes from
 * its own `item`, so this is a pure, self-contained component
 * (module-vue-vuetify "component design").
 */
import StatusChip from "@/components/StatusChip.vue";
import type { SearchItem } from "@/types/records";
import {
  candidateBranchText,
  issueIndicatorLabel,
  recordKindTypeLabel,
  searchApprovalStateLabel,
  searchErratumStatusLabel,
  searchRecordStateLabel,
} from "@/utils/labels";

defineProps<{
  /** The search-result item to render. */
  item: SearchItem;
  /** Whether a divider renders above this row (every row but the
   *  first in the list). */
  divided: boolean;
}>();

function recordHref(item: SearchItem): string {
  return `/records/${item.id}`;
}

/** This row's primary title: for an erratum, "Erratum for <target>"
 *  leads (so two rows both stored as "Erratum: Decision" are
 *  distinguishable by their target), with the erratum's own stored
 *  title shown as a secondary line; an ordinary decision just shows
 *  its title. */
function rowTitle(item: SearchItem): string {
  if (item.record_kind !== "erratum") {
    return item.title;
  }
  return item.erratum_for_title
    ? `Erratum for ${item.erratum_for_title}`
    : "Erratum for an unknown decision";
}
</script>

<template>
  <li class="result-row" :class="{ 'border-t': divided }">
    <router-link
      :to="recordHref(item)"
      class="result-link d-flex flex-column py-3 px-1
        text-decoration-none"
    >
      <span class="text-title-medium">{{ rowTitle(item) }}</span>
      <span
        v-if="item.record_kind === 'erratum'"
        class="text-body-medium text-medium-emphasis"
      >
        {{ item.title }}
      </span>
      <div class="d-flex flex-wrap align-center ga-2 mt-1">
        <span class="text-body-medium text-medium-emphasis">
          {{ item.source_id }} / {{ item.project }}
          <template v-if="candidateBranchText(item.kind, item.ref)">
            · {{ candidateBranchText(item.kind, item.ref) }}
          </template>
        </span>
        <StatusChip
          v-if="searchRecordStateLabel(item.kind)"
          v-bind="searchRecordStateLabel(item.kind)!"
        />
        <StatusChip
          v-if="item.record_kind === 'erratum'"
          v-bind="recordKindTypeLabel(item.record_kind)"
        />
        <StatusChip
          v-if="item.record_kind === 'erratum'"
          v-bind="
            searchErratumStatusLabel(item.approval_state, item.approvable)
          "
        />
        <StatusChip
          v-else
          v-bind="
            searchApprovalStateLabel(item.approval_state, item.approvable)
          "
        />
        <StatusChip
          v-if="issueIndicatorLabel(item.issue_counts)"
          v-bind="issueIndicatorLabel(item.issue_counts)!"
        />
      </div>
    </router-link>
  </li>
</template>

<style scoped>
.result-link {
  /* No Vuetify utility sets an anchor's text colour to "inherit from
     context"; without this a router-link renders browser-default
     link blue. */
  color: inherit;
}

.result-link:hover,
.result-link:focus-visible {
  /* Hover/focus highlight at the theme's on-surface token, low
     opacity -- Vuetify has no built-in hover treatment for a plain
     router-link acting as a row. */
  background: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
