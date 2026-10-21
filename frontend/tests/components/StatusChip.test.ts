/**
 * Ensure `StatusChip` never puts `aria-label` on its `v-chip` root
 * (P11-R-15: a plain, non-interactive `<span>` by default, on which
 * `aria-label` has no defined accessibility mapping -- axe's
 * `aria-prohibited-attr` rule). When `ariaLabel` differs from the
 * visible `text` (the shortened-for-space case, e.g. "DEV" standing
 * in for "DEV LOGIN"), the short text is hidden from assistive tech
 * and the full text is exposed through ordinary, visually hidden
 * content instead. When no `ariaLabel` is given, or it matches
 * `text` exactly, the chip renders the plain text with no hidden
 * duplicate.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import StatusChip from "@/components/StatusChip.vue";

describe("StatusChip", () => {
  it("never sets aria-label on the chip element", () => {
    const wrapper = mount(StatusChip, {
      props: {
        icon: "mdi-flask-outline",
        text: "DEV",
        ariaLabel: "DEV LOGIN: development login mode is active",
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.find(".v-chip").attributes("aria-label")).toBeUndefined();
  });

  it("hides the short text from assistive tech and exposes the full text", () => {
    const wrapper = mount(StatusChip, {
      props: {
        icon: "mdi-flask-outline",
        text: "DEV",
        ariaLabel: "DEV LOGIN: development login mode is active",
      },
      global: { plugins: [vuetify] },
    });

    const visible = wrapper
      .findAll("span")
      .find((span) => span.text() === "DEV");
    expect(visible?.attributes("aria-hidden")).toBe("true");

    const full = wrapper.find(".d-sr-only");
    expect(full.exists()).toBe(true);
    expect(full.text()).toBe("DEV LOGIN: development login mode is active");

    // Still visible to a sighted user, and findable in the hover
    // title, regardless of the assistive-tech wiring above.
    expect(wrapper.text()).toContain("DEV");
    expect(wrapper.find(".v-chip").attributes("title")).toBe(
      "DEV LOGIN: development login mode is active",
    );
  });

  it("renders plain text with no hidden duplicate when no ariaLabel is given", () => {
    const wrapper = mount(StatusChip, {
      props: { icon: "mdi-check-circle", text: "Backend online" },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.find(".d-sr-only").exists()).toBe(false);
    const visible = wrapper
      .findAll("span")
      .find((span) => span.text() === "Backend online");
    expect(visible?.attributes("aria-hidden")).toBeUndefined();
    expect(wrapper.find(".v-chip").attributes("title")).toBe(
      "Backend online",
    );
  });

  it("renders plain text with no hidden duplicate when ariaLabel matches text", () => {
    const wrapper = mount(StatusChip, {
      props: {
        icon: "mdi-check-circle",
        text: "Backend online",
        ariaLabel: "Backend online",
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.find(".d-sr-only").exists()).toBe(false);
  });
});
