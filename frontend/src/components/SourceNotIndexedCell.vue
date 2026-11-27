<script setup lang="ts">
/**
 * The Sources table's "Not indexed" cell: how many documents of one
 * registration intake could not index, linking to the not-indexed
 * list filtered to that registration. A zero is plain text -- there
 * is nothing to follow.
 */
import { notIndexedListLocation } from "@/utils/notIndexedPaths";

defineProps<{
  /** The registration id. */
  sourceId: string;
  /** Documents of this registration that could not be indexed. */
  count: number;
}>();
</script>

<template>
  <router-link
    v-if="count > 0"
    :to="notIndexedListLocation(sourceId)"
    class="d-inline-block py-1 text-primary"
  >
    {{ count }} not indexed
  </router-link>
  <span v-else class="text-medium-emphasis">None</span>
</template>
