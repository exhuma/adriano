<script setup lang="ts">
/**
 * Divergence and competing-candidate warnings for the record page:
 * content divergence within one identity (published vs. accepted),
 * and other candidates of the same identity holding different
 * content, each a separate concern that can occur independently.
 * A competing candidate whose content cannot be decided shows the
 * neutral "Blocked" status (R-02, `approvalDisplayLabel`).
 * both `router-link`s had no colour class, so
 * each rendered in the browser's own link colour instead of the
 * theme; `text-primary` fixes both (verified >=4.5:1 against the
 * warning tonal tint and against plain `surface`,
 * `tests/plugins/vuetify.test.ts`).
 */
import StatusChip from "@/components/StatusChip.vue";
import type { CompetingCandidateOut, DivergenceOut } from "@/types/approval";
import type { RecordKind } from "@/types/records";
import { shortDigest } from "@/utils/digest";
import { approvalDisplayLabel, divergenceLabel } from "@/utils/labels";

defineProps<{
  /** Content divergence within the record's identity, if any. */
  divergence: DivergenceOut | null;
  /** Other candidates of the identity holding different content. */
  competingCandidates: CompetingCandidateOut[];
  /** Whether the viewed record is a normal decision or an erratum;
   *  picks the right chip vocabulary for each competing candidate. */
  recordKind: RecordKind;
}>();
</script>

<template>
  <v-alert
    v-if="divergence"
    type="warning"
    variant="tonal"
    :icon="divergenceLabel(divergence.kind).icon"
    class="mb-4"
  >
    <div>{{ divergence.message }}</div>
    <ul v-if="divergence.other_record_ids.length > 0" class="mt-2">
      <li v-for="id in divergence.other_record_ids" :key="id">
        <router-link :to="`/records/${id}`" class="text-primary">
          View the {{ shortDigest(divergence.other_digest) }} revision
        </router-link>
      </li>
    </ul>
  </v-alert>

  <v-card v-if="competingCandidates.length > 0" class="mb-4">
    <v-card-title tag="h2" class="text-title-large">
      <v-icon icon="mdi-source-branch" size="small" aria-hidden="true" class="mr-1" />
      Competing candidates
    </v-card-title>
    <v-card-text class="text-body-medium text-medium-emphasis">
      Other candidates of this same record hold different content. A
      decision on one never affects another.
    </v-card-text>
    <v-list density="compact" tabindex="-1">
      <v-list-item v-for="candidate in competingCandidates" :key="candidate.id">
        <router-link :to="`/records/${candidate.id}`" class="text-primary">
          {{ candidate.ref }}
        </router-link>
        <template #append>
          <code class="mr-2" :title="candidate.digest">
            {{ shortDigest(candidate.digest) }}
          </code>
          <StatusChip
            v-bind="
              approvalDisplayLabel(
                {
                  state: candidate.approval_state,
                  approvable: candidate.approvable,
                },
                'candidate',
                recordKind,
                candidate.ref,
              )
            "
          />
        </template>
      </v-list-item>
    </v-list>
  </v-card>
</template>
