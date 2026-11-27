<script setup lang="ts">
/**
 * "Not indexed" page: the documents intake could not index, newest
 * first, page by page, with filters for source, project, reason and
 * origin. Readable by every signed-in user. The list is read-only:
 * an entry clears on its own once the file is fixed or removed, so
 * there is deliberately no dismiss action, and the page says so.
 *
 * The filters and the page live in the URL (`useNotIndexedQuery`),
 * so a filtered list is shareable and the Sources page can link here
 * per registration. Results are fetched whenever the URL query
 * changes. The filter bar and one entry are their own components
 * (`NotIndexedFilterBar`, `NotIndexedRow`).
 */
import { computed, onMounted, ref, shallowRef, watch } from "vue";
import { useRoute } from "vue-router";

import { ApiError } from "@/api";
import { listNotIndexed } from "@/api/notIndexed";
import { listSources } from "@/api/sources";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import NotIndexedFilterBar from "@/components/notIndexed/NotIndexedFilterBar.vue";
import NotIndexedRow from "@/components/notIndexed/NotIndexedRow.vue";
import { withLoading } from "@/composables/useLoading";
import {
  readOrigin,
  readPage,
  readString,
  useNotIndexedQuery,
} from "@/composables/useNotIndexedQuery";
import type { NotIndexedPage, NotIndexedParams } from "@/types/notIndexed";
import { forbiddenText, isForbidden } from "@/utils/apiErrors";
import { notIndexedReasonOptions } from "@/utils/labels";

const PAGE_SIZE = 20;

type LoadState = "loading" | "loaded" | "error";

const route = useRoute();
const { source, project, reason, origin, page, clearFilters } =
  useNotIndexedQuery();

const loadState = ref<LoadState>("loading");
const errorText = ref<string | null>(null);
const results = ref<NotIndexedPage | null>(null);
// `shallowRef`: replaced wholesale; `SourceOut.last_error` is the
// recursive `JsonValue` type that Vue's deep unwrapping cannot handle.
const sourceIds = shallowRef<string[]>([]);

onMounted(async () => {
  try {
    sourceIds.value = (await listSources()).map((entry) => entry.id);
  } catch {
    // The source filter just offers nothing; the list still works.
  }
});

const sourceOptions = computed(() =>
  sourceIds.value.map((id) => ({ title: id, value: id })),
);
const reasonOptions = notIndexedReasonOptions();

/** The filters as committed to the URL (never the half-typed ones). */
const committedParams = computed<NotIndexedParams>(() => ({
  source_id: readString(route.query.source) || undefined,
  project: readString(route.query.project) || undefined,
  reason: readString(route.query.reason) || undefined,
  origin: readOrigin(route.query.origin) || undefined,
  page: readPage(route.query.page),
  page_size: PAGE_SIZE,
}));

const hasActiveFilters = computed(() => {
  const { source_id, project, reason, origin } = committedParams.value;
  return Boolean(source_id || project || reason || origin);
});

/** Requests are numbered so a slow, stale response never overwrites
 *  a newer one. */
let latestRequest = 0;

async function fetchEntries(): Promise<void> {
  const current = ++latestRequest;
  loadState.value = "loading";
  errorText.value = null;
  try {
    const next = await withLoading(() => listNotIndexed(committedParams.value));
    if (current !== latestRequest) {
      return;
    }
    results.value = next;
    loadState.value = "loaded";
  } catch (error) {
    if (current !== latestRequest) {
      return;
    }
    errorText.value = isForbidden(error)
      ? forbiddenText(error)
      : error instanceof ApiError
        ? `The list could not be loaded (status ${error.status}). ` +
          "Check your connection and try again."
        : "The list could not be loaded. Check your connection and try again.";
    loadState.value = "error";
  }
}

watch(committedParams, fetchEntries, { immediate: true });

const pageCount = computed(() =>
  results.value ? Math.max(1, Math.ceil(results.value.total / PAGE_SIZE)) : 1,
);

const resultSummary = computed(() => {
  if (!results.value || results.value.total === 0) {
    return "";
  }
  const first = (results.value.page - 1) * PAGE_SIZE + 1;
  const last = first + results.value.items.length - 1;
  const total = results.value.total;
  return `Showing ${first}–${last} of ${total} ${
    total === 1 ? "document" : "documents"
  }.`;
});
</script>

<template>
  <section aria-labelledby="not-indexed-heading">
    <h1
      id="not-indexed-heading"
      class="text-headline-medium font-weight-medium mb-2"
    >
      Not indexed
    </h1>
    <p class="text-body-medium text-medium-emphasis mb-2">
      Documents the catalog found but could not index, newest first.
      An entry disappears on its own once the file is fixed or removed
      in its repository; there is nothing to dismiss here.
    </p>

    <NotIndexedFilterBar
      v-model:source="source"
      v-model:project="project"
      v-model:reason="reason"
      v-model:origin="origin"
      :source-options="sourceOptions"
      :reason-options="reasonOptions"
    />

    <p class="d-sr-only" role="status" aria-live="polite">
      {{ resultSummary }}
    </p>

    <LoadingState v-if="loadState === 'loading'" text="Loading the list…" />

    <ErrorState
      v-else-if="loadState === 'error'"
      title="Couldn't load the not-indexed list"
      :text="errorText ?? undefined"
      @retry="fetchEntries"
    />

    <template v-else-if="results">
      <EmptyState
        v-if="results.total === 0 && !hasActiveFilters"
        class="mt-6"
        icon="mdi-check-circle-outline"
        title="Every document is indexed"
        text="Nothing is waiting here: the catalog could index every
          document it found."
      />
      <EmptyState
        v-else-if="results.total === 0"
        class="mt-6"
        icon="mdi-filter-off-outline"
        title="No entries match your filters"
        text="No document that failed to index matches this filter
          combination."
      >
        <template #actions>
          <v-btn
            color="primary"
            variant="tonal"
            prepend-icon="mdi-filter-remove-outline"
            @click="clearFilters"
          >
            Clear filters
          </v-btn>
        </template>
      </EmptyState>

      <template v-else>
        <p
          class="text-body-medium text-medium-emphasis mt-4 mb-2"
          aria-hidden="true"
        >
          {{ resultSummary }}
        </p>

        <NotIndexedRow
          v-for="item in results.items"
          :key="`${item.source_id}|${item.project}|${item.path}|${item.ref}`"
          :item="item"
        />

        <v-pagination
          v-if="pageCount > 1"
          v-model="page"
          :length="pageCount"
          class="mt-4"
          aria-label="Not-indexed list pages"
        />
      </template>
    </template>
  </section>
</template>
