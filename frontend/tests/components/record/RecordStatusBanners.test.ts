/**
 * Ensure the record page's prominent status banners render for each
 * independently optional case (rfc-editor.org/info reference design:
 * "This RFC is now obsolete, see RFC 9110" / "was updated, see RFC
 * 8615"): obsoleted, updated, has-errata (with counts), and -- on an
 * erratum page -- which decision it corrects (resolved or not) plus
 * the viewed erratum's own status.
 */
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordStatusBanners from "@/components/record/RecordStatusBanners.vue";
import type {
  ApprovalStateCode,
  ErrataSummaryOut,
  ErratumForOut,
  InboundLinkOut,
  RecordState,
} from "@/types/records";

function emptySummary(): ErrataSummaryOut {
  return { total: 0, verified: 0, reported: 0, rejected: 0, changed: 0, proposed: 0 };
}

async function mountBanners(props: {
  obsoletedBy?: InboundLinkOut[];
  updatedBy?: InboundLinkOut[];
  errataSummary?: ErrataSummaryOut;
  erratumFor?: ErratumForOut | null;
  erratumApprovalState?: ApprovalStateCode;
  erratumKind?: RecordState;
  erratumRef?: string;
}) {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  const wrapper = mount(RecordStatusBanners, {
    props: {
      obsoletedBy: props.obsoletedBy ?? [],
      updatedBy: props.updatedBy ?? [],
      errataSummary: props.errataSummary ?? emptySummary(),
      erratumFor: props.erratumFor ?? null,
      erratumApprovalState: props.erratumApprovalState ?? "pending",
      erratumKind: props.erratumKind ?? "published",
      erratumRef: props.erratumRef,
    },
    global: { plugins: [router, vuetify] },
  });
  return wrapper;
}

describe("RecordStatusBanners", () => {
  it("renders nothing when the record is plain, with no errata", async () => {
    const wrapper = await mountBanners({});

    expect(wrapper.text().trim()).toBe("");
  });

  it("shows the obsoleted banner with a link to each superseding decision", async () => {
    const wrapper = await mountBanners({
      obsoletedBy: [
        { link_type: "obsoleted_by", source_id: "aaa", source_title: "Use gRPC" },
      ],
    });

    expect(wrapper.text()).toContain("This decision is obsolete, see");
    const link = wrapper.find("a[href='/records/aaa']");
    expect(link.text()).toBe("Use gRPC");
  });

  it("shows the updated banner distinctly from the obsoleted banner", async () => {
    const wrapper = await mountBanners({
      updatedBy: [
        { link_type: "updated_by", source_id: "bbb", source_title: "Use PostgreSQL v2" },
      ],
    });

    expect(wrapper.text()).toContain("This decision was updated, see");
    expect(wrapper.text()).not.toContain("This decision is obsolete");
    expect(wrapper.find("a[href='/records/bbb']").text()).toBe("Use PostgreSQL v2");
  });

  it("shows the has-errata notice with the verified/reported counts", async () => {
    const wrapper = await mountBanners({
      errataSummary: {
        total: 3,
        verified: 2,
        reported: 1,
        rejected: 0,
        changed: 0,
        proposed: 0,
      },
    });

    expect(wrapper.text()).toContain(
      "This decision has 3 errata (2 verified or not requiring review, 1 reported).",
    );
    expect(wrapper.find("a[href='#errata']").exists()).toBe(true);
  });

  it("uses the singular 'erratum' for a single published erratum", async () => {
    const wrapper = await mountBanners({
      errataSummary: {
        total: 1,
        verified: 0,
        reported: 1,
        rejected: 0,
        changed: 0,
        proposed: 0,
      },
    });

    expect(wrapper.text()).toContain("This decision has 1 erratum (1 reported).");
  });

  it("spells 'changed since verification' and joins a proposed clause onto the same sentence", async () => {
    const wrapper = await mountBanners({
      errataSummary: {
        total: 2,
        verified: 0,
        reported: 0,
        rejected: 1,
        changed: 1,
        proposed: 1,
      },
    });

    expect(wrapper.text()).toContain(
      "This decision has 2 errata (1 changed since verification, 1 rejected); " +
        "1 more is proposed.",
    );
    expect(wrapper.text()).not.toContain("0 verified");
    expect(wrapper.text()).not.toContain("0 reported");
  });

  it("pluralizes the proposed clause for more than one proposed erratum", async () => {
    const wrapper = await mountBanners({
      errataSummary: {
        total: 1,
        verified: 1,
        reported: 0,
        rejected: 0,
        changed: 0,
        proposed: 2,
      },
    });

    expect(wrapper.text()).toContain(
      "This decision has 1 erratum (1 verified or not requiring review); " +
        "2 more are proposed.",
    );
  });

  it("shows a dedicated proposed-only sentence when nothing is published yet", async () => {
    const wrapper = await mountBanners({
      errataSummary: {
        total: 0,
        verified: 0,
        reported: 0,
        rejected: 0,
        changed: 0,
        proposed: 3,
      },
    });

    expect(wrapper.text()).toContain(
      "This decision has 3 proposed errata (not yet published).",
    );
  });

  it("pluralizes a single proposed-only erratum", async () => {
    const wrapper = await mountBanners({
      errataSummary: {
        total: 0,
        verified: 0,
        reported: 0,
        rejected: 0,
        changed: 0,
        proposed: 1,
      },
    });

    expect(wrapper.text()).toContain(
      "This decision has 1 proposed erratum (not yet published).",
    );
  });

  it("shows no errata notice when there are neither published nor proposed errata", async () => {
    const wrapper = await mountBanners({ errataSummary: emptySummary() });

    expect(wrapper.text()).not.toContain("errata");
  });

  it("shows a resolved erratum-for banner linking to the corrected decision, with the erratum's own status", async () => {
    const wrapper = await mountBanners({
      erratumFor: {
        uuid: "33333333-3333-3333-3333-333333333333",
        id: "ccc",
        title: "Use PostgreSQL",
        resolved: true,
      },
      erratumApprovalState: "accepted",
      erratumKind: "published",
    });

    expect(wrapper.text()).toContain("This is an erratum for");
    expect(wrapper.find("a[href='/records/ccc']").text()).toBe("Use PostgreSQL");
    expect(wrapper.text()).toContain("Verified");
  });

  it("shows an unresolved erratum-for banner with the target's short UUID, full value reachable", async () => {
    const wrapper = await mountBanners({
      erratumFor: {
        uuid: "33333333-3333-3333-3333-333333333333",
        id: null,
        title: null,
        resolved: false,
      },
    });

    expect(wrapper.text()).toContain("This is an erratum for an unknown decision");
    expect(wrapper.text()).toContain("33333333");
    expect(wrapper.text()).not.toContain("33333333-3333-3333-3333-333333333333");
    const code = wrapper.find("code");
    expect(code.attributes("title")).toBe("33333333-3333-3333-3333-333333333333");
  });

  it("shows the viewed candidate erratum's 'Reported — Proposed' status, with its branch", async () => {
    const wrapper = await mountBanners({
      erratumFor: {
        uuid: "33333333-3333-3333-3333-333333333333",
        id: "ccc",
        title: "Use PostgreSQL",
        resolved: true,
      },
      erratumApprovalState: "pending",
      erratumKind: "candidate",
      erratumRef: "feature-x",
    });

    expect(wrapper.text()).toContain("Reported — Proposed (branch feature-x)");
  });
});
