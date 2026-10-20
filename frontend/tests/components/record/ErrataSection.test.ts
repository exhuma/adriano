/**
 * Ensure the errata section groups published errata before a
 * "Proposed errata" group of candidates, shows each one's status and
 * type, collapses a rejected erratum behind a toggle (expanding on
 * click), and falls back to "Content not indexed yet" when
 * `has_content` is false.
 */
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { afterEach, describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import ErrataSection from "@/components/record/ErrataSection.vue";
import type { ErratumOut } from "@/types/records";

function erratum(overrides: Partial<ErratumOut> = {}): ErratumOut {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    kind: "published",
    ref: "main",
    source_id: "central",
    project: "platform",
    path: "doc/decisions/errata/2025-05-01-fix.md",
    title: "Erratum: Consequences",
    type: "technical",
    section: "Consequences",
    reported_by: null,
    reported_date: null,
    original_html: null,
    corrected_html: "<p>fixed</p>",
    notes_html: null,
    approval_state: "pending",
    digest: "sha256-v1:def",
    updated_at: "2026-01-01T00:00:00Z",
    has_content: true,
    ...overrides,
  };
}

async function mountSection(errata: ErratumOut[]) {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  // `attachTo: document.body` is required for `isVisible()` (used by
  // the toggle-region test below) to read real computed styles --
  // jsdom only computes style for attached elements.
  const wrapper = mount(ErrataSection, {
    props: { errata },
    global: { plugins: [router, vuetify] },
    attachTo: document.body,
  });
  return wrapper;
}

describe("ErrataSection", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("hides the whole section when there are no errata", async () => {
    const wrapper = await mountSection([]);

    expect(wrapper.find("#errata").exists()).toBe(false);
  });

  it("counts only published errata in the heading, with proposed shown separately", async () => {
    const published = erratum({ id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", kind: "published" });
    const candidate = erratum({
      id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      kind: "candidate",
      ref: "feature-x",
    });
    const wrapper = await mountSection([published, candidate]);

    // Matches `RecordHeader`'s errata link, which also counts
    // published errata only -- the two headline counts must never
    // contradict each other. Never a bare "(0)" (R-13).
    expect(wrapper.find("h2").text()).toBe("Errata — 1 erratum · 1 proposed");
    const html = wrapper.html();
    expect(html.indexOf("aaaaaaaa")).toBeLessThan(html.indexOf("Proposed errata"));
    expect(html.indexOf("Proposed errata")).toBeLessThan(html.indexOf("bbbbbbbb"));
  });

  it("shows status and type chips for each erratum", async () => {
    const wrapper = await mountSection([erratum({ approval_state: "accepted", type: "editorial" })]);

    expect(wrapper.text()).toContain("Verified");
    expect(wrapper.text()).toContain("Editorial");
  });

  it("appends the proposed/branch suffix for a candidate erratum", async () => {
    const wrapper = await mountSection([
      erratum({ kind: "candidate", ref: "feature-x", approval_state: "pending" }),
    ]);

    expect(wrapper.text()).toContain("Reported — Proposed (branch feature-x)");
  });

  it("collapses a rejected erratum by default behind a toggle wired with aria-controls, expanding on click", async () => {
    const wrapper = await mountSection([erratum({ approval_state: "rejected" })]);

    const toggle = wrapper.find("button[aria-expanded='false']");
    expect(toggle.exists()).toBe(true);
    const controlsId = toggle.attributes("aria-controls");
    expect(controlsId).toBeTruthy();
    // The controlled region exists in the DOM (not `v-if`-removed) so
    // `aria-controls` always points at a real element, merely hidden
    // while collapsed -- the WAI-ARIA disclosure pattern.
    const region = wrapper.find(`#${controlsId}`);
    expect(region.exists()).toBe(true);
    expect(region.isVisible()).toBe(false);

    await toggle.trigger("click");

    expect(wrapper.text()).toContain("Corrected text — should say:");
    expect(wrapper.find("button[aria-expanded='true']").exists()).toBe(true);
    expect(region.isVisible()).toBe(true);
  });

  it("expands a non-rejected erratum by default, with no toggle button", async () => {
    const wrapper = await mountSection([erratum({ approval_state: "pending" })]);

    expect(wrapper.text()).toContain("Corrected text — should say:");
    expect(wrapper.find("button[aria-expanded]").exists()).toBe(false);
  });

  it("shows 'Content not indexed yet' instead of text blocks when has_content is false", async () => {
    const wrapper = await mountSection([erratum({ has_content: false })]);

    expect(wrapper.text()).toContain("Content not indexed yet");
    expect(wrapper.text()).not.toContain("Corrected text — should say:");
    expect(wrapper.find("a[href='/records/11111111-1111-1111-1111-111111111111']").exists()).toBe(
      true,
    );
  });
});
