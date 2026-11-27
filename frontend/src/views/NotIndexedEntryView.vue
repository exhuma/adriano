<script setup lang="ts">
/**
 * Detail of one not-indexed entry: its location, how it was found,
 * why it was not indexed, and the content intake rejected, read-only
 * and monospaced. The location comes from the query string
 * (`source_id`, `project`, `path`, `ref`: project, path and ref
 * contain slashes). `content` is `null` when intake could not store
 * or read the document; the page says so instead of showing an empty
 * box. A 404 means the entry cleared on its own since the list was
 * read, which is the good outcome, and is worded that way.
 */
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { ApiError } from "@/api";
import { getNotIndexedEntry } from "@/api/notIndexed";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import StatusChip from "@/components/StatusChip.vue";
import NotIndexedLinks from "@/components/notIndexed/NotIndexedLinks.vue";
import NotIndexedReasons from "@/components/notIndexed/NotIndexedReasons.vue";
import { withLoading } from "@/composables/useLoading";
import { readString } from "@/composables/useNotIndexedQuery";
import type { NotIndexedDetail, NotIndexedLocation } from "@/types/notIndexed";
import { forbiddenText, isForbidden } from "@/utils/apiErrors";
import { formatDateTime } from "@/utils/dates";
import { originLabel } from "@/utils/labels";
import { notIndexedListLocation } from "@/utils/notIndexedPaths";

type LoadState = "loading" | "loaded" | "cleared" | "error";

const route = useRoute();
const loadState = ref<LoadState>("loading");
const errorText = ref<string | null>(null);
const entry = ref<NotIndexedDetail | null>(null);

const location = computed<NotIndexedLocation>(() => ({
  source_id: readString(route.query.source_id),
  project: readString(route.query.project),
  path: readString(route.query.path),
  ref: readString(route.query.ref),
}));

async function load(): Promise<void> {
  loadState.value = "loading";
  errorText.value = null;
  try {
    entry.value = await withLoading(() => getNotIndexedEntry(location.value));
    loadState.value = "loaded";
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      loadState.value = "cleared";
      return;
    }
    errorText.value = isForbidden(error)
      ? forbiddenText(error)
      : "The entry could not be loaded. Check your connection and try again.";
    loadState.value = "error";
  }
}

watch(location, load, { immediate: true });
</script>

<template>
  <section aria-labelledby="not-indexed-entry-heading">
    <v-btn
      :to="notIndexedListLocation(location.source_id)"
      variant="text"
      color="primary"
      prepend-icon="mdi-arrow-left"
      class="mb-2"
    >
      Back to the list
    </v-btn>

    <LoadingState v-if="loadState === 'loading'" text="Loading the entry…" />

    <div
      v-else-if="loadState === 'cleared'"
      class="d-flex flex-column align-center text-center py-12 px-4"
    >
      <v-icon
        icon="mdi-check-circle-outline"
        size="48"
        color="medium-emphasis"
        aria-hidden="true"
      />
      <h1
        id="not-indexed-entry-heading"
        class="text-headline-medium font-weight-medium mt-2"
      >
        This entry is gone
      </h1>
      <p class="text-body-medium text-medium-emphasis">
        The file was fixed or removed since the list was loaded, so the
        entry cleared on its own.
      </p>
    </div>

    <ErrorState
      v-else-if="loadState === 'error'"
      title="Couldn't load this entry"
      :text="errorText ?? undefined"
      @retry="load"
    />

    <template v-else-if="entry">
      <h1
        id="not-indexed-entry-heading"
        class="text-headline-medium font-weight-medium text-wrap mb-1"
      >
        {{ entry.path }}
      </h1>
      <p class="text-body-medium text-medium-emphasis mb-2">
        {{ entry.source_id }} / {{ entry.project }} @ {{ entry.ref }}
      </p>
      <div class="d-flex flex-wrap align-center ga-2 mb-2">
        <StatusChip
          :icon="entry.origin === 'push' ? 'mdi-upload' : 'mdi-cloud-sync-outline'"
          :text="originLabel(entry.origin)"
        />
        <span class="text-body-small text-medium-emphasis">
          First seen {{ formatDateTime(entry.first_seen_at) }} · last seen
          {{ formatDateTime(entry.last_seen_at) }}
        </span>
      </div>

      <v-alert
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
        icon="mdi-information-outline"
      >
        This entry disappears on its own once the file is fixed or
        removed in its repository. There is nothing to dismiss here.
      </v-alert>

      <v-card class="mb-4">
        <v-card-title tag="h2" class="text-title-large">
          Why it was not indexed
        </v-card-title>
        <v-card-text>
          <NotIndexedReasons :reasons="entry.reasons" />
        </v-card-text>
        <v-card-actions>
          <NotIndexedLinks
            :source-url="entry.source_url"
            :holder-uuid="entry.holder_uuid"
          />
        </v-card-actions>
      </v-card>

      <v-card>
        <v-card-title tag="h2" class="text-title-large">
          Rejected content
        </v-card-title>
        <v-card-text>
          <!-- Browser `<pre>` is monospace (the diff panel relies on
               the same UA default); scrolling and spacing are
               utility classes. -->
          <pre
            v-if="entry.content !== null"
            class="overflow-auto ma-0 pa-3 border rounded text-body-small"
            tabindex="0"
            aria-label="Rejected document content"
          >{{ entry.content }}</pre>
          <p v-else class="text-body-medium text-medium-emphasis">
            The content of this document was not stored, so it cannot be
            shown. Open the file in its repository instead.
          </p>
        </v-card-text>
      </v-card>
    </template>
  </section>
</template>
