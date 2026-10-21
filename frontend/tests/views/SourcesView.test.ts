/**
 * Ensure "Poll all"/"Poll now" render only for callers with the
 * `operate` permission (otherwise a short explanation), that a
 * successful poll shows a snackbar and refreshes the status a few
 * times, and that poll/list errors (403/404/409) are shown with
 * actionable text. Also covers the docs/ui-review O-01/O-02/O-03/O-04
 * fixes: one status chip per row with staleness as secondary text, a
 * default-size "Poll now", the problem/recovery sub-row, the
 * tooltip/screen-reader-accessible absolute dates, and the "Only
 * operators…" hint sitting below the table rather than above it.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api";
import StatusChip from "@/components/StatusChip.vue";
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
  config_error_code: null,
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

  it("renders a problems[] last_error as plain-language text, " +
    "keeping the raw message as Details", async () => {
    listSources.mockResolvedValue([
      {
        ...baseSource,
        last_status: "failed",
        last_error: {
          problems: [
            { code: "source_error", message: "fake source is down" },
            { code: "fetch_failed", message: "could not fetch a.md" },
          ],
        },
      },
    ]);
    const wrapper = await mountView();

    const items = wrapper.findAll("li");
    expect(items).toHaveLength(2);
    expect(items[0].text()).toContain("Couldn't reach the source");
    expect(items[0].text()).toContain("Details: fake source is down");
    expect(items[1].text()).toContain("Couldn't fetch a changed file");
    expect(items[1].text()).toContain("Details: could not fetch a.md");
    expect(wrapper.text()).not.toContain("{");
  });

  it("hides problem/recovery detail from a reader, keeping status " +
    "and dates", async () => {
    canOperate = false;
    listSources.mockResolvedValue([
      {
        ...baseSource,
        last_status: "failed",
        last_attempt_at: "2026-01-01T00:00:00Z",
        last_error: {
          problems: [{ code: "source_error", message: "fake source is down" }],
        },
      },
    ]);
    const wrapper = await mountView();

    expect(wrapper.text()).toContain("Failed");
    expect(wrapper.find("li").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("fake source is down");
    expect(wrapper.text()).not.toContain("Couldn't reach the source");
  });

  it("renders a source_error last_error shape as plain text", async () => {
    listSources.mockResolvedValue([
      {
        ...baseSource,
        last_status: "failed",
        last_error: { source_error: "connection refused" },
      },
    ]);
    const wrapper = await mountView();

    expect(wrapper.text()).toContain("connection refused");
    expect(wrapper.text()).not.toContain("{");
  });

  it("never renders raw JSON for an unrecognised last_error shape", async () => {
    listSources.mockResolvedValue([
      {
        ...baseSource,
        last_status: "failed",
        last_error: { weird: { nested: true } },
      },
    ]);
    const wrapper = await mountView();

    expect(wrapper.text()).toContain("See server logs (details unavailable).");
    expect(wrapper.text()).not.toContain("{");
    expect(wrapper.text()).not.toContain("weird");
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

  it("shows exactly one status chip per row, with staleness as " +
    "secondary text rather than a second chip (O-01)", async () => {
    listSources.mockResolvedValue([
      { ...baseSource, enabled: false, last_status: "disabled", stale: true },
    ]);
    const wrapper = await mountView();

    expect(wrapper.findAllComponents(StatusChip)).toHaveLength(1);
    const chipText = wrapper.findComponent(StatusChip).text();
    expect(chipText).toBe("Disabled");
    expect(chipText).not.toContain("stale");
    expect(wrapper.text()).toContain("Stale");
  });

  it("renders the problem/recovery detail as a full-width sub-row " +
    "under the failing source, not a same-row column (O-03)", async () => {
    listSources.mockResolvedValue([
      {
        ...baseSource,
        last_status: "failed",
        stale: false,
        last_error: {
          problems: [{ code: "source_error", message: "fake source is down" }],
        },
      },
    ]);
    const wrapper = await mountView();

    const rows = wrapper.findAll("tbody > tr");
    expect(rows.length).toBe(2);
    expect(rows[0].text()).not.toContain("fake source is down");
    expect(rows[1].text()).toContain("fake source is down");
    const subRowCell = rows[1].find("td");
    expect(subRowCell.attributes("colspan")).toBe("8");
  });

  it("labels a config error by its stable code for an operator, " +
    "keeping the raw text as Details (R-10)", async () => {
    listSources.mockResolvedValue([
      {
        ...baseSource,
        type: "gitlab",
        enabled: false,
        last_status: "disabled",
        config_error: "token_env: GitLab token env var GL_TOKEN is not set",
        config_error_code: "token_env_missing",
      },
    ]);
    const wrapper = await mountView();

    const rows = wrapper.findAll("tbody > tr");
    expect(rows).toHaveLength(2);
    expect(rows[1].text()).toContain(
      "The access token's environment variable is not set",
    );
    expect(rows[1].text()).toContain("Details: token_env: GitLab token");
  });

  it("hides a config error from a reader", async () => {
    canOperate = false;
    listSources.mockResolvedValue([
      {
        ...baseSource,
        enabled: false,
        last_status: "disabled",
        config_error: "token_env: GitLab token env var GL_TOKEN is not set",
        config_error_code: "token_env_missing",
      },
    ]);
    const wrapper = await mountView();

    expect(wrapper.text()).not.toContain("GL_TOKEN");
    expect(wrapper.text()).not.toContain("access token");
  });

  it("does not add a problem sub-row for a healthy source", async () => {
    listSources.mockResolvedValue([baseSource]);
    const wrapper = await mountView();

    expect(wrapper.findAll("tbody > tr")).toHaveLength(1);
  });

  it("shows the absolute date in a tooltip and to screen readers, " +
    "not as a second visible line (O-03)", async () => {
    listSources.mockResolvedValue([
      { ...baseSource, last_attempt_at: "2026-01-01T00:00:00Z" },
    ]);
    const wrapper = await mountView();

    const srOnly = wrapper.find(".d-sr-only");
    expect(srOnly.exists()).toBe(true);
    expect(srOnly.text()).toContain("2026");
    const tooltip = wrapper.findComponent({ name: "VTooltip" });
    expect(tooltip.exists()).toBe(true);
    expect(tooltip.props("text")).toContain("2026");
  });

  it("renders Poll now at the default size with the primary colour (O-02)", async () => {
    listSources.mockResolvedValue([baseSource]);
    const wrapper = await mountView();

    const pollNowButton = wrapper
      .findAllComponents({ name: "VBtn" })
      .find((btn) => btn.text().includes("Poll now"));
    expect(pollNowButton!.props("size")).toBe("default");
    expect(pollNowButton!.props("color")).toBe("primary");
  });

  it("shows the operator hint below the table, not above it (O-04)", async () => {
    canOperate = false;
    listSources.mockResolvedValue([baseSource]);
    const wrapper = await mountView();

    const html = wrapper.html();
    const tableIndex = html.indexOf("Registration");
    const hintIndex = html.indexOf("Only operators can trigger polling");
    expect(tableIndex).toBeGreaterThan(-1);
    expect(hintIndex).toBeGreaterThan(tableIndex);
  });
});
