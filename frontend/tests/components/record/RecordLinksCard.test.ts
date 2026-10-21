/**
 * Ensure outbound/inbound links never show a full raw UUID as
 * primary content: a resolved link uses its title; an unresolved or
 * untitled target shows a short UUID with the full value reachable
 * via tooltip and copy-to-clipboard.
 */
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordLinksCard from "@/components/record/RecordLinksCard.vue";
import type { InboundLinkOut, OutboundLinkOut } from "@/types/records";

const TARGET_UUID = "33333333-3333-3333-3333-333333333333";

/** A real router (not a stub) so `<router-link>` resolves to a real,
 *  inspectable `<a>` -- needed by the "New issues" #1/#2 tests below,
 *  which check the link's own classes. */
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: "/", component: { template: "<div />" } },
    { path: "/records/:id", component: { template: "<div />" } },
  ],
});

function mountCard(
  outboundLinks: OutboundLinkOut[],
  inboundLinks: InboundLinkOut[] = [],
) {
  return mount(RecordLinksCard, {
    props: { outboundLinks, inboundLinks },
    global: { plugins: [router, vuetify] },
  });
}

describe("RecordLinksCard", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the target's title as the link text when resolved", () => {
    const wrapper = mountCard([
      {
        link_type: "updates",
        target_uuid: TARGET_UUID,
        target_id: "44444444-4444-4444-4444-444444444444",
        target_title: "Adopt gRPC for internal APIs",
        resolution: "same_registration",
        ambiguous: false,
        candidate_ids: [],
      },
    ]);

    expect(wrapper.text()).toContain("Adopt gRPC for internal APIs");
    expect(wrapper.text()).not.toContain(TARGET_UUID);
  });

  it("shows a short UUID with copy for a resolved-but-untitled target", () => {
    const wrapper = mountCard([
      {
        link_type: "updates",
        target_uuid: TARGET_UUID,
        target_id: "44444444-4444-4444-4444-444444444444",
        target_title: null,
        resolution: "same_registration",
        ambiguous: false,
        candidate_ids: [],
      },
    ]);

    expect(wrapper.text()).toContain("Untitled");
    expect(wrapper.text()).not.toContain(TARGET_UUID);
    const code = wrapper.find("code");
    expect(code.text()).toBe("33333333");
    expect(code.attributes("title")).toBe(TARGET_UUID);
    expect(wrapper.find("button").exists()).toBe(true);
  });

  it("shows a short UUID with copy for an ambiguous target", () => {
    const wrapper = mountCard([
      {
        link_type: "obsoletes",
        target_uuid: TARGET_UUID,
        target_id: null,
        target_title: null,
        resolution: null,
        ambiguous: true,
        candidate_ids: ["a", "b"],
      },
    ]);

    expect(wrapper.text()).toContain("Ambiguous");
    expect(wrapper.text()).not.toContain(TARGET_UUID);
    const code = wrapper.find("code");
    expect(code.text()).toBe("33333333");
    expect(code.attributes("title")).toBe(TARGET_UUID);
  });

  it("shows a short UUID with copy for a missing target", () => {
    const wrapper = mountCard([
      {
        link_type: "obsoletes",
        target_uuid: TARGET_UUID,
        target_id: null,
        target_title: null,
        resolution: null,
        ambiguous: false,
        candidate_ids: [],
      },
    ]);

    expect(wrapper.text()).toContain("Missing target");
    expect(wrapper.text()).not.toContain(TARGET_UUID);
    const code = wrapper.find("code");
    expect(code.text()).toBe("33333333");
    expect(code.attributes("title")).toBe(TARGET_UUID);
  });

  it("copies the full target UUID, not the shortened form", async () => {
    const wrapper = mountCard([
      {
        link_type: "obsoletes",
        target_uuid: TARGET_UUID,
        target_id: null,
        target_title: null,
        resolution: null,
        ambiguous: false,
        candidate_ids: [],
      },
    ]);

    await wrapper.find("button").trigger("click");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(TARGET_UUID);
  });

  it("never shows a raw UUID for an inbound link (it has a title)", () => {
    const sourceId = "55555555-5555-5555-5555-555555555555";
    const wrapper = mountCard(
      [],
      [
        {
          link_type: "updated_by",
          source_id: sourceId,
          source_title: "Use PostgreSQL v2",
        },
      ],
    );

    expect(wrapper.text()).toContain("Use PostgreSQL v2");
    expect(wrapper.text()).not.toContain(sourceId);
  });

  // a resolved outbound link's own box
  // must be >=24px tall (`d-inline-block py-1`) and theme-coloured
  // (`text-primary`), with its `v-list-item-subtitle` ancestor's
  // medium-emphasis opacity reset to 1 so that colour is not
  // refaded under 4.5:1.
  it("enlarges and colours a resolved outbound link", () => {
    const wrapper = mountCard([
      {
        link_type: "updates",
        target_uuid: TARGET_UUID,
        target_id: "44444444-4444-4444-4444-444444444444",
        target_title: "Adopt gRPC for internal APIs",
        resolution: "same_registration",
        ambiguous: false,
        candidate_ids: [],
      },
    ]);

    const link = wrapper.findComponent({ name: "RouterLink" });
    expect(link.classes()).toContain("text-primary");
    expect(link.classes()).toContain("d-inline-block");
    expect(link.classes()).toContain("py-1");
    const subtitle = wrapper.find(".v-list-item-subtitle");
    expect(subtitle.attributes("style")).toContain(
      "--v-list-item-subtitle-opacity: 1",
    );
  });

  // Same follow-up: inbound links are always resolved, so the
  // opacity override and the colour/target-size classes apply
  // unconditionally.
  it("enlarges and colours an inbound link", () => {
    const sourceId = "55555555-5555-5555-5555-555555555555";
    const wrapper = mountCard(
      [],
      [
        {
          link_type: "updated_by",
          source_id: sourceId,
          source_title: "Use PostgreSQL v2",
        },
      ],
    );

    const link = wrapper.findComponent({ name: "RouterLink" });
    expect(link.classes()).toContain("text-primary");
    expect(link.classes()).toContain("d-inline-block");
    expect(link.classes()).toContain("py-1");
    const subtitle = wrapper.find(".v-list-item-subtitle");
    expect(subtitle.attributes("style")).toContain(
      "--v-list-item-subtitle-opacity: 1",
    );
  });
});
