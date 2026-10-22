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
    // The empty state's own action ("Clear search and filters" --
    // see the dedicated S-07 test below), not the active-filter
    // row's "Clear filters": `q` alone sets no chip, so that row's
    // button stays hidden here (P11-R-05).
    const clearButtons = wrapper
      .findAll("button")
      .filter((btn) => btn.text().includes("Clear"));
    expect(clearButtons.length).toBeGreaterThan(0);
  });

  it("renders the empty-state title as a heading", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/");

    const heading = wrapper.find("h2");
    expect(heading.exists()).toBe(true);
    expect(heading.text()).toBe("No indexed records yet");
  });

  it("labels the no-matches action 'Clear search and filters' when a query is set, and 'Clear filters' otherwise (S-07)", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const withQuery = await mountSearchView("/?q=nonexistent");
    const queryAction = withQuery.wrapper
      .findAll("button")
      .find((btn) => btn.text().includes("Clear search and filters"));
    expect(queryAction).toBeDefined();

    const withoutQuery = await mountSearchView("/?source=central");
    const filterOnlyAction = withoutQuery.wrapper
      .findAll("button")
      .find((btn) => btn.text() === "Clear filters");
    expect(filterOnlyAction).toBeDefined();
    expect(
      withoutQuery.wrapper.text().includes("Clear search and filters"),
    ).toBe(false);
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
          approvable: true,
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
    // Two `role="status"` regions exist now: the active-filter row
    // (empty here -- no filter is active) and the result-count live
    // region.
    const statusRegions = wrapper.findAll('[role="status"]');
    const countRegion = statusRegions.find((region) =>
      region.text().includes("Showing"),
    );
    expect(countRegion?.text()).toContain("Showing 1–1 of 1 record.");
  });

  it("shows the neutral 'Blocked' status, not 'Pending approval', " +
    "for a row whose content cannot be decided (R-02)", async () => {
    const page: SearchPage = {
      items: [
        {
          id: "66666666-6666-6666-6666-666666666666",
          title: "No UUID here",
          source_id: "central",
          project: "platform",
          path: "doc/decisions/2023-01-11-no-uuid.md",
          ref: "local",
          kind: "published",
          record_kind: "decision",
          approval_state: "pending",
          approvable: false,
          issue_counts: { error: 1, warning: 0 },
          erratum_for_title: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/");

    expect(wrapper.text()).toContain("Blocked");
    expect(wrapper.text()).not.toContain("Pending approval");
  });

  it("hides the 'Published' chip (the default state) but shows 'Candidate' (S-02)", async () => {
    const base: SearchPage["items"][number] = {
      id: "22222222-2222-2222-2222-222222222222",
      title: "Use Stripe for card payment processing",
      source_id: "central",
      project: "payments",
      path: "doc/decisions/2023-02-01-stripe.md",
      ref: "local",
      kind: "published",
      record_kind: "decision",
      approval_state: "pending",
      approvable: true,
      issue_counts: { error: 0, warning: 0 },
      erratum_for_title: null,
    };
    searchRecords.mockResolvedValue({
      items: [
        base,
        {
          ...base,
          id: "33333333-3333-3333-3333-333333333333",
          kind: "candidate",
          ref: "feature/payments-migration",
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    });

    const { wrapper } = await mountSearchView("/");

    // Scoped to the results list: "Published" is also a static label
    // on the (untouched) state filter toggle button elsewhere on the
    // page.
    const list = wrapper.find(".results-list");
    expect(list.text()).not.toContain("Published");
    expect(list.text()).toContain("Candidate");
    // The branch is shown once, as plain text, never inside the chip.
    expect(list.text()).toContain("Ref: feature/payments-migration");
    const candidateChip = wrapper
      .findAllComponents({ name: "StatusChip" })
      .find((chip) => chip.props("text") === "Candidate");
    expect(candidateChip?.props("text")).toBe("Candidate");
  });

  it("shows 'Pending approval' as a neutral (uncoloured) chip, and a non-default state in colour (decision 2)", async () => {
    searchRecords.mockResolvedValue({
      items: [
        {
          id: "66666666-6666-6666-6666-666666666666",
          title: "Retire the legacy invoicing processor integration",
          source_id: "central",
          project: "payments",
          path: "doc/decisions/2023-03-01-retire.md",
          ref: "local",
          kind: "published",
          record_kind: "decision",
          approval_state: "pending",
          approvable: true,
          issue_counts: { error: 0, warning: 0 },
          erratum_for_title: null,
        },
        {
          id: "77777777-7777-7777-7777-777777777777",
          title: "Adopt gRPC for internal APIs",
          source_id: "central",
          project: "platform",
          path: "doc/decisions/2023-03-02-grpc.md",
          ref: "local",
          kind: "published",
          record_kind: "decision",
          approval_state: "changed_since_acceptance",
          approvable: true,
          issue_counts: { error: 0, warning: 0 },
          erratum_for_title: null,
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    });

    const { wrapper } = await mountSearchView("/");

    const chips = wrapper.findAllComponents({ name: "StatusChip" });
    const pendingChip = chips.find(
      (chip) => chip.props("text") === "Pending approval",
    );
    expect(pendingChip).toBeDefined();
    expect(pendingChip?.props("color")).toBeUndefined();

    // Shown to 1-2 words, with the full meaning kept for assistive
    // tech via the aria-label (the row link's accessible name must
    // still convey the state).
    const changedChip = chips.find((chip) => chip.props("text") === "Changed");
    expect(changedChip).toBeDefined();
    expect(changedChip?.props("color")).toBe("warning");
    expect(changedChip?.props("ariaLabel")).toBe("Changed since acceptance");
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
          approvable: true,
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
    const titleSpan = wrapper.find(".result-link span.text-title-medium");
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
          approvable: true,
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

  it("gives the needs-approval tooltip activator an accessible name (S-03)", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/");

    // The hint text moved off the switch (no more two-line
    // `persistent-hint`) and onto a focusable info button, named via
    // `aria-label` so it stays accessible whether or not the
    // hover/focus tooltip is open.
    const infoButton = wrapper
      .findAll("button")
      .find((btn) => (btn.attributes("aria-label") ?? "").includes("Needs approval"));
    expect(infoButton).toBeDefined();
    expect(infoButton!.attributes("aria-label")).toContain(
      "pending, rejected, changed since acceptance",
    );
    expect(wrapper.text()).not.toContain(
      "Pending, rejected, changed since acceptance, or no approval policy",
    );
    // Regression check: nesting `<v-tooltip activator="parent">`
    // inside a `<v-btn icon="...">` makes Vuetify treat the button as
    // having custom slot content and silently skip auto-rendering the
    // `icon` prop's glyph, leaving the button visually empty
    // (coordinator browser check caught this at 1920px -- the button
    // existed, at the right size and position, but painted nothing).
    // An explicit `<v-icon>` must stay in the template.
    expect(infoButton!.find(".mdi-information-outline").exists()).toBe(true);
  });

  it("uses a non-warning colour for the needs-approval switch (decision 2, S-04)", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/");

    const switchComponent = wrapper.findComponent({ name: "VSwitch" });
    expect(switchComponent.props("color")).toBe("primary");
  });

  it("shows one closable chip per active filter in a live region, and a chip close clears only that filter (S-04)", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);
    // `project: "platform"` must stay a valid option under `source:
    // "central"` here -- SearchView's (pre-existing, untouched by
    // this task) `watch(source, ...)` clears `project` whenever it no
    // longer matches the current source's project list, which would
    // otherwise confound this test with an unrelated second filter
    // change.
    getFacets.mockResolvedValue({
      sources: [
        {
          source_id: "central",
          count: 1,
          projects: [{ project: "platform", count: 1 }],
        },
      ],
    });

    const { router, wrapper } = await mountSearchView(
      "/?needs_approval=true&source=central&project=platform",
    );
    await flushPromises();

    const statusRegions = wrapper.findAll('[role="status"]');
    const chipRegion = statusRegions.find((region) =>
      region.text().includes("Needs approval"),
    );
    expect(chipRegion).toBeDefined();
    expect(chipRegion!.attributes("aria-live")).toBe("polite");
    expect(chipRegion!.text()).toContain("Source: central");
    expect(chipRegion!.text()).toContain("Project: platform");

    const chips = wrapper.findAllComponents({ name: "VChip" });
    const sourceChip = chips.find((chip) => chip.text().includes("Source: central"));
    expect(sourceChip).toBeDefined();
    const closeButton = sourceChip!.find(".v-chip__close");
    expect(closeButton.exists()).toBe(true);
    await closeButton.trigger("click");
    // `router.replace()` resolves over an unpredictable number of
    // microtask ticks in this test environment, so the URL assertion
    // below polls rather than assuming one or two `flushPromises()`
    // calls are enough; the chip row itself, re-read straight from
    // the live filter refs on every render, updates deterministically
    // and is asserted first.
    await flushPromises();

    const remainingChips = wrapper
      .findAllComponents({ name: "VChip" })
      .map((chip) => chip.text());
    expect(remainingChips.some((text) => text.includes("Source: central"))).toBe(
      false,
    );
    expect(remainingChips.some((text) => text === "Needs approval")).toBe(true);
    expect(remainingChips.some((text) => text.includes("Project: platform"))).toBe(
      true,
    );

    for (let attempt = 0; attempt < 10; attempt += 1) {
      if (router.currentRoute.value.query.source === undefined) {
        break;
      }
      await flushPromises();
    }
    expect(router.currentRoute.value.query.source).toBeUndefined();
    expect(router.currentRoute.value.query.needs_approval).toBe("true");
    expect(router.currentRoute.value.query.project).toBe("platform");
  });

  it("hides the active-filter row's 'Clear filters' when only the " +
    "free-text query is set -- no filter chip exists for it, so the " +
    "button must not appear just because something is set (P11-R-05)",
  async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/?q=nonexistent");
    await flushPromises();

    const statusRegions = wrapper.findAll('[role="status"]');
    const chipRegion = statusRegions.find((region) => region.text() === "");
    expect(chipRegion).toBeDefined();
    expect(
      wrapper.findAll("button").some((btn) => btn.text() === "Clear filters"),
    ).toBe(false);
  });

  it("clears only the active filters, keeping the free-text query " +
    "and the sort order, and the button sits outside the live " +
    "region (P11-R-05)",
  async () => {
    searchRecords.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
    getFacets.mockResolvedValue(emptyFacets);

    const { wrapper, router } = await mountSearchView(
      "/?q=postgres&sort=recent&needs_approval=true&source=central",
    );
    await flushPromises();

    const statusRegions = wrapper.findAll('[role="status"]');
    const chipRegion = statusRegions.find((region) =>
      region.text().includes("Needs approval"),
    );
    expect(chipRegion).toBeDefined();

    const clearButton = wrapper
      .findAll("button")
      .find((btn) => btn.text() === "Clear filters");
    expect(clearButton).toBeDefined();
    // A sibling of, not a descendant of, the chip row's own
    // `role="status"` node -- an all-filters clear is a persistent
    // action beside the live region, not content it announces.
    expect(chipRegion!.element.contains(clearButton!.element)).toBe(false);

    await clearButton!.trigger("click");
    await flushPromises();

    // `router.replace()` resolves over an unpredictable number of
    // microtask ticks in this test environment (see the chip-close
    // test above), so poll -- interleaving a real macrotask tick, not
    // just microtask-draining `flushPromises()` calls, since this
    // navigation (clearing four filters at once) takes more hops to
    // settle than a single-filter clear does.
    for (let attempt = 0; attempt < 50; attempt += 1) {
      if (router.currentRoute.value.query.needs_approval === undefined) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 0));
      await flushPromises();
    }

    expect(router.currentRoute.value.query.q).toBe("postgres");
    expect(router.currentRoute.value.query.sort).toBe("recent");
    expect(router.currentRoute.value.query.needs_approval).toBeUndefined();
    expect(router.currentRoute.value.query.source).toBeUndefined();
  });

  it("switches the default sort to Relevance once a query is typed " +
    "from the landing page, with no explicit choice made, and keeps " +
    "it out of the URL (P11-R-02)",
  async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper, router } = await mountSearchView("/");
    await flushPromises();

    const sortSelect = () =>
      wrapper
        .findAllComponents({ name: "VSelect" })
        .find((select) => select.props("label") === "Sort by");
    expect(sortSelect()!.props("modelValue")).toBe("title");

    const input = wrapper.find(
      'input[placeholder="Search by title, UUID, project, or path"]',
    );
    await input.setValue("postgres");
    // The real debounce delay (300ms default): the whole point of
    // this test is the reactive *getter* re-evaluating once the
    // debounce actually commits `q` to the URL, not a timer mock
    // standing in for it. Poll past it rather than a single fixed
    // wait, which is unreliable under full-suite load.
    for (let attempt = 0; attempt < 50; attempt += 1) {
      if (router.currentRoute.value.query.q === "postgres") {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 50));
      await flushPromises();
    }

    expect(router.currentRoute.value.query.q).toBe("postgres");
    expect(router.currentRoute.value.query.sort).toBeUndefined();
    expect(sortSelect()!.props("modelValue")).toBe("relevance");
  });

  it("shows no active-filter chip for the free-text query or the sort order", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const { wrapper } = await mountSearchView("/?q=postgres&sort=recent");
    await flushPromises();

    const chips = wrapper.findAllComponents({ name: "VChip" });
    expect(chips.some((chip) => chip.text().includes("postgres"))).toBe(false);
    expect(chips.some((chip) => chip.text().toLowerCase().includes("recent"))).toBe(
      false,
    );
  });

  it("mentions the active-filter count in the result line, with a " +
    "direct sentence for needs-approval alone that still keeps the " +
    "page range (S-04, P11-R-21)", async () => {
    searchRecords.mockResolvedValue({
      items: [],
      total: 14,
      page: 1,
      page_size: 20,
    });

    const { wrapper } = await mountSearchView("/?needs_approval=true");
    await flushPromises();

    expect(wrapper.text()).toContain(
      "Showing 1–14 of 14 records that need approval.",
    );
  });

  it("mentions a plain filter count in the result line for other filter combinations", async () => {
    searchRecords.mockResolvedValue({
      items: [],
      total: 3,
      page: 1,
      page_size: 20,
    });

    const { wrapper } = await mountSearchView("/?source=central&project=platform");
    await flushPromises();

    expect(wrapper.text()).toContain("Showing 1–3 of 3 records.");
    expect(wrapper.text()).toContain("2 filters active.");
  });

  it("offers 'Relevance' in the sort select only when a query is set (S-08)", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    const withoutQuery = await mountSearchView("/");
    const selectWithoutQuery = withoutQuery.wrapper
      .findAllComponents({ name: "VSelect" })
      .find((select) => select.props("label") === "Sort by");
    const itemTitlesWithoutQuery = (
      selectWithoutQuery!.props("items") as { title: string }[]
    ).map((item) => item.title);
    expect(itemTitlesWithoutQuery).toEqual(["Title A–Z", "Recently changed"]);

    const withQuery = await mountSearchView("/?q=postgres");
    const selectWithQuery = withQuery.wrapper
      .findAllComponents({ name: "VSelect" })
      .find((select) => select.props("label") === "Sort by");
    const itemTitlesWithQuery = (
      selectWithQuery!.props("items") as { title: string }[]
    ).map((item) => item.title);
    expect(itemTitlesWithQuery).toEqual([
      "Relevance",
      "Title A–Z",
      "Recently changed",
    ]);
  });

  it("keeps a non-default sort in the URL and sends it to the API", async () => {
    const page: SearchPage = { items: [], total: 0, page: 1, page_size: 20 };
    searchRecords.mockResolvedValue(page);

    await mountSearchView("/?q=postgres&sort=recent");
    await flushPromises();

    expect(searchRecords).toHaveBeenCalledWith(
      expect.objectContaining({ sort: "recent" }),
    );
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
