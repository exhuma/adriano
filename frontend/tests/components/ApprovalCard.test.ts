/**
 * Ensure `ApprovalCard` switches to the RFC "report → verify/reject"
 * wording when the viewed record is an erratum (buttons, dialog
 * title via `DecisionDialog`, and the state explanation), while a
 * normal decision keeps the plain Accept/Reject wording; that focus
 * returns to the button that opened the decision dialog; and that the
 * card's titles are headings (docs/ui-review G-05).
 */
import { flushPromises, mount } from "@vue/test-utils";
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
  it("shows plain Accept/Reject buttons and the plain state chip for a decision", () => {
    const wrapper = mountCard("decision");

    const buttons = wrapper.findAll("button").map((b) => b.text());
    expect(buttons).toContain("Accept");
    expect(buttons).toContain("Reject");
    expect(wrapper.text()).toContain("Awaiting review.");
    expect(wrapper.text()).toContain("Pending approval");
  });

  it("shows 'Verify erratum' / 'Reject erratum' buttons and the erratum status chip for an erratum", () => {
    const wrapper = mountCard("erratum");

    const buttons = wrapper.findAll("button").map((b) => b.text());
    expect(buttons).toContain("Verify erratum");
    expect(buttons).toContain("Reject erratum");
    expect(wrapper.text()).toContain(
      "This erratum is reported and awaits verification.",
    );
    // The erratum vocabulary chip ("Reported"), not the decision
    // wording ("Pending approval"), for the erratum's own status.
    expect(wrapper.text()).toContain("Reported");
    expect(wrapper.text()).not.toContain("Pending approval");
  });
});

describe("ApprovalCard dialog focus", () => {
  it("returns focus to Accept after the dialog is cancelled", async () => {
    const wrapper = mount(ApprovalCard, {
      props: {
        approval: baseApproval(),
        kind: "published",
        recordKind: "decision",
        recordId: "11111111-1111-1111-1111-111111111111",
      },
      global: { plugins: [vuetify] },
      attachTo: document.body,
    });

    const accept = wrapper
      .findAll("button")
      .find((b) => b.text() === "Accept")!;
    await accept.trigger("click");
    await flushPromises();
    const cancel = Array.from(document.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Cancel",
    );
    expect(cancel).toBeDefined();
    (document.activeElement as HTMLElement | null)?.blur();

    cancel!.click();
    await flushPromises();

    expect(document.activeElement).toBe(accept.element);
    wrapper.unmount();
  });

  it("uses an h2 card title and an h3 for the decision history", () => {
    const wrapper = mountCard("decision");

    expect(wrapper.find("h2").text()).toBe("Approval");
    expect(wrapper.find("h3").text()).toBe("Decision history");
  });
});
