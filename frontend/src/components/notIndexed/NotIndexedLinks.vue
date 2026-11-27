<script setup lang="ts">
/**
 * The two places an entry can be followed to: the file in its
 * repository (`source_url`, shown only when the registration knows
 * it) and, for a duplicate UUID, the ADR that holds the UUID
 * (`/records/{holder_uuid}`).
 */
import { recordPath } from "@/utils/recordPaths";

defineProps<{
  /** URL of the file in its repository, if known. */
  sourceUrl: string | null;
  /** The ADR holding the UUID, for a duplicate; otherwise `null`. */
  holderUuid: string | null;
}>();
</script>

<template>
  <div class="d-flex flex-wrap align-center ga-2">
    <v-btn
      v-if="sourceUrl"
      :href="sourceUrl"
      target="_blank"
      rel="noopener noreferrer"
      variant="text"
      size="small"
      color="primary"
      prepend-icon="mdi-open-in-new"
    >
      Open file in repository
    </v-btn>
    <v-btn
      v-if="holderUuid"
      :to="recordPath(holderUuid)"
      variant="text"
      size="small"
      color="primary"
      prepend-icon="mdi-file-document-outline"
    >
      View the ADR that holds this UUID
    </v-btn>
  </div>
</template>
