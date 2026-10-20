/**
 * Ensure the record page's prominent status banners render for each
 * independently optional case (rfc-editor.org/info reference design:
 * "This RFC is now obsolete, see RFC 9110" / "was updated, see RFC
 * 8615"): a single lifecycle notice (obsoleted takes priority over
 * updated, never the error colour, R-04), and -- on an erratum page
 * -- which decision it corrects (resolved or not), without repeating
 * its own approval-state chip (R-11).
 */
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordStatusBanners from "@/components/record/RecordStatusBanners.vue";
import type { DisplayStatus, ErratumForOut, InboundLinkOut } from "@/types/records";

async function mountBanners(props: {
  status?: DisplayStatus;
  obsoletedBy?: InboundLinkOut[];
  updatedBy?: InboundLinkOut[];
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
      status: props.status ?? "active",
      obsoletedBy: props.obsoletedBy ?? [],
      updatedBy: props.updatedBy ?? [],
      erratumFor: props.erratumFor ?? null,
    },
    global: { plugins: [router, vuetify] },
  });
  return wrapper;
}

describe("RecordStatusBanners", () => {
  it("renders nothing for an active record with no erratum-for link", async () => {
    const wrapper = await mountBanners({});

    expect(wrapper.text().trim()).toBe("");
  });

  it("shows the obsoleted lifecycle notice with a link to each superseding decision, never in the error colour", async () => {
    const wrapper = await mountBanners({
      status: "obsoleted",
      obsoletedBy: [
        { link_type: "obsoleted_by", source_id: "aaa", source_title: "Use gRPC" },
      ],
    });

    expect(wrapper.text()).toContain("This decision is obsolete, see");
    const link = wrapper.find("a[href='/records/aaa']");
    expect(link.text()).toBe("Use gRPC");
    const alert = wrapper.findComponent({ name: "VAlert" });
    expect(alert.props("type")).not.toBe("error");
  });

  it("shows the updated lifecycle notice distinctly from the obsoleted one", async () => {
    const wrapper = await mountBanners({
      status: "updated",
      updatedBy: [
        { link_type: "updated_by", source_id: "bbb", source_title: "Use PostgreSQL v2" },
      ],
    });

    expect(wrapper.text()).toContain("This decision was updated, see");
    expect(wrapper.text()).not.toContain("This decision is obsolete");
    expect(wrapper.find("a[href='/records/bbb']").text()).toBe("Use PostgreSQL v2");
  });

  it("prefers the obsoleted notice over the updated one when both link lists are present", async () => {
    const wrapper = await mountBanners({
      status: "obsoleted",
      obsoletedBy: [
        { link_type: "obsoleted_by", source_id: "aaa", source_title: "Use gRPC" },
      ],
      updatedBy: [
        { link_type: "updated_by", source_id: "bbb", source_title: "Use PostgreSQL v2" },
      ],
    });

    expect(wrapper.text()).toContain("This decision is obsolete, see");
    expect(wrapper.text()).not.toContain("was updated");
  });

  it("shows a resolved erratum-for banner linking to the corrected decision, without repeating its own status chip", async () => {
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
    // R-11: the status already shows in the sidebar and the Approval
    // card, so this banner must not render its own chip.
    expect(wrapper.findComponent({ name: "StatusChip" }).exists()).toBe(false);
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
});
