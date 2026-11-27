/**
 * Ensure `useNotIndexedQuery` reads its filters from the URL, applies
 * the select filters immediately and the typed project after a
 * debounce, resets the page when a filter changes, and restores the
 * refs on back/forward.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useNotIndexedQuery } from "@/composables/useNotIndexedQuery";

type QueryApi = ReturnType<typeof useNotIndexedQuery>;

async function mountQuery(
  initialPath: string,
): Promise<{ router: Router; api: QueryApi }> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/not-indexed", component: { template: "<div />" } }],
  });
  await router.push(initialPath);
  await router.isReady();
  let api!: QueryApi;
  const Probe = defineComponent({
    setup() {
      api = useNotIndexedQuery();
      return () => h("div");
    },
  });
  mount(Probe, { global: { plugins: [router] } });
  await flushPromises();
  return { router, api };
}

describe("useNotIndexedQuery", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("reads the filters and page from the URL", async () => {
    const { api } = await mountQuery(
      "/not-indexed?source=central&project=p&reason=bad_yaml&origin=push&page=3",
    );

    expect(api.source.value).toBe("central");
    expect(api.project.value).toBe("p");
    expect(api.reason.value).toBe("bad_yaml");
    expect(api.origin.value).toBe("push");
    expect(api.page.value).toBe(3);
  });

  it("ignores an invalid origin and page", async () => {
    const { api } = await mountQuery("/not-indexed?origin=other&page=0");

    expect(api.origin.value).toBe("");
    expect(api.page.value).toBe(1);
  });

  it("applies a select filter at once and resets the page", async () => {
    const { router, api } = await mountQuery("/not-indexed?page=3");

    api.origin.value = "poll";
    await flushPromises();

    expect(router.currentRoute.value.query).toEqual({ origin: "poll" });
  });

  it("debounces the typed project before it reaches the URL", async () => {
    const { router, api } = await mountQuery("/not-indexed");

    api.project.value = "plat";
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({});

    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({ project: "plat" });
  });

  it("restores the filters on back/forward navigation", async () => {
    const { router, api } = await mountQuery("/not-indexed?source=central");

    await router.push("/not-indexed?reason=duplicate_uuid");
    await flushPromises();

    expect(api.source.value).toBe("");
    expect(api.reason.value).toBe("duplicate_uuid");
  });

  it("clearFilters resets every filter and clears the URL", async () => {
    const { router, api } = await mountQuery(
      "/not-indexed?source=central&origin=push&page=2",
    );

    api.clearFilters();
    await flushPromises();

    expect(api.source.value).toBe("");
    expect(api.origin.value).toBe("");
    expect(api.page.value).toBe(1);
    expect(router.currentRoute.value.query).toEqual({});
  });
});
