/**
 * Ensure the Sources-table problem cell renders each display kind
 * correctly, with the dash fallback when there is nothing to show;
 * that a recognised poll-problem code gets a plain-language headline
 * while the backend's own message stays as secondary "Details" text; and that
 * operator-only detail (env-var
 * names, recovery steps) is hidden from a reader entirely (decision
 * 3, Task 8).
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import SourceProblemCell from "@/components/SourceProblemCell.vue";

describe("SourceProblemCell", () => {
  it("shows a dash when there is no problem and no hint", () => {
    const wrapper = mount(SourceProblemCell, {
      props: { problem: { kind: "none" }, hint: null, canOperate: true },
    });
    expect(wrapper.text()).toBe("—");
  });

  it("renders a text problem under a generic headline", () => {
    const wrapper = mount(SourceProblemCell, {
      props: {
        problem: { kind: "text", text: "disk full" },
        hint: null,
        canOperate: true,
      },
    });
    expect(wrapper.text()).toContain("disk full");
    expect(wrapper.text()).toContain("Problem");
  });

  it("labels a recognised code and keeps the raw message as Details", () => {
    const wrapper = mount(SourceProblemCell, {
      props: {
        problem: {
          kind: "list",
          items: [{ message: "fake source is down", code: "source_error" }],
        },
        hint: "Check the root path and scope in catalog.yaml, then poll again.",
        canOperate: true,
      },
    });
    const items = wrapper.findAll("li");
    expect(items).toHaveLength(1);
    expect(items[0].text()).toContain("Couldn't reach the source");
    expect(items[0].text()).toContain("Details: fake source is down");
    expect(wrapper.text()).toContain("Check the root path");
  });

  it("falls back to the raw message alone for an unrecognised code", () => {
    const wrapper = mount(SourceProblemCell, {
      props: {
        problem: {
          kind: "list",
          items: [{ message: "a future problem", code: "future_code" }],
        },
        hint: null,
        canOperate: true,
      },
    });
    expect(wrapper.text()).toContain("a future problem");
    expect(wrapper.text()).not.toContain("Details:");
  });

  it("labels a config error by its code, keeping the raw text as " +
    "Details (R-10)", () => {
    const wrapper = mount(SourceProblemCell, {
      props: {
        problem: {
          kind: "config",
          code: "token_env_missing",
          text: "token_env: GitLab token env var GL_TOKEN is not set",
        },
        hint: null,
        canOperate: true,
      },
    });
    expect(wrapper.text()).toContain("Configuration problem");
    expect(wrapper.text()).toContain(
      "The access token's environment variable is not set",
    );
    expect(wrapper.text()).toContain(
      "Details: token_env: GitLab token env var GL_TOKEN is not set",
    );
  });

  it("shows a config error's raw text alone without a code", () => {
    const wrapper = mount(SourceProblemCell, {
      props: {
        problem: { kind: "config", code: null, text: "something odd" },
        hint: null,
        canOperate: true,
      },
    });
    expect(wrapper.text()).toContain("something odd");
    expect(wrapper.text()).not.toContain("Details:");
  });

  it("hides a config error from a reader", () => {
    const wrapper = mount(SourceProblemCell, {
      props: {
        problem: {
          kind: "config",
          code: "token_env_missing",
          text: "token_env: GitLab token env var GL_TOKEN is not set",
        },
        hint: null,
        canOperate: false,
      },
    });
    expect(wrapper.text()).toBe("—");
  });

  it("hides problem and recovery detail entirely for a reader", () => {
    const wrapper = mount(SourceProblemCell, {
      props: {
        problem: {
          kind: "list",
          items: [{ message: "fake source is down", code: "source_error" }],
        },
        hint: "Check the root path and scope in catalog.yaml, then poll again.",
        canOperate: false,
      },
    });
    expect(wrapper.text()).toBe("—");
  });
});
