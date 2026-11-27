/**
 * Ensure the not-indexed page lists entries with their location,
 * origin, plain-language reasons and first/last seen times; links a
 * duplicate to the ADR holding the UUID and an entry to its file in
 * the repository; filters and paginates through the URL; says the
 * entries clear on their own (and offers no dismiss action); and
 * distinguishes "nothing is not indexed" from "no match".
 */
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api";
import vuetify from "@/plugins/vuetify";
import type { NotIndexedItem, NotIndexedPage } from "@/types/notIndexed";
import NotIndexedView from "@/views/NotIndexedView.vue";

const listNotIndexed = vi.fn();
const listSources = vi.fn();

vi.mock("@/api/notIndexed", () => ({
  listNotIndexed: (...args: unknown[]) => listNotIndexed(...args),
}));
vi.mock("@/api/sources", () => ({
  listSources: (...args: unknown[]) => listSources(...args),
}));

const HOLDER = "11111111-1111-1111-1111-111111111111";

function item(overrides: Partial<NotIndexedItem> = {}): NotIndexedItem {
  return {
    source_id: "central",
    project: "platform",
    path: "doc/decisions/0001-broken.md",
    ref: "main",
    origin: "poll",
    reasons: [
      { severity: "error", code: "missing_uuid", message: "no uuid in the front matter" },
    ],
    holder_uuid: null,
    source_url: "https://git.example.com/platform/-/blob/main/doc/decisions/0001-broken.md",
    first_seen_at: "2026-01-01T00:00:00Z",
    last_seen_at: "2026-01-02T00:00:00Z",
    has_content: true,
    ...overrides,
  };
}

function page(items: NotIndexedItem[], total = items.length): NotIndexedPage {
  return { items, total, page: 1, page_size: 20 };
}

async function mountView(initialPath = "/not-indexed"): Promise<{
  router: Router;
  wrapper: ReturnType<typeof mount>;
}> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/not-indexed", component: NotIndexedView },
      { path: "/not-indexed/entry", component: { template: "<div />" } },
      { path: "/records/:uuid", component: { template: "<div />" } },
    ],
  });
  await router.push(initialPath);
  await router.isReady();
  const wrapper = mount(NotIndexedView, {
    global: { plugins: [router, vuetify] },
  });
  await flushPromises();
  return { router, wrapper };
}

describe("NotIndexedView", () => {
  beforeEach(() => {
    listSources.mockResolvedValue([{ id: "central" }, { id: "other" }]);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("shows each entry's location, origin, reason in plain words and seen times", async () => {
    listNotIndexed.mockResolvedValue(page([item()]));

    const { wrapper } = await mountView();

    expect(wrapper.text()).toContain("doc/decisions/0001-broken.md");
    expect(wrapper.text()).toContain("central / platform @ main");
    expect(wrapper.text()).toContain("Polled");
    expect(wrapper.text()).toContain("The record has no UUID — no uuid in the front matter");
    expect(wrapper.text()).toContain("First seen");
    expect(wrapper.text()).toContain("last seen");
    expect(wrapper.text()).toContain("Showing 1–1 of 1 document.");
  });

  it("links an entry to its file in the repository and to its detail", async () => {
    listNotIndexed.mockResolvedValue(page([item({ origin: "push", ref: "feature/x" })]));

    const { wrapper } = await mountView();

    const file = wrapper.find("a[href^='https://git.example.com']");
    expect(file.text()).toBe("Open file in repository");
    expect(file.attributes("target")).toBe("_blank");
    expect(file.attributes("rel")).toContain("noopener");
    expect(wrapper.text()).toContain("Pushed");
    const detail = wrapper.find("a[href^='/not-indexed/entry']");
    expect(detail.attributes("href")).toBe(
      "/not-indexed/entry?source_id=central&project=platform" +
        "&path=doc/decisions/0001-broken.md&ref=feature/x",
    );
  });

  it("shows no repository link when the file's URL is unknown", async () => {
    listNotIndexed.mockResolvedValue(page([item({ source_url: null })]));

    const { wrapper } = await mountView();

    expect(wrapper.text()).not.toContain("Open file in repository");
  });

  it("links a duplicate to the ADR that holds its UUID", async () => {
    listNotIndexed.mockResolvedValue(
      page([
        item({
          reasons: [
            { severity: "error", code: "duplicate_uuid", message: "UUID already held" },
          ],
          holder_uuid: HOLDER,
        }),
        item({ path: "doc/other.md" }),
      ]),
    );

    const { wrapper } = await mountView();

    const holderLinks = wrapper.findAll(`a[href='/records/${HOLDER}']`);
    expect(holderLinks.length).toBe(1);
    expect(holderLinks[0].text()).toBe("View the ADR that holds this UUID");
    expect(wrapper.text()).toContain("Another file already holds this UUID");
  });

  it("says entries clear on their own and offers no dismiss action", async () => {
    listNotIndexed.mockResolvedValue(page([item()]));

    const { wrapper } = await mountView();

    expect(wrapper.text()).toContain("disappears on its own");
    const buttons = wrapper.findAll("button, a").map((b) => b.text().toLowerCase());
    expect(buttons.some((t) => /dismiss|delete|remove|ignore/.test(t))).toBe(false);
  });

  it("requests the filters and page from the URL", async () => {
    listNotIndexed.mockResolvedValue(page([item()], 45));

    await mountView(
      "/not-indexed?source=central&project=platform&reason=duplicate_uuid&origin=push&page=2",
    );

    expect(listNotIndexed).toHaveBeenCalledWith({
      source_id: "central",
      project: "platform",
      reason: "duplicate_uuid",
      origin: "push",
      page: 2,
      page_size: 20,
    });
  });

  it("requests the unfiltered first page without a query", async () => {
    listNotIndexed.mockResolvedValue(page([item()]));

    await mountView();

    expect(listNotIndexed).toHaveBeenCalledWith({
      source_id: undefined,
      project: undefined,
      reason: undefined,
      origin: undefined,
      page: 1,
      page_size: 20,
    });
  });

  it("refetches with the new filter when the URL changes", async () => {
    listNotIndexed.mockResolvedValue(page([item()]));
    const { router } = await mountView();

    await router.replace({ query: { origin: "push" } });
    await flushPromises();

    expect(listNotIndexed).toHaveBeenLastCalledWith(
      expect.objectContaining({ origin: "push", page: 1 }),
    );
  });

  it("paginates when there are more entries than one page", async () => {
    listNotIndexed.mockResolvedValue(page([item()], 45));

    const { wrapper } = await mountView();

    expect(wrapper.find("nav[aria-label='Not-indexed list pages']").exists()).toBe(true);
  });

  it("shows the empty state when nothing is not indexed", async () => {
    listNotIndexed.mockResolvedValue(page([]));

    const { wrapper } = await mountView();

    expect(wrapper.text()).toContain("Every document is indexed");
    expect(wrapper.text()).not.toContain("Clear filters");
  });

  it("distinguishes 'no match' from 'nothing not indexed' when filters are set", async () => {
    listNotIndexed.mockResolvedValue(page([]));

    const { wrapper } = await mountView("/not-indexed?origin=push");

    expect(wrapper.text()).toContain("No entries match your filters");
    const clear = wrapper.findAll("button").find((b) => b.text() === "Clear filters");
    expect(clear).toBeDefined();
  });

  it("clears the filters from the URL", async () => {
    listNotIndexed.mockResolvedValue(page([]));
    const { router, wrapper } = await mountView("/not-indexed?origin=push");

    await wrapper.findAll("button").find((b) => b.text() === "Clear filters")!.trigger("click");
    await flushPromises();

    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({}));
  });

  it("shows a friendly message when the list cannot be loaded", async () => {
    listNotIndexed.mockRejectedValue(new ApiError(500, {}));

    const { wrapper } = await mountView();

    expect(wrapper.text()).toContain("Couldn't load the not-indexed list");
    expect(wrapper.text()).toContain("status 500");
  });
});
