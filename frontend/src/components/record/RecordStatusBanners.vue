<script setup lang="ts">
/**
 * Record detail page's prominent status notices, shown right below
 * the header and before the two-column body (rfc-editor.org/info's
 * "This RFC is now obsolete, see RFC 9110" / "was updated, see RFC
 * 8615" layout, the product owner's reference design): the decision
 * is obsolete or was updated (from inbound links), it has errata, or
 * -- when the record being viewed is itself an erratum -- which
 * decision it corrects. Each is independently optional, mirroring
 * `DivergenceBanner`'s combination of independent warnings. Purely
 * presentational: the parent computes every prop from the loaded
 * record detail.
 */
import { computed } from "vue";

import type { ErrataSummaryOut, ErratumForOut, InboundLinkOut } from "@/types/records";
import { shortUuid } from "@/utils/digest";

const props = defineProps<{
  /** Inbound `obsoleted_by` links, or an empty array when this
   *  decision has not been obsoleted. */
  obsoletedBy: InboundLinkOut[];
  /** Inbound `updated_by` links, or an empty array when this
   *  decision has not been updated. */
  updatedBy: InboundLinkOut[];
  /** Errata counts for this decision, for the "has N errata" notice;
   *  hidden when there are none, published or proposed. */
  errataSummary: ErrataSummaryOut;
  /** The decision this record corrects, when it is itself an
   *  erratum; `null` for an ordinary decision. */
  erratumFor: ErratumForOut | null;
}>();

/** Whether to show the "has N errata" notice: at least one published
 *  or proposed (candidate) erratum exists. */
const hasErrataNotice = computed(
  () => props.errataSummary.total + props.errataSummary.proposed > 0,
);

/** Singular/plural noun for an erratum count. */
function pluralizeErrata(count: number): string {
  return count === 1 ? "erratum" : "errata";
}

/** The errata notice's sentence, built from the counts: a dedicated
 *  "N proposed errata (not yet published)" sentence when nothing is
 *  published yet, otherwise the total plus only the nonzero
 *  verified/reported/changed/rejected parts, and a trailing
 *  "N proposed" sentence only when there are proposed (candidate)
 *  errata on top of the published ones. */
const errataNoticeText = computed(() => {
  const s = props.errataSummary;
  if (s.total === 0) {
    return (
      `This decision has ${s.proposed} proposed ` +
      `${pluralizeErrata(s.proposed)} (not yet published).`
    );
  }
  const parts: string[] = [];
  if (s.verified > 0) {
    parts.push(`${s.verified} verified`);
  }
  if (s.reported > 0) {
    parts.push(`${s.reported} reported`);
  }
  if (s.changed > 0) {
    parts.push(`${s.changed} changed`);
  }
  if (s.rejected > 0) {
    parts.push(`${s.rejected} rejected`);
  }
  let text =
    `This decision has ${s.total} ${pluralizeErrata(s.total)} ` +
    `(${parts.join(", ")}).`;
  if (s.proposed > 0) {
    text += ` ${s.proposed} proposed.`;
  }
  return text;
});

/** Short form of the erratum's target UUID, shown when the target
 *  cannot be resolved to a known record. */
const erratumForShortUuid = computed(() =>
  props.erratumFor ? shortUuid(props.erratumFor.uuid) : "",
);
</script>

<template>
  <v-alert
    v-if="obsoletedBy.length > 0"
    type="error"
    variant="tonal"
    icon="mdi-archive-arrow-down-outline"
    class="mb-3"
  >
    This decision is obsolete, see
    <template v-for="(link, index) in obsoletedBy" :key="link.source_id">
      <router-link :to="`/records/${link.source_id}`">{{ link.source_title }}</router-link><span v-if="index < obsoletedBy.length - 1">, </span>
    </template>.
  </v-alert>

  <v-alert
    v-if="updatedBy.length > 0"
    type="warning"
    variant="tonal"
    icon="mdi-arrow-up-bold-circle-outline"
    class="mb-3"
  >
    This decision was updated, see
    <template v-for="(link, index) in updatedBy" :key="link.source_id">
      <router-link :to="`/records/${link.source_id}`">{{ link.source_title }}</router-link><span v-if="index < updatedBy.length - 1">, </span>
    </template>.
  </v-alert>

  <v-alert
    v-if="erratumFor"
    type="info"
    variant="tonal"
    icon="mdi-file-alert-outline"
    class="mb-3"
  >
    <template v-if="erratumFor.resolved && erratumFor.id">
      This is an erratum for
      <router-link :to="`/records/${erratumFor.id}`">{{ erratumFor.title }}</router-link>.
    </template>
    <template v-else>
      This is an erratum for an unknown decision
      <code>{{ erratumForShortUuid }}</code>.
    </template>
  </v-alert>

  <v-alert
    v-if="hasErrataNotice"
    type="info"
    variant="tonal"
    icon="mdi-note-alert-outline"
    class="mb-3"
  >
    {{ errataNoticeText }}
    <a href="#errata">View errata</a>
  </v-alert>
</template>
