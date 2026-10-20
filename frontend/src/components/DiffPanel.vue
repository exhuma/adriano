<script setup lang="ts">
/**
 * Unified diff between two stored content snapshots of one record's
 * identity. Loads the server default (last decided snapshot, else
 * the previous revision, else "no prior revision") on mount, and
 * offers a cheap selector over the digests already known to the
 * page (current, previous, decision history, identity siblings) to
 * compare any other pair without a second network round trip for
 * the option list itself.
 */
import { computed, onMounted, ref, watch } from "vue";

import { ApiError } from "@/api";
import { getRecordDiff } from "@/api/records";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import type {
  CompetingCandidateOut,
  DecisionSummaryOut,
  RecordDiffOut,
} from "@/types/approval";
import type { SiblingOut } from "@/types/records";
import { classifyDiffLines } from "@/utils/diff";
import { formatDateTime } from "@/utils/dates";
import { shortDigest } from "@/utils/digest";

const props = defineProps<{
  /** Record id to diff. */
  recordId: string;
  /** The record's current digest. */
  currentDigest: string;
  /** The record's previous stored digest, if any. */
  previousDigest: string | null;
  /** Owning source/registration id, for the header. */
  sourceId: string;
  /** Project path within the source, for the header. */
  project: string;
  /** Branch/ref the content came from, for the header. */
  refName: string;
  /** When the owning registration last indexed successfully, for the
   *  header (`null` if it never has). */
  lastIndexedAt: string | null;
  /** Decision history of the identity, for the digest selector. */
  history: DecisionSummaryOut[];
  /** Identity siblings (published/candidates), for the selector. */
  siblings: SiblingOut[];
  /** Competing candidates, also offered in the selector. */
  competingCandidates: CompetingCandidateOut[];
}>();

type LoadState = "loading" | "loaded" | "error";

const loadState = ref<LoadState>("loading");
const diff = ref<RecordDiffOut | null>(null);
const errorText = ref<string | null>(null);
const fromDigest = ref<string | undefined>(undefined);
const toDigest = ref<string | undefined>(undefined);

/** Every digest known to this page, deduplicated, for the "compare
 *  against" selectors -- cheap because it is built from data the
 *  page already has. */
const digestOptions = computed(() => {
  const seen = new Map<string, string>();
  seen.set(props.currentDigest, `Current revision (${shortDigest(props.currentDigest)})`);
  if (props.previousDigest) {
    seen.set(
      props.previousDigest,
      `Previous revision (${shortDigest(props.previousDigest)})`,
    );
  }
  for (const event of props.history) {
    const word = event.action === "accepted" ? "Accepted" : "Rejected";
    seen.set(event.digest, `${word} (${shortDigest(event.digest)})`);
  }
  for (const sibling of props.siblings) {
    const kind = sibling.kind === "candidate" ? `candidate @ ${sibling.ref}` : "published";
    seen.set(sibling.digest, `${kind} (${shortDigest(sibling.digest)})`);
  }
  for (const candidate of props.competingCandidates) {
    seen.set(
      candidate.digest,
      `candidate @ ${candidate.ref} (${shortDigest(candidate.digest)})`,
    );
  }
  return [...seen.entries()].map(([value, title]) => ({ value, title }));
});

const diffLines = computed(() =>
  diff.value ? classifyDiffLines(diff.value.unified_diff) : [],
);

const summaryText = computed(() => {
  if (!diff.value) {
    return "";
  }
  const added = diff.value.lines_added;
  const removed = diff.value.lines_removed;
  return `${added} line${added === 1 ? "" : "s"} added, ` +
    `${removed} line${removed === 1 ? "" : "s"} removed`;
});

async function load(): Promise<void> {
  loadState.value = "loading";
  errorText.value = null;
  try {
    diff.value = await getRecordDiff(props.recordId, {
      from: fromDigest.value,
      to: toDigest.value,
    });
    loadState.value = "loaded";
  } catch (error) {
    errorText.value =
      error instanceof ApiError
        ? `The diff could not be loaded (status ${error.status}).`
        : "The diff could not be loaded. Check your connection and try again.";
    loadState.value = "error";
  }
}

onMounted(load);
watch([fromDigest, toDigest], load);
</script>

<template>
  <v-card class="mb-4">
    <v-card-title tag="h2" class="text-title-large">Diff</v-card-title>
    <v-card-subtitle class="diff-source">
      {{ sourceId }} / {{ project }} @ {{ refName }} — last indexed
      {{ lastIndexedAt ? formatDateTime(lastIndexedAt) : "never" }}
    </v-card-subtitle>

    <v-card-text v-if="digestOptions.length > 2" class="diff-selectors">
      <v-select
        v-model="fromDigest"
        :items="[{ title: 'Default base', value: undefined }, ...digestOptions]"
        label="Compare from"
        density="comfortable"
        variant="outlined"
        class="diff-select"
      />
      <v-select
        v-model="toDigest"
        :items="[{ title: 'Default target (current)', value: undefined }, ...digestOptions]"
        label="Compare to"
        density="comfortable"
        variant="outlined"
        class="diff-select"
      />
    </v-card-text>

    <v-card-text v-if="loadState === 'loading'">
      <LoadingState text="Loading diff…" />
    </v-card-text>

    <v-card-text v-else-if="loadState === 'error'">
      <ErrorState
        title="Couldn't load the diff"
        :text="errorText ?? undefined"
        @retry="load"
      />
    </v-card-text>

    <template v-else-if="diff">
      <v-card-text class="text-body-medium">
        <span v-if="diff.base">
          <strong>{{ diff.base.label }}</strong>
          (<code :title="diff.base.digest">{{ shortDigest(diff.base.digest) }}</code>
          <span v-if="diff.base.decided_at">
            , {{ formatDateTime(diff.base.decided_at) }}</span>)
          →
        </span>
        <strong>{{ diff.target.label }}</strong>
        (<code :title="diff.target.digest">{{ shortDigest(diff.target.digest) }}</code>
        <span v-if="diff.target.decided_at">
          , {{ formatDateTime(diff.target.decided_at) }}</span>)
      </v-card-text>

      <v-card-text v-if="diff.reason === 'no_prior_revision'" class="text-body-medium text-medium-emphasis">
        No prior revision exists to compare against.
      </v-card-text>
      <v-card-text v-else-if="diff.identical" class="text-body-medium">
        <v-icon icon="mdi-equal" size="small" aria-hidden="true" class="mr-1" />
        These two revisions are identical.
      </v-card-text>
      <v-card-text v-else>
        <p class="sr-only" role="status">{{ summaryText }}</p>
        <p class="text-body-small text-medium-emphasis mb-1">
          Legend: lines starting with
          <code>+</code> were added, lines starting with <code>-</code> were
          removed (also {{ summaryText }}).
        </p>
        <pre class="diff-pre" aria-hidden="false"><span
            v-for="(line, index) in diffLines"
            :key="index"
            :class="`diff-line diff-line--${line.kind}`"
          >{{ line.text }}
</span></pre>
      </v-card-text>
    </template>
  </v-card>
</template>

<style scoped>
.diff-source {
  white-space: normal;
  opacity: var(--v-medium-emphasis-opacity);
}

.diff-selectors {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.diff-select {
  min-width: 14rem;
  flex: 1 1 14rem;
}

.diff-pre {
  overflow-x: auto;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", Menlo, monospace;
  font-size: 0.8125rem;
  line-height: 1.4;
  white-space: pre;
  margin: 0;
  padding: 0.5rem;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
}

.diff-line {
  display: block;
}

.diff-line--added {
  background: rgba(var(--v-theme-success), 0.12);
}

.diff-line--removed {
  background: rgba(var(--v-theme-error), 0.12);
}

.diff-line--hunk {
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
