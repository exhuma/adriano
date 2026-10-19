/**
 * Ensure the health composable reflects /healthz on mount, maps the
 * backend's 503 "degraded" body correctly, and re-checks on window
 * focus.
 */
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useHealth } from "@/composables/useHealth";

const HealthProbe = defineComponent({
  setup() {
    const { state } = useHealth();
    return () => h("span", state.value);
  },
});

describe("useHealth", () => {
  const originalFetch = globalThis.fetch;
  let wrapper: VueWrapper | null = null;

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("reports ok after a healthy /healthz response", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ status: "ok", database: "ok" }),
          { status: 200 },
        ),
      );

    wrapper = mount(HealthProbe);
    await flushPromises();

    expect(wrapper.text()).toBe("ok");
  });

  it("reports degraded for the backend's well-formed 503 body", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ status: "degraded", database: "unavailable" }),
        { status: 503 },
      ),
    );

    wrapper = mount(HealthProbe);
    await flushPromises();

    expect(wrapper.text()).toBe("degraded");
  });

  it("reports error when the backend cannot be reached at all", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    wrapper = mount(HealthProbe);
    await flushPromises();

    expect(wrapper.text()).toBe("error");
  });

  it("re-checks when the window regains focus", async () => {
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(
          JSON.stringify({ status: "ok", database: "ok" }),
          { status: 200 },
        ),
    );
    globalThis.fetch = fetchMock;

    wrapper = mount(HealthProbe);
    await flushPromises();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    window.dispatchEvent(new Event("focus"));
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
