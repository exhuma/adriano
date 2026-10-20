/**
 * Ensure the record page's prominent status banners render for each
 * independently optional case (rfc-editor.org/info reference design:
 * "This RFC is now obsolete, see RFC 9110" / "was updated, see RFC
 * 8615"): obsoleted, updated, has-errata (with counts), and -- on an
 * erratum page -- which decision it corrects, resolved or not.
 */
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordStatusBanners from "@/components/record/RecordStatusBanners.vue";
import type { ErrataSummaryOut, ErratumForOut, InboundLinkOut } from "@/types/records";

function emptySummary(): ErrataSummaryOut {
  return { total: 0, verified: 0, reported: 0, rejected: 0, changed: 0, proposed: 0 };
}

async function mountBanners(props: {
  obsoletedBy?: InboundLinkOut[];
  updatedBy?: InboundLinkOut[];
  errataSummary?: ErrataSummaryOut;
  erratumFor?: ErratumForOut | null;
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
      "This decision has 3 errata (2 verified, 1 reported).",
    );
    expect(wrapper.find("a[href='#errata']").exists()).toBe(true);
  });

  it("includes changed and rejected counts only when nonzero, and a proposed sentence", async () => {
    const wrapper = await mountBanners({
      errataSummary: {
        total: 2,
        verified: 1,
        reported: 0,
        rejected: 1,
        changed: 1,
        proposed: 2,
      },
    });

    expect(wrapper.text()).toContain(
      "This decision has 2 errata (1 verified, 0 reported, 1 changed, 1 rejected).",
    );
    expect(wrapper.text()).toContain("2 proposed.");
  });

  it("shows no errata notice when there are neither published nor proposed errata", async () => {
    const wrapper = await mountBanners({ errataSummary: emptySummary() });

    expect(wrapper.text()).not.toContain("errata");
  });

  it("shows a resolved erratum-for banner linking to the corrected decision", async () => {
    const wrapper = await mountBanners({
      erratumFor: {
        uuid: "33333333-3333-3333-3333-333333333333",
        id: "ccc",
        title: "Use PostgreSQL",
        resolved: true,
      },
    });

    expect(wrapper.text()).toContain("This is an erratum for");
    expect(wrapper.find("a[href='/records/ccc']").text()).toBe("Use PostgreSQL");
  });

  it("shows an unresolved erratum-for banner with the target's short UUID", async () => {
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
  });
});
