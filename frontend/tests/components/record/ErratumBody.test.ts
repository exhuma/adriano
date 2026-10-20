/**
 * Ensure `ErratumBody` shows the resolved "Erratum for <title>" link
 * when the target resolves, falls back to the short UUID when it
 * does not, and renders its own original/corrected text.
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

async function mountBody(erratumFor: ErratumForOut | null) {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  const wrapper = mount(ErratumBody, {
    props: { erratum: content(), erratumFor },
    global: { plugins: [router, vuetify] },
  });
  return wrapper;
}

describe("ErratumBody", () => {
  it("links to the resolved decision it corrects", async () => {
    const wrapper = await mountBody({
      uuid: "11111111-1111-1111-1111-111111111111",
      id: "22222222-2222-2222-2222-222222222222",
      title: "Use PostgreSQL",
      resolved: true,
    });

    expect(wrapper.text()).toContain("Erratum for");
    const link = wrapper.find("a[href='/records/22222222-2222-2222-2222-222222222222']");
    expect(link.text()).toBe("Use PostgreSQL");
  });

  it("falls back to the target's short UUID when unresolved", async () => {
    const wrapper = await mountBody({
      uuid: "33333333-3333-3333-3333-333333333333",
      id: null,
      title: null,
      resolved: false,
    });

    expect(wrapper.text()).toContain("Erratum for an unknown decision");
    expect(wrapper.text()).toContain("33333333");
    expect(wrapper.text()).not.toContain("33333333-3333-3333-3333-333333333333");
  });

  it("shows its own type, section, and text blocks", async () => {
    const wrapper = await mountBody(null);

    expect(wrapper.text()).toContain("Technical");
    expect(wrapper.text()).toContain("Section: Consequences");
    expect(wrapper.text()).toContain("Reported by alice@example.com");
    expect(wrapper.text()).toContain("Original text — says:");
    expect(wrapper.text()).toContain("Corrected text — should say:");
  });
});
