/**
 * Ensure the sidebar composes every metadata card (approval summary,
 * metadata, provenance, links, siblings, legacy sign-off) and never
 * the document body itself, which stays in the main column
 * (rfc-editor.org/info layout: metadata to the side, the document in
 * the middle); that its first card carries the sidebar heading, the
 * status and -- only when the caller can decide -- Accept/Reject
 * (docs/ui-review R-01); that card titles are real headings under
 * the sidebar `h2` (G-05); and that static lists are not tab stops
 * (G-10).
 */
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordSidebar from "@/components/record/RecordSidebar.vue";
import type { ApprovalOut } from "@/types/approval";

type SidebarProps = InstanceType<typeof RecordSidebar>["$props"];

function approval(overrides: Partial<ApprovalOut> = {}): ApprovalOut {
  return {
    state: "accepted",
    needs_approval: false,
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
    can_decide: false,
    decide_blocked_code: "anonymous",
    decide_blocked_reason: "sign in as a reviewer to decide",
    divergence: null,
    competing_candidates: [],
    ...overrides,
  };
}

function baseProps(): SidebarProps {
  return {
    recordKind: "decision",
    kind: "published",
    recordId: "11111111-1111-1111-1111-111111111111",
    recordTitle: "Adopt gRPC for internal APIs",
    approval: approval(),
    adrUuid: "22222222-2222-2222-2222-222222222222",
    decisionDate: "2024-12-24",
    decisionDateInferred: false,
    provenance: {
      source_id: "central",
      project: "platform",
      path: "doc/decisions/2024-12-24-use-postgres.md",
      ref: "main",
      source_url: "https://git.example.com/platform",
      updated_at: "2026-02-03T10:00:00Z",
    },
    freshness: {
      last_attempt_at: null,
      last_success_at: "2026-01-01T00:00:00Z",
      last_status: "ok",
      stale: false,
      intake: ["poll"],
    },
    outboundLinks: [],
    inboundLinks: [
      {
        link_type: "updated_by",
        source_id: "ddd",
        source_title: "Use PostgreSQL v2",
      },
    ],
    siblings: [
      {
        id: "eee",
        kind: "candidate",
        source_id: "central",
        project: "platform",
        path: "doc/decisions/2024-12-24-use-postgres.md",
        ref: "feature/x",
        digest: "sha256-v1:abc",
        title: "Use PostgreSQL",
        decision_date: "2024-12-24",
        decision_date_inferred: false,
        approval_state: "pending",
      },
    ],
    legacySignoffEntries: ["Jane Doe <jane@example.com>"],
  };
}

async function mountSidebar(overrides: Partial<SidebarProps> = {}) {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  await router.push("/");

  return mount(RecordSidebar, {
    props: { ...baseProps(), ...overrides },
    global: { plugins: [router, vuetify] },
    attachTo: document.body,
  });
}

function buttonTexts(wrapper: Awaited<ReturnType<typeof mountSidebar>>) {
  return wrapper.findAll("button").map((b) => b.text());
}

describe("RecordSidebar", () => {
  it("titles itself for a decision and composes every metadata card", async () => {
    const wrapper = await mountSidebar();

    expect(wrapper.find("h2").text()).toBe("About this decision");
    expect(wrapper.text()).toContain("Metadata");
    expect(wrapper.text()).toContain("Provenance");
    expect(wrapper.text()).toContain("Referenced by");
    expect(wrapper.text()).toContain("Other revisions");
    expect(wrapper.text()).toContain("Legacy sign-off (unverified)");
    expect(wrapper.text()).toContain("Jane Doe <jane@example.com>");
    wrapper.unmount();
  });

  it("titles itself for an erratum", async () => {
    const wrapper = await mountSidebar({
      recordKind: "erratum",
      approval: approval({ state: "pending" }),
    });

    expect(wrapper.find("h2").text()).toBe("About this erratum");
    wrapper.unmount();
  });

  it("puts the heading in its first card, labelling the aside", async () => {
    const wrapper = await mountSidebar();

    const aside = wrapper.find("aside");
    const firstCard = aside.find(".v-card");
    const heading = firstCard.find("h2");
    expect(heading.exists()).toBe(true);
    expect(aside.attributes("aria-labelledby")).toBe(heading.attributes("id"));
    wrapper.unmount();
  });

  it("renders every info card title as an h3 under the h2", async () => {
    const wrapper = await mountSidebar();

    const h3s = wrapper.findAll("h3").map((h) => h.text());
    expect(h3s).toEqual([
      "Metadata",
      "Provenance",
      "Referenced by",
      "Other revisions",
      "Legacy sign-off (unverified)",
    ]);
    for (const h3 of wrapper.findAll("h3")) {
      expect(h3.classes()).toContain("text-title-medium");
    }
    expect(wrapper.findAll("h2")).toHaveLength(1);
    wrapper.unmount();
  });

  it("includes an approval summary chip linking to the approval card", async () => {
    const wrapper = await mountSidebar();

    expect(wrapper.text()).toContain("Accepted");
    const link = wrapper.find("a[href='#approval']");
    expect(link.exists()).toBe(true);
    expect(link.text()).toBe("Approval details");
    wrapper.unmount();
  });

  it("uses the erratum vocabulary for the approval summary chip on an erratum", async () => {
    const wrapper = await mountSidebar({
      recordKind: "erratum",
      approval: approval({ state: "not_required" }),
    });

    expect(wrapper.text()).toContain("Published (no review required)");
    expect(wrapper.text()).not.toContain("Approval not required");
    wrapper.unmount();
  });

  it("shows Accept/Reject in the first card when can_decide", async () => {
    const wrapper = await mountSidebar({
      approval: approval({
        state: "pending",
        can_decide: true,
        decide_blocked_code: null,
        decide_blocked_reason: null,
      }),
    });

    const firstCard = wrapper.find("aside .v-card");
    const texts = firstCard.findAll("button").map((b) => b.text());
    expect(texts).toEqual(["Accept", "Reject"]);
    wrapper.unmount();
  });

  it("shows no Accept/Reject when the caller cannot decide", async () => {
    const wrapper = await mountSidebar({
      approval: approval({ state: "pending" }),
    });

    expect(buttonTexts(wrapper)).not.toContain("Accept");
    expect(buttonTexts(wrapper)).not.toContain("Reject");
    wrapper.unmount();
  });

  it("returns focus to the sidebar trigger after closing", async () => {
    const wrapper = await mountSidebar({
      approval: approval({
        state: "pending",
        can_decide: true,
        decide_blocked_code: null,
        decide_blocked_reason: null,
      }),
    });

    const reject = wrapper
      .findAll("aside .v-card button")
      .find((b) => b.text() === "Reject")!;
    (reject.element as HTMLElement).focus();
    await reject.trigger("click");
    await flushPromises();
    const cancel = Array.from(document.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Cancel",
    );
    expect(cancel).toBeDefined();
    (document.activeElement as HTMLElement | null)?.blur();

    cancel!.click();
    await flushPromises();

    expect(document.activeElement).toBe(reject.element);
    wrapper.unmount();
  });

  it("never makes the static info lists tab stops", async () => {
    const wrapper = await mountSidebar();

    const lists = wrapper.findAll(".v-list");
    expect(lists.length).toBeGreaterThan(0);
    for (const list of lists) {
      expect(list.attributes("tabindex")).toBe("-1");
    }
    wrapper.unmount();
  });

  it("never renders the document body", async () => {
    const wrapper = await mountSidebar();

    expect(wrapper.text()).not.toContain("Decision record");
    expect(wrapper.html()).not.toContain("v-html");
    wrapper.unmount();
  });
});
