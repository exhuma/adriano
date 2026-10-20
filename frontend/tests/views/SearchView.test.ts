/**
 * Ensure the search landing page renders the honest empty states
 * (catalog empty vs. no matches for the active filters), the loaded
 * result list with its status chips, and an error state with a
 * working retry -- all against a mocked API, never a real request.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import SearchView from "@/views/SearchView.vue";
import type { FacetsOut } from "@/types/sources";
import type { SearchPage } from "@/types/records";

const searchRecords = vi.fn();
const getFacets = vi.fn();

// `vi.mock` calls are hoisted above these imports by Vitest's
// transform, so `SearchView` above already resolves against the
// mocked module.
vi.mock("@/api/records", () => ({
  searchRecords: (...args: unknown[]) => searchRecords(...args),
  getFacets: (...args: unknown[]) => getFacets(...args),
}));

const emptyFacets: FacetsOut = { sources: [] };

function makeRouter(initialPath = "/"): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: SearchView },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  return router.push(initialPath).then(() => router.isReady()).then(() => router);
}

async function mountSearchView(initialPath = "/") {
  const router = await makeRouter(initialPath);
  const wrapper = mount(SearchView, {
    global: { plugins: [router, vuetify] },
  });
  await flushPromises();
  return { router, wrapper };
}

describe("SearchView", () => {
  beforeEach(() => {
    getFacets.mockResolvedValue(emptyFacets);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("shows the honest catalog-empty state with no filters applied", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/");

    expect(wrapper.text()).toContain("No indexed records yet");
    expect(wrapper.text()).not.toContain("No matches for your filters");
  });

  it("distinguishes 'no matches' from 'catalog empty' when filters are active", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/?q=nonexistent");

    expect(wrapper.text()).toContain("No matches for your filters");
    const clearButtons = wrapper
      .findAll("button")
      .filter((btn) => btn.text().includes("Clear filters"));
    expect(clearButtons.length).toBeGreaterThan(0);
  });

  it("renders results with state and approval chips and an accessible count", async () => {
    const page: SearchPage = {
      items: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          title: "Use PostgreSQL",
          source_id: "central",
          project: "platform",
          path: "doc/decisions/2023-01-10-use-postgres.md",
          ref: "local",
          kind: "published",
          record_kind: "decision",
          approval_state: "pending",
          issue_counts: { error: 0, warning: 1 },
          erratum_for_title: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/");

    expect(wrapper.text()).toContain("Use PostgreSQL");
    expect(wrapper.text()).toContain("central / platform");
    expect(wrapper.text()).toContain("Pending approval");
    expect(wrapper.text()).toContain("1 warning");
    expect(wrapper.find('[role="status"]').text()).toContain(
      "Showing 1–1 of 1 record.",
    );
  });

  it("shows an erratum row leading with 'Erratum for <title>', the stored title as secondary, and the erratum status chip", async () => {
    const page: SearchPage = {
      items: [
        {
          id: "44444444-4444-4444-4444-444444444444",
          title: "Erratum: Consequences",
          source_id: "central",
          project: "platform",
          path: "doc/decisions/errata/2025-05-01-fix.md",
          ref: "main",
          kind: "published",
          record_kind: "erratum",
          approval_state: "pending",
          issue_counts: { error: 0, warning: 0 },
          erratum_for_title: "Use PostgreSQL",
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/?record_type=erratum");

    expect(wrapper.text()).toContain("Erratum: Consequences");
    expect(wrapper.text()).toContain("Erratum for Use PostgreSQL");
    expect(wrapper.text()).toContain("Erratum");
    // The erratum vocabulary ("Reported"), not the decision wording
    // ("Pending approval"), for the row's own approval chip.
    expect(wrapper.text()).toContain("Reported");
    expect(wrapper.text()).not.toContain("Pending approval");
    const titleSpan = wrapper.find(".result-text span.text-subtitle-1");
    expect(titleSpan.text()).toBe("Erratum for Use PostgreSQL");
    expect(searchRecords).toHaveBeenCalledWith(
      expect.objectContaining({ record_type: "erratum" }),
    );
  });

  it("shows 'Erratum for an unknown decision' when the target is unresolved", async () => {
    const page: SearchPage = {
      items: [
        {
          id: "55555555-5555-5555-5555-555555555555",
          title: "Erratum: orphaned",
          source_id: "central",
          project: "platform",
          path: "doc/decisions/errata/2025-05-01-orphan.md",
          ref: "main",
          kind: "published",
          record_kind: "erratum",
          approval_state: "pending",
          issue_counts: { error: 0, warning: 0 },
          erratum_for_title: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/?record_type=erratum");

    expect(wrapper.text()).toContain("Erratum for an unknown decision");
  });

  it("normalises an invalid record_type in the URL to the default, as a non-active filter", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/?record_type=bogus");

    expect(searchRecords).toHaveBeenCalledWith(
      expect.objectContaining({ record_type: undefined }),
    );
    // Not treated as an active filter: the empty state is the
    // honest "catalog empty" one, not "no matches for your filters".
    expect(wrapper.text()).toContain("No indexed records yet");
  });

  it("shows an error state and retries the same request on demand", async () => {
    searchRecords.mockRejectedValueOnce(new Error("network down"));
    searchRecords.mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    const { wrapper } = await mountSearchView("/");

    expect(wrapper.text()).toContain("Couldn't load search results");

    const retryButton = wrapper
      .findAll("button")
      .find((btn) => btn.text().includes("Retry"));
    expect(retryButton).toBeDefined();
    await retryButton!.trigger("click");
    await flushPromises();

    expect(searchRecords).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("No indexed records yet");
  });
});
