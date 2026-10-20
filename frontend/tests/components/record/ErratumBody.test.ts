/**
 * Ensure `ErratumBody` falls back to the target's short UUID (full
 * value reachable) when the erratum-for target is unresolved, no
 * longer repeats the resolved "Erratum for <title>" line (that is now
 * the page's own `h1`, see `RecordHeader.vue`), renders its own
 * original/corrected text, and shows a clear fallback instead of an
 * empty card when the erratum's content was never indexed.
 */
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import ErratumBody from "@/components/record/ErratumBody.vue";
import type { ErratumContentOut, ErratumForOut } from "@/types/records";

function content(): ErratumContentOut {
  return {
    type: "technical",
    section: "Consequences",
    reported_by: "alice@example.com",
    reported_date: "2025-05-01",
    original_html: "<p>old</p>",
    corrected_html: "<p>new</p>",
    notes_html: null,
  };
}

async function mountBody(
  erratumFor: ErratumForOut | null,
  erratum: ErratumContentOut | null = content(),
) {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  const wrapper = mount(ErratumBody, {
    props: { erratum, erratumFor },
    global: { plugins: [router, vuetify] },
  });
  return wrapper;
}

describe("ErratumBody", () => {
  it("has a real h2 card title", async () => {
    const wrapper = await mountBody(null);

    expect(wrapper.find("h2").text()).toBe("Erratum");
  });

  it("shows nothing extra when the target is resolved (the page's own h1 covers it)", async () => {
    const wrapper = await mountBody({
      uuid: "11111111-1111-1111-1111-111111111111",
      id: "22222222-2222-2222-2222-222222222222",
      title: "Use PostgreSQL",
      resolved: true,
    });

    expect(wrapper.text()).not.toContain("Erratum for");
    expect(wrapper.find("a[href='/records/22222222-2222-2222-2222-222222222222']").exists()).toBe(
      false,
    );
  });

  it("falls back to the target's short UUID when unresolved, with the full value reachable", async () => {
    const wrapper = await mountBody({
      uuid: "33333333-3333-3333-3333-333333333333",
      id: null,
      title: null,
      resolved: false,
    });

    expect(wrapper.text()).toContain("Erratum for an unknown decision");
    expect(wrapper.text()).toContain("33333333");
    expect(wrapper.text()).not.toContain("33333333-3333-3333-3333-333333333333");
    const code = wrapper.find("code");
    expect(code.attributes("title")).toBe("33333333-3333-3333-3333-333333333333");
  });

  it("shows its own type, section, and text blocks when the target is unresolved", async () => {
    const wrapper = await mountBody(null);

    expect(wrapper.text()).toContain("Technical");
    expect(wrapper.text()).toContain("Section: Consequences");
    expect(wrapper.text()).toContain("Reported by alice@example.com");
    expect(wrapper.text()).toContain("Original text — says:");
    expect(wrapper.text()).toContain("Corrected text — should say:");
  });

  it("omits its own 'Section: …' line when the header subtitle already shows it (R-11)", async () => {
    const wrapper = await mountBody({
      uuid: "11111111-1111-1111-1111-111111111111",
      id: "22222222-2222-2222-2222-222222222222",
      title: "Use PostgreSQL",
      resolved: true,
    });

    expect(wrapper.text()).not.toContain("Section: Consequences");
    // The rest of the meta line is unaffected.
    expect(wrapper.text()).toContain("Technical");
    expect(wrapper.text()).toContain("Reported by alice@example.com");
  });

  it("shows 'Content not indexed yet' instead of an empty card when erratum content is null", async () => {
    const wrapper = await mountBody(null, null);

    expect(wrapper.text()).toContain("Content not indexed yet.");
    expect(wrapper.text()).not.toContain("Type not set");
    expect(wrapper.text()).not.toContain("Corrected text — should say:");
  });
});
