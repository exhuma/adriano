/**
 * Ensure the sidebar's approval summary card shows the neutral
 * "Blocked" status instead of "Pending approval" when the record's
 * content cannot be decided (docs/ui-review R-02), for both a
 * decision and an erratum, and that Accept/Reject only render when
 * `can_decide` is true.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordApprovalSummaryCard from
  "@/components/record/RecordApprovalSummaryCard.vue";
import type { ApprovalOut } from "@/types/approval";

function baseApproval(overrides: Partial<ApprovalOut> = {}): ApprovalOut {
  return {
    state: "pending",
    needs_approval: true,
    digest: "sha256-v1:abc",
    policy: {
      status: "configured",
      id: "global",
      version: 1,
      required: true,
      allow_self_approval: false,
    },
    history: [],
    approvable: true,
    approval_blocker: null,
    last_accepted_digest: null,
    can_decide: true,
    decide_blocked_code: null,
    decide_blocked_reason: null,
    divergence: null,
    competing_candidates: [],
    ...overrides,
  };
}

function mountCard(overrides: Partial<Record<string, unknown>> = {}) {
  return mount(RecordApprovalSummaryCard, {
    props: {
      approval: baseApproval(),
      kind: "published",
      recordKind: "decision",
      recordId: "11111111-1111-1111-1111-111111111111",
      recordTitle: "Adopt gRPC for internal APIs",
      recordRef: "main",
      headingId: "about-heading",
      ...overrides,
    },
    global: { plugins: [vuetify] },
  });
}

describe("RecordApprovalSummaryCard", () => {
  it("shows the ordinary 'Pending approval' status when approvable", () => {
    const wrapper = mountCard();

    expect(wrapper.text()).toContain("Pending approval");
    expect(wrapper.text()).not.toContain("Blocked");
  });

  it("shows the neutral 'Blocked' status when the content is not " +
    "approvable", () => {
    const wrapper = mountCard({
      approval: baseApproval({ approvable: false, can_decide: false }),
    });

    expect(wrapper.text()).toContain("Blocked");
    expect(wrapper.text()).not.toContain("Pending approval");
  });

  it("shows 'Blocked' for an unapprovable erratum too", () => {
    const wrapper = mountCard({
      recordKind: "erratum",
      approval: baseApproval({ approvable: false, can_decide: false }),
    });

    expect(wrapper.text()).toContain("Blocked");
    expect(wrapper.text()).not.toContain("Reported");
  });

  it("hides Accept/Reject when can_decide is false", () => {
    const wrapper = mountCard({
      approval: baseApproval({ approvable: false, can_decide: false }),
    });

    expect(wrapper.findAll("button")).toHaveLength(0);
  });

  it("shows Accept/Reject when can_decide is true", () => {
    const wrapper = mountCard();

    const buttons = wrapper.findAll("button").map((b) => b.text());
    expect(buttons).toContain("Accept");
    expect(buttons).toContain("Reject");
  });
});
