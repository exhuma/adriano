/**
 * Ensure the sidebar composes every metadata card (approval summary,
 * metadata, provenance, links, siblings, legacy sign-off) and never
 * the document body itself, which stays in the main column
 * (rfc-editor.org/info layout: metadata to the side, the document in
 * the middle).
 */
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordSidebar from "@/components/record/RecordSidebar.vue";

async function mountSidebar() {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  await router.push("/");

  return mount(RecordSidebar, {
    props: {
      recordKind: "decision",
      kind: "published",
      approvalState: "accepted",
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
        { link_type: "updated_by", source_id: "ddd", source_title: "Use PostgreSQL v2" },
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
    },
    global: { plugins: [router, vuetify] },
  });
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
  });

  it("titles itself for an erratum", async () => {
    const router: Router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/", component: { template: "<div />" } }],
    });
    await router.push("/");
    const wrapper = mount(RecordSidebar, {
      props: {
        recordKind: "erratum",
        kind: "published",
        approvalState: "pending",
        adrUuid: null,
        decisionDate: null,
        decisionDateInferred: false,
        provenance: {
          source_id: "central",
          project: "platform",
          path: "x",
          ref: "main",
          source_url: null,
          updated_at: "2026-02-03T10:00:00Z",
        },
        freshness: {
          last_attempt_at: null,
          last_success_at: null,
          last_status: "never",
          stale: false,
          intake: ["poll"],
        },
        outboundLinks: [],
        inboundLinks: [],
        siblings: [],
        legacySignoffEntries: [],
      },
      global: { plugins: [router, vuetify] },
    });

    expect(wrapper.find("h2").text()).toBe("About this erratum");
  });

  it("includes an approval summary chip linking to the approval card", async () => {
    const wrapper = await mountSidebar();

    expect(wrapper.text()).toContain("Accepted");
    const link = wrapper.find("a[href='#approval']");
    expect(link.exists()).toBe(true);
    expect(link.text()).toBe("View approval");
  });

  it("never renders the document body", async () => {
    const wrapper = await mountSidebar();

    expect(wrapper.text()).not.toContain("Decision record");
    expect(wrapper.html()).not.toContain("v-html");
  });
});
