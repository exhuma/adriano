<script setup lang="ts">
/**
 * One Sources-table cell: a registration's problem (readable text or
 * a list, never raw JSON -- audit finding S3) plus its recovery
 * hint. Extracted from `SourcesView.vue` to keep that view within
 * the component-size target.
 */
import type { SourceProblemDisplay } from "@/utils/sourceErrors";

defineProps<{
  /** How to render the registration's problem, if any. */
  problem: SourceProblemDisplay;
  /** A concrete next step for the operator, or `null` when healthy. */
  hint: string | null;
}>();
</script>

<template>
  <template v-if="problem.kind !== 'none' || hint">
    <p v-if="problem.kind === 'text'" class="text-body-medium">
      {{ problem.text }}
    </p>
    <ul v-else-if="problem.kind === 'list'" class="problem-list">
      <li v-for="(item, index) in problem.items" :key="index" class="text-body-medium">
        {{ item.message }}
        <span v-if="item.code" class="text-body-small text-medium-emphasis">
          ({{ item.code }})
        </span>
      </li>
    </ul>
    <p v-if="hint" class="text-body-medium text-medium-emphasis">
      {{ hint }}
    </p>
  </template>
  <span v-else class="text-medium-emphasis">—</span>
</template>

<style scoped>
.problem-list {
  margin: 0;
  padding-inline-start: 1.1rem;
}
</style>
