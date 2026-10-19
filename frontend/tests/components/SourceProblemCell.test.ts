/**
 * Ensure the Sources-table problem cell renders each display kind
 * correctly, with the dash fallback when there is nothing to show.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import SourceProblemCell from "@/components/SourceProblemCell.vue";

describe("SourceProblemCell", () => {
  it("shows a dash when there is no problem and no hint", () => {
    const wrapper = mount(SourceProblemCell, {
      props: { problem: { kind: "none" }, hint: null },
    });
    expect(wrapper.text()).toBe("—");
  });

  it("renders a text problem", () => {
    const wrapper = mount(SourceProblemCell, {
      props: { problem: { kind: "text", text: "disk full" }, hint: null },
    });
    expect(wrapper.text()).toContain("disk full");
  });

  it("renders a list problem with code as secondary text", () => {
    const wrapper = mount(SourceProblemCell, {
      props: {
        problem: {
          kind: "list",
          items: [{ message: "fake source is down", code: "source_error" }],
        },
        hint: "Check the root path and scope in catalog.yaml, then poll again.",
      },
    });
    const items = wrapper.findAll("li");
    expect(items).toHaveLength(1);
    expect(items[0].text()).toContain("fake source is down");
    expect(items[0].text()).toContain("source_error");
    expect(wrapper.text()).toContain("Check the root path");
  });
});
