/**
 * Ensure `useSearchQuery` keeps filters in sync with the URL: initial
 * values are read from the query string, free-text `q` changes are
 * debounced before they reach the URL (and reset the page), the
 * other filters apply immediately, "Clear filters" resets and clears
 * the URL, and external navigation (back/forward) restores the
 * refs.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSearchQuery } from "@/composables/useSearchQuery";

type SearchQueryApi = ReturnType<typeof useSearchQuery>;

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
}

async function mountSearchQuery(
  initialPath: string,
  debounceMs = 300,
): Promise<{ router: Router; api: SearchQueryApi }> {
  const router = makeRouter();
  await router.push(initialPath);
  await router.isReady();

  let api!: SearchQueryApi;
  const Probe = defineComponent({
    setup() {
      api = useSearchQuery({ debounceMs });
      return () => h("div");
    },
  });
  mount(Probe, { global: { plugins: [router] } });
  await flushPromises();
  return { router, api };
}

describe("useSearchQuery", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("reads initial filters and page from the URL", async () => {
    const { api } = await mountSearchQuery(
      "/?q=postgres&source=central&project=platform&state=published&page=3",
    );

    expect(api.q.value).toBe("postgres");
    expect(api.source.value).toBe("central");
    expect(api.project.value).toBe("platform");
    expect(api.state.value).toBe("published");
    expect(api.page.value).toBe(3);
    expect(api.hasActiveFilters.value).toBe(true);
  });

  it("treats a blank URL as no active filters and page 1", async () => {
    const { api } = await mountSearchQuery("/");

    expect(api.q.value).toBe("");
    expect(api.page.value).toBe(1);
    expect(api.hasActiveFilters.value).toBe(false);
  });

  it("debounces q before writing it to the URL and resets the page", async () => {
    const { router, api } = await mountSearchQuery("/?q=old&page=2", 300);

    api.q.value = "new";
    await flushPromises();
    // Not yet written: the debounce has not elapsed.
    expect(router.currentRoute.value.query.q).toBe("old");

    await vi.advanceTimersByTimeAsync(299);
    expect(router.currentRoute.value.query.q).toBe("old");

    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();
    expect(router.currentRoute.value.query.q).toBe("new");
    // Changing the search term resets pagination.
    expect(router.currentRoute.value.query.page).toBeUndefined();
    expect(api.page.value).toBe(1);
  });

  it("only writes the latest value when q changes repeatedly within the delay", async () => {
    const { router, api } = await mountSearchQuery("/", 300);

    api.q.value = "a";
    await flushPromises();
    await vi.advanceTimersByTimeAsync(150);
    api.q.value = "ab";
    await flushPromises();
    await vi.advanceTimersByTimeAsync(150);
    // The first debounce window never completed.
    expect(router.currentRoute.value.query.q).toBeUndefined();

    await vi.advanceTimersByTimeAsync(150);
    await flushPromises();
    expect(router.currentRoute.value.query.q).toBe("ab");
  });

  it("applies source/project/state changes immediately, without debounce", async () => {
    const { router, api } = await mountSearchQuery("/");

    api.source.value = "central";
    await flushPromises();

    expect(router.currentRoute.value.query.source).toBe("central");
  });

  it("reads needs_approval from the URL and includes it in active filters", async () => {
    const { api } = await mountSearchQuery("/?needs_approval=true");

    expect(api.needsApproval.value).toBe(true);
    expect(api.hasActiveFilters.value).toBe(true);
  });

  it("applies needs_approval immediately, without debounce", async () => {
    const { router, api } = await mountSearchQuery("/");

    api.needsApproval.value = true;
    await flushPromises();

    expect(router.currentRoute.value.query.needs_approval).toBe("true");
  });

  it("clearFilters resets every filter (including needs_approval and record_type) and clears the URL", async () => {
    const { router, api } = await mountSearchQuery(
      "/?q=postgres&source=central&project=platform&state=candidate" +
        "&needs_approval=true&record_type=all&page=2",
    );

    api.clearFilters();
    await flushPromises();

    expect(api.q.value).toBe("");
    expect(api.source.value).toBe("");
    expect(api.project.value).toBe("");
    expect(api.state.value).toBe("");
    expect(api.needsApproval.value).toBe(false);
    expect(api.recordType.value).toBe("decision");
    expect(api.page.value).toBe(1);
    expect(router.currentRoute.value.query).toEqual({});
  });

  it("defaults record_type to 'decision', omitted from the URL and not an active filter", async () => {
    const { api } = await mountSearchQuery("/");

    expect(api.recordType.value).toBe("decision");
    expect(api.hasActiveFilters.value).toBe(false);
  });

  it("reads record_type from the URL and includes a non-default value in active filters", async () => {
    const { api } = await mountSearchQuery("/?record_type=erratum");

    expect(api.recordType.value).toBe("erratum");
    expect(api.hasActiveFilters.value).toBe(true);
  });

  it("applies record_type immediately, without debounce, and omits the default from the URL", async () => {
    const { router, api } = await mountSearchQuery("/");

    api.recordType.value = "all";
    await flushPromises();
    expect(router.currentRoute.value.query.record_type).toBe("all");

    api.recordType.value = "decision";
    await flushPromises();
    expect(router.currentRoute.value.query.record_type).toBeUndefined();
  });

  it("ignores an invalid record_type in the URL, falling back to the default", async () => {
    const { api } = await mountSearchQuery("/?record_type=bogus");

    expect(api.recordType.value).toBe("decision");
  });

  it("clearFilters discards a pending debounced q change", async () => {
    const { router, api } = await mountSearchQuery("/", 300);

    api.q.value = "will be discarded";
    await flushPromises();
    api.clearFilters();
    await flushPromises();

    await vi.advanceTimersByTimeAsync(400);
    await flushPromises();

    expect(api.q.value).toBe("");
    expect(router.currentRoute.value.query.q).toBeUndefined();
  });

  it("restores filters on external navigation (back/forward)", async () => {
    const { router, api } = await mountSearchQuery("/?q=first");

    await router.push({ query: { q: "second", source: "central" } });
    await flushPromises();

    expect(api.q.value).toBe("second");
    expect(api.source.value).toBe("central");
  });
});
