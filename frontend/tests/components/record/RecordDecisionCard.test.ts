/**
 * Ensure `RecordDecisionCard` has no "Decision record" card title
 * (R-03: that was a third repetition of the page's own h1), and skips
 * a leading markdown h1 that duplicates the record's own title while
 * rendering every other body element untouched.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordDecisionCard from "@/components/record/RecordDecisionCard.vue";

function mountCard(renderedHtml: string, title: string) {
  return mount(RecordDecisionCard, {
    props: { renderedHtml, title },
    global: { plugins: [vuetify] },
  });
}

describe("RecordDecisionCard", () => {
  it("has no 'Decision record' card title", () => {
    const wrapper = mountCard("<h1>Use PostgreSQL</h1><p>Context</p>", "Use PostgreSQL");

    expect(wrapper.text()).not.toContain("Decision record");
  });

  it("skips a leading markdown h1 that duplicates the record title", () => {
    const wrapper = mountCard(
      "<h1>Use PostgreSQL</h1><h2>Context</h2><p>Body text.</p>",
      "Use PostgreSQL",
    );

    expect(wrapper.find("h1").exists()).toBe(false);
    expect(wrapper.find("h2").text()).toBe("Context");
    expect(wrapper.text()).toContain("Body text.");
  });

  it("keeps a leading markdown h1 that does not match the record title", () => {
    const wrapper = mountCard(
      "<h1>Different heading</h1><p>Context</p>",
      "Use PostgreSQL",
    );

    expect(wrapper.find("h1").text()).toBe("Different heading");
  });
});
