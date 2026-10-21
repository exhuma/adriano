/**
 * Ensure `ApprovalCard` switches to the RFC "report → verify/reject"
 * wording when the viewed record is an erratum (buttons, dialog
 * title via `DecisionDialog`, and the state explanation), while a
 * normal decision keeps the plain Accept/Reject wording; that focus
 * returns to the button that opened the decision dialog; that the
 * card's titles are headings; that content
 * which cannot be decided shows the neutral "Blocked" status instead
 * of "Pending approval" (R-02); and that the "why you can't decide"
 * line uses plain-language copy for the blocker code, muted for a
 * reader, instead of the raw `decide_blocked_reason` text (R-10).
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

const RECORD_TITLE = "Adopt gRPC for internal APIs";

function mountCard(recordKind: "decision" | "erratum") {
  return mount(ApprovalCard, {
    props: {
      approval: baseApproval(),
      kind: "published",
      recordKind,
      recordId: "11111111-1111-1111-1111-111111111111",
      recordTitle: RECORD_TITLE,
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
  it("names the record in the decision dialog (D-02)", async () => {
    const wrapper = mountCard("decision");

    const accept = wrapper
      .findAll("button")
      .find((b) => b.text() === "Accept")!;
    await accept.trigger("click");
    await flushPromises();

    expect(document.body.textContent).toContain(RECORD_TITLE);
    wrapper.unmount();
  });

  it("returns focus to Accept after the dialog is cancelled", async () => {
    const wrapper = mount(ApprovalCard, {
      props: {
        approval: baseApproval(),
        kind: "published",
        recordKind: "decision",
        recordId: "11111111-1111-1111-1111-111111111111",
        recordTitle: RECORD_TITLE,
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

describe("ApprovalCard blocked content (R-02, R-10, P11-R-07)", () => {
  it("shows the neutral 'Blocked' status instead of 'Pending approval'," +
    " the explanation once, and a raw-text fallback only when no" +
    " issues card already explains it", () => {
    const wrapper = mount(ApprovalCard, {
      props: {
        approval: {
          ...baseApproval(),
          approvable: false,
          can_decide: false,
          decide_blocked_code: "not_approvable",
          decide_blocked_reason:
            "this content cannot be decided: the record has no valid `uuid`",
        },
        kind: "published",
        recordKind: "decision",
        recordId: "11111111-1111-1111-1111-111111111111",
        recordTitle: RECORD_TITLE,
        hasValidationIssues: false,
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Blocked");
    expect(wrapper.text()).not.toContain("Pending approval");
    const occurrences = wrapper.text().split(
      "This content can't be decided until its problems are fixed.",
    ).length - 1;
    expect(occurrences).toBe(1);
    expect(wrapper.text()).toContain(
      "Details: this content cannot be decided: the record has no " +
        "valid `uuid`",
    );
  });

  it("drops the raw 'Details' line when the issues card already" +
    " explains the problem", () => {
    const wrapper = mount(ApprovalCard, {
      props: {
        approval: {
          ...baseApproval(),
          approvable: false,
          can_decide: false,
          decide_blocked_code: "not_approvable",
          decide_blocked_reason:
            "this content cannot be decided: the record has no valid `uuid`",
        },
        kind: "published",
        recordKind: "decision",
        recordId: "11111111-1111-1111-1111-111111111111",
        recordTitle: RECORD_TITLE,
        hasValidationIssues: true,
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Blocked");
    expect(wrapper.text()).toContain(
      "This content can't be decided until its problems are fixed.",
    );
    expect(wrapper.text()).not.toContain("Details:");
    expect(wrapper.text()).not.toContain("`uuid`");
  });

  it("shows a short, muted line for a reader blocked by not_eligible", () => {
    const wrapper = mount(ApprovalCard, {
      props: {
        approval: {
          ...baseApproval(),
          can_decide: false,
          decide_blocked_code: "not_eligible",
          decide_blocked_reason:
            "not a reviewer: the approval policy lists neither this " +
            "user nor any of their roles",
        },
        kind: "published",
        recordKind: "decision",
        recordId: "11111111-1111-1111-1111-111111111111",
        recordTitle: RECORD_TITLE,
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Only reviewers can approve this.");
    expect(wrapper.text()).not.toContain("not a reviewer:");
    expect(wrapper.find(".text-medium-emphasis").exists()).toBe(true);
  });

  it("uses a plain-language reason for every other blocker code too", () => {
    const wrapper = mount(ApprovalCard, {
      props: {
        approval: {
          ...baseApproval(),
          can_decide: false,
          decide_blocked_code: "policy_missing",
          decide_blocked_reason:
            "the approval policy is not configured or invalid; " +
            "decisions are refused",
        },
        kind: "published",
        recordKind: "decision",
        recordId: "11111111-1111-1111-1111-111111111111",
        recordTitle: RECORD_TITLE,
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain(
      "No approval policy is configured, so nothing can be decided yet.",
    );
    expect(wrapper.text()).not.toContain("decisions are refused");
  });
});
