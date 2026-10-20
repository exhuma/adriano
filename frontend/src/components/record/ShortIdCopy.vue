<script setup lang="ts">
/**
 * Shows a technical identifier (a UUID) in its shortened running-text
 * form, with the full value reachable via a hover/focus tooltip and a
 * click-to-copy button (module-ux-principles "Technical identifiers":
 * never show only the shortened form). Shared by `RecordMetadataCard`
 * (the record's own UUID), `RecordStatusBanners`, and `ErratumBody`
 * (an erratum's unresolved target UUID), so the pattern has exactly
 * one implementation; the copy button itself is `CopyValueButton`.
 */
import CopyValueButton from "@/components/CopyValueButton.vue";
import { shortUuid } from "@/utils/digest";

defineProps<{
  /** Full identifier value to shorten, show in a tooltip, and copy. */
  value: string;
  /** What the identifier identifies, used in the copy button's
   *  accessible name, e.g. "UUID" or "target UUID". */
  label: string;
}>();
</script>

<template>
  <span class="d-inline-flex align-center ga-1">
    <code :title="value">{{ shortUuid(value) }}</code>
    <CopyValueButton :value="value" :label="`full ${label}`" />
  </span>
</template>
