/**
 * Ensure the entry page shows the rejected content read-only and
 * monospaced when it was stored, says so plainly when it was not,
 * words a 404 as "cleared on its own", and reads the location from
 * the query string (slashes intact).
 */
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api";
import vuetify from "@/plugins/vuetify";
import type { NotIndexedDetail } from "@/types/notIndexed";
import NotIndexedEntryView from "@/views/NotIndexedEntryView.vue";

const getNotIndexedEntry = vi.fn();

vi.mock("@/api/notIndexed", () => ({
  getNotIndexedEntry: (...args: unknown[]) => getNotIndexedEntry(...args),
}));

const HOLDER = "11111111-1111-1111-1111-111111111111";
const QUERY =
  "?source_id=central&project=group%2Fplatform" +
  "&path=doc%2Fadr%2F0001.md&ref=feature%2Fx";

function detail(overrides: Partial<NotIndexedDetail> = {}): NotIndexedDetail {
  return {
    source_id: "central",
    project: "group/platform",
    path: "doc/adr/0001.md",
    ref: "feature/x",
    origin: "push",
    reasons: [
      { severity: "error", code: "duplicate_uuid", message: "UUID already held" },
    ],
    holder_uuid: HOLDER,
    source_url: "https://git.example.com/f.md",
    first_seen_at: "2026-01-01T00:00:00Z",
    last_seen_at: "2026-01-02T00:00:00Z",
    has_content: true,
    content: "---\nuuid: x\n---\n# Broken\n",
    ...overrides,
  };
}

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/not-indexed", component: { template: "<div />" } },
      { path: "/not-indexed/entry", component: NotIndexedEntryView },
      { path: "/records/:uuid", component: { template: "<div />" } },
    ],
  });
  await router.push(`/not-indexed/entry${QUERY}`);
  await router.isReady();
  const wrapper = mount(NotIndexedEntryView, {
    global: { plugins: [router, vuetify] },
  });
  await flushPromises();
  return wrapper;
}

describe("NotIndexedEntryView", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("loads the entry by the location in the query string", async () => {
    getNotIndexedEntry.mockResolvedValue(detail());

    await mountView();

    expect(getNotIndexedEntry).toHaveBeenCalledWith({
      source_id: "central",
      project: "group/platform",
      path: "doc/adr/0001.md",
      ref: "feature/x",
    });
  });

  it("shows the rejected content read-only, as preformatted text, with the reason and links", async () => {
    getNotIndexedEntry.mockResolvedValue(detail());

    const wrapper = await mountView();

    const pre = wrapper.find("pre");
    expect(pre.text()).toBe("---\nuuid: x\n---\n# Broken");
    expect(wrapper.find("textarea, input").exists()).toBe(false);
    expect(wrapper.text()).toContain("Another file already holds this UUID");
    expect(wrapper.find(`a[href='/records/${HOLDER}']`).exists()).toBe(true);
    expect(wrapper.find("a[href='https://git.example.com/f.md']").exists()).toBe(true);
    expect(wrapper.text()).toContain("disappears on its own");
    expect(wrapper.text()).toContain("Pushed");
  });

  it("says the content was not stored when there is none", async () => {
    getNotIndexedEntry.mockResolvedValue(
      detail({ content: null, has_content: false }),
    );

    const wrapper = await mountView();

    expect(wrapper.find("pre").exists()).toBe(false);
    expect(wrapper.text()).toContain("The content of this document was not stored");
  });

  it("words a 404 as the entry having cleared on its own", async () => {
    getNotIndexedEntry.mockRejectedValue(new ApiError(404, {}));

    const wrapper = await mountView();

    expect(wrapper.text()).toContain("This entry is gone");
    expect(wrapper.text()).toContain("cleared on its own");
  });

  it("links back to the list filtered to the entry's source", async () => {
    getNotIndexedEntry.mockResolvedValue(detail());

    const wrapper = await mountView();

    expect(wrapper.find("a[href='/not-indexed?source=central']").exists()).toBe(true);
  });

  it("shows a retryable error for other failures", async () => {
    getNotIndexedEntry.mockRejectedValue(new ApiError(500, {}));

    const wrapper = await mountView();

    expect(wrapper.text()).toContain("Couldn't load this entry");
  });
});
