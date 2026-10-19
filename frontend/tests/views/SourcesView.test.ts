/**
 * Ensure "Poll all"/"Poll now" render only for callers with the
 * `operate` permission (otherwise a short explanation), that a
 * successful poll shows a snackbar and refreshes the status a few
 * times, and that poll/list errors (403/404/409) are shown with
 * actionable text.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api";
import vuetify from "@/plugins/vuetify";
import SourcesView from "@/views/SourcesView.vue";
import type { SourceOut } from "@/types/sources";

const listSources = vi.fn();
const pollAllSources = vi.fn();
const pollSource = vi.fn();
let canOperate = true;

vi.mock("@/api/sources", () => ({
  listSources: (...args: unknown[]) => listSources(...args),
  pollAllSources: (...args: unknown[]) => pollAllSources(...args),
  pollSource: (...args: unknown[]) => pollSource(...args),
}));

vi.mock("@/composables/useAuth", () => ({
  useAuth: () => ({ can: (permission: string) => permission === "operate" && canOperate }),
}));

const baseSource: SourceOut = {
  id: "central",
  type: "filesystem",
  intake: ["poll"],
  published_ref: "local",
  enabled: true,
  config_error: null,
  last_attempt_at: null,
  last_success_at: null,
  last_status: "never",
  last_error: null,
  stale: true,
};

async function mountView() {
  const wrapper = mount(SourcesView, {
    global: { plugins: [vuetify] },
    // The snackbar teleports its content to `document.body`; attach
    // there so its text is reachable via `document.body.textContent`.
    attachTo: document.body,
  });
  await flushPromises();
  return wrapper;
}

describe("SourcesView", () => {
  beforeEach(() => {
    canOperate = true;
    listSources.mockReset();
    pollAllSources.mockReset();
    pollSource.mockReset();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("shows Poll all and per-row Poll now for an operator", async () => {
    listSources.mockResolvedValue([baseSource]);
    const wrapper = await mountView();

    expect(wrapper.text()).toContain("Poll all");
    expect(wrapper.text()).toContain("Poll now");
    expect(wrapper.text()).not.toContain("Only operators can trigger polling");
  });

  it("hides poll controls and explains who can poll for a reader", async () => {
    canOperate = false;
    listSources.mockResolvedValue([baseSource]);
    const wrapper = await mountView();

    expect(wrapper.text()).not.toContain("Poll all");
    expect(wrapper.text()).not.toContain("Poll now");
    expect(wrapper.text()).toContain("Only operators can trigger polling");
  });

  it("shows a snackbar and refreshes status after a successful poll-all", async () => {
    listSources.mockResolvedValue([baseSource]);
    pollAllSources.mockResolvedValue({
      accepted: ["central"],
      message: "Poll started for 1 registration(s)",
    });
    const wrapper = await mountView();

    const pollAllButton = wrapper
      .findAll("button")
      .find((btn) => btn.text().includes("Poll all"));
    await pollAllButton!.trigger("click");
    await flushPromises();

    expect(document.body.textContent).toContain("Poll started for 1 registration(s)");
    expect(listSources).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(10000);
    await flushPromises();

    expect(listSources.mock.calls.length).toBeGreaterThan(1);
  });

  it("shows an actionable message for a 409 (not pollable)", async () => {
    listSources.mockResolvedValue([baseSource]);
    pollAllSources.mockRejectedValue(
      new ApiError(409, { detail: "nothing is pollable", code: "not_pollable" }),
    );
    const wrapper = await mountView();

    const pollAllButton = wrapper
      .findAll("button")
      .find((btn) => btn.text().includes("Poll all"));
    await pollAllButton!.trigger("click");
    await flushPromises();

    expect(document.body.textContent).toContain("nothing is pollable");
  });

  it("shows a friendly no-access message on a 403 from the list request", async () => {
    listSources.mockRejectedValue(
      new ApiError(403, {
        detail: "the 'read' permission is required; ask an administrator",
        code: "permission_required",
      }),
    );
    const wrapper = await mountView();

    expect(wrapper.text()).toContain("No access");
    expect(wrapper.text()).toContain("ask an administrator");
  });

  it("disables Poll now on a specific row while its poll is pending", async () => {
    listSources.mockResolvedValue([baseSource]);
    let resolvePoll: (value: { accepted: string[]; message: string }) => void = () => {};
    pollSource.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePoll = resolve;
        }),
    );
    const wrapper = await mountView();

    const pollNowButton = wrapper
      .findAll("button")
      .find((btn) => btn.text().includes("Poll now"));
    await pollNowButton!.trigger("click");
    await flushPromises();

    expect(pollNowButton!.attributes("disabled")).not.toBeUndefined();

    resolvePoll({ accepted: ["central"], message: "Poll started for central" });
    await flushPromises();
  });
});
