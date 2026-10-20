/**
 * Ensure `DecisionHistoryTable` switches an accepted event's label to
 * "Verified" (RFC report/verify/reject vocabulary) when `recordKind`
 * is "erratum", while a plain decision (or the default when
 * `recordKind` is omitted) keeps the "Accepted" wording. Rejected
 * events always read "Rejected", regardless of record kind.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import DecisionHistoryTable from "@/components/DecisionHistoryTable.vue";
import type { DecisionSummaryOut } from "@/types/approval";

function decisionEvent(
  action: DecisionSummaryOut["action"],
): DecisionSummaryOut {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    digest: "sha256-v1:abc",
    current_digest: true,
    action,
    actor_issuer: "https://idp.example",
    actor_subject: "user-1",
    actor_display: "Jane Reviewer",
    comment: null,
    policy_id: "global",
    policy_version: 1,
    provenance: {
      record_id: "11111111-1111-1111-1111-111111111111",
      kind: "published",
      source_id: null,
      project: null,
      ref: null,
      path: null,
      source_url: null,
    },
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("DecisionHistoryTable", () => {
  it("labels an accepted event 'Verified' for an erratum", () => {
    const wrapper = mount(DecisionHistoryTable, {
      props: {
        history: [decisionEvent("accepted")],
        recordKind: "erratum",
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Verified");
    expect(wrapper.text()).not.toContain("Accepted");
  });

  it("labels an accepted event 'Accepted' for a plain decision", () => {
    const wrapper = mount(DecisionHistoryTable, {
      props: {
        history: [decisionEvent("accepted")],
        recordKind: "decision",
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Accepted");
    expect(wrapper.text()).not.toContain("Verified");
  });

  it("defaults to the plain 'Accepted' wording when recordKind is omitted", () => {
    const wrapper = mount(DecisionHistoryTable, {
      props: {
        history: [decisionEvent("accepted")],
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Accepted");
    expect(wrapper.text()).not.toContain("Verified");
  });

  it("labels a rejected event 'Rejected' regardless of record kind", () => {
    const wrapper = mount(DecisionHistoryTable, {
      props: {
        history: [decisionEvent("rejected")],
        recordKind: "erratum",
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Rejected");
    expect(wrapper.text()).not.toContain("Verified");
  });
});
