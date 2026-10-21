<script setup lang="ts">
/**
 * One Sources-table cell: a registration's problem (readable text or
 * a list, never raw JSON -- audit finding S3) plus its recovery
 * hint. Rendered by `SourcesView.vue` inside a full-width sub-row
 * under a failing registration, not a dedicated table column
 * (a far-right "Problem & recovery" column was
 * the one most likely to be scrolled out of view, and the operator
 * needs it most). Extracted to keep that view within the
 * component-size target.
 *
 * Each `list`-kind item's stable `code`, when recognised, is shown
 * as a plain-language headline with the
 * backend's own message kept underneath as secondary "Details" text
 * -- never discarded, since it carries the per-instance specifics
 * (which project, which file). A `config`-kind problem (a
 * registration's `config_error`) is labelled the same way from its
 * stable `config_error_code`. A `text`-kind problem (no code at all)
 * gets a generic "Problem" headline instead.
 *
 * Operator-only detail (env-var names, recovery steps) is gated by
 * `canOperate` (decision 3, Task 8): a reader sees only the
 * Status/Last-attempt/Last-success columns elsewhere in the row, and
 * this cell renders the same dash fallback as "nothing to show" for
 * them, regardless of whether a problem exists.
 */
import type { SourceProblemDisplay } from "@/utils/sourceErrors";
import { configErrorLabel, pollProblemLabel } from "@/utils/labels";

defineProps<{
  /** How to render the registration's problem, if any. */
  problem: SourceProblemDisplay;
  /** A concrete next step for the operator, or `null` when healthy. */
  hint: string | null;
  /** Whether the caller has the `operate` permission; `false` hides
   *  this cell's content entirely (decision 3: readers see status
   *  and dates only). */
  canOperate: boolean;
}>();
</script>

<template>
  <template v-if="canOperate && (problem.kind !== 'none' || hint)">
    <p v-if="problem.kind === 'text'" class="text-body-medium">
      <span class="text-label-large d-block">Problem</span>
      {{ problem.text }}
    </p>
    <p v-else-if="problem.kind === 'config'" class="text-body-medium">
      <span class="text-label-large d-block">Configuration problem</span>
      {{ configErrorLabel(problem.code) ?? problem.text }}
      <span
        v-if="configErrorLabel(problem.code)"
        class="text-body-small text-medium-emphasis d-block"
      >
        Details: {{ problem.text }}
      </span>
    </p>
    <ul v-else-if="problem.kind === 'list'" class="ma-0 ps-4">
      <li v-for="(item, index) in problem.items" :key="index" class="text-body-medium">
        {{ pollProblemLabel(item.code) ?? item.message }}
        <span
          v-if="pollProblemLabel(item.code)"
          class="text-body-small text-medium-emphasis d-block"
        >
          Details: {{ item.message }}
        </span>
      </li>
    </ul>
    <p v-if="hint" class="text-body-medium text-medium-emphasis">
      {{ hint }}
    </p>
  </template>
  <span v-else class="text-medium-emphasis">—</span>
</template>

