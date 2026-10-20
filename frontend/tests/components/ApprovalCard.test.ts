/**
 * Ensure `ApprovalCard` switches to the RFC "report → verify/reject"
 * wording when the viewed record is an erratum (buttons, dialog
 * title via `DecisionDialog`, and the state explanation), while a
 * normal decision keeps the plain Accept/Reject wording.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import ApprovalCard from "@/components/ApprovalCard.vue";
import type { ApprovalOut } from "@/types/approval";

function baseApproval(): ApprovalOut {
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
  };
}

function mountCard(recordKind: "decision" | "erratum") {
  return mount(ApprovalCard, {
    props: {
      approval: baseApproval(),
      kind: "published",
      recordKind,
      recordId: "11111111-1111-1111-1111-111111111111",
    },
    global: { plugins: [vuetify] },
  });
}

describe("ApprovalCard", () => {
  it("shows plain Accept/Reject buttons for a decision", () => {
    const wrapper = mountCard("decision");

    const buttons = wrapper.findAll("button").map((b) => b.text());
    expect(buttons).toContain("Accept");
    expect(buttons).toContain("Reject");
    expect(wrapper.text()).toContain("Awaiting review.");
  });

  it("shows 'Verify erratum' / 'Reject erratum' buttons for an erratum", () => {
    const wrapper = mountCard("erratum");

    const buttons = wrapper.findAll("button").map((b) => b.text());
    expect(buttons).toContain("Verify erratum");
    expect(buttons).toContain("Reject erratum");
    expect(wrapper.text()).toContain(
      "This erratum is reported and awaits verification.",
    );
  });
});
