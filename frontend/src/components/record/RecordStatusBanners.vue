<script setup lang="ts">
/**
 * Record detail page's prominent status notices, shown right below
 * the header and before the two-column body (rfc-editor.org/info's
 * "This RFC is now obsolete, see RFC 9110" / "was updated, see RFC
 * 8615" layout, the product owner's reference design): a single
 * lifecycle notice (obsoleted takes priority over updated, matching
 * the backend's own precedence in
 * `domain/relationships.py::_status`), and -- when the record being
 * viewed is itself an erratum -- which decision it corrects. The two
 * are independently optional, mirroring `DivergenceBanner`'s
 * combination of independent warnings. Obsolescence is a lifecycle
 * state, not a fault, so the lifecycle notice uses the `warning`
 * colour rather than `error` (R-04). The old "has N errata" notice
 * moved to a link in `RecordHeader`'s metadata line (R-04: say each
 * fact once -- the dedicated `ErrataSection` already covers the
 * detail), and the erratum-for notice no longer repeats its own
 * approval-state chip, which the sidebar and the Approval card
 * already show (R-11). Purely presentational: the parent computes
 * every prop from the loaded record detail.
 * both notices' `router-link`s had no colour
 * class, so each rendered in the browser's own link colour instead
 * of the theme (4.14:1 in dark). `text-primary` fixes both; it stays
 * >=4.5:1 against the warning/info tonal tint these alerts paint
 * behind it (`tests/plugins/vuetify.test.ts`).
 */
import { computed } from "vue";

import ShortIdCopy from "@/components/record/ShortIdCopy.vue";
import type { DisplayStatus, ErratumForOut, InboundLinkOut } from "@/types/records";

const props = defineProps<{
  /** The record's derived lifecycle status, from inbound links;
   *  picks which lifecycle notice, if any, to show. */
  status: DisplayStatus;
  /** Inbound `obsoleted_by` links, used when `status` is
   *  `"obsoleted"`. */
  obsoletedBy: InboundLinkOut[];
  /** Inbound `updated_by` links, used when `status` is `"updated"`. */
  updatedBy: InboundLinkOut[];
  /** The decision this record corrects, when it is itself an
   *  erratum; `null` for an ordinary decision. */
  erratumFor: ErratumForOut | null;
}>();

/** The one lifecycle notice to show (obsoleted takes priority over
 *  updated), or `null` for an active record or when the matching
 *  link list is unexpectedly empty. */
const lifecycleNotice = computed(() => {
  if (props.status === "obsoleted" && props.obsoletedBy.length > 0) {
    return {
      icon: "mdi-archive-arrow-down-outline",
      verb: "is obsolete",
      links: props.obsoletedBy,
    };
  }
  if (props.status === "updated" && props.updatedBy.length > 0) {
    return {
      icon: "mdi-arrow-up-bold-circle-outline",
      verb: "was updated",
      links: props.updatedBy,
    };
  }
  return null;
});
</script>

<template>
  <v-alert
    v-if="lifecycleNotice"
    type="warning"
    variant="tonal"
    :icon="lifecycleNotice.icon"
    class="mb-3"
  >
    This decision {{ lifecycleNotice.verb }}, see
    <template v-for="(link, index) in lifecycleNotice.links" :key="link.source_id">
      <router-link :to="`/records/${link.source_id}`" class="text-primary">
        {{ link.source_title }}
      </router-link><span v-if="index < lifecycleNotice.links.length - 1">, </span>
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
      <router-link :to="`/records/${erratumFor.id}`" class="text-primary">
        {{ erratumFor.title }}
      </router-link>.
    </template>
    <template v-else>
      This is an erratum for an unknown decision
      <ShortIdCopy :value="erratumFor.uuid" label="target UUID" />.
    </template>
  </v-alert>
</template>
