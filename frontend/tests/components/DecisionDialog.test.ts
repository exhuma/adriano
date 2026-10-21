/**
 * Ensure the decide dialog never submits on Cancel/Escape, requires
 * an explicit confirmation to reject, caps the comment counter at
 * 2000 characters, has an accessible name naming the record, and shows the
 * digest short by default
 * with the exact value reachable behind a "Show full digest"
 * disclosure (R-12) so a reviewer can still verify it.
 *
 * `v-dialog` teleports its content to `document.body`, outside the
 * mounted wrapper's own element, so assertions on rendered content
 * query `document.body` directly (as `SourcesView.test.ts` already
 * does for the teleported snackbar) instead of `wrapper.find`.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import DecisionDialog from "@/components/DecisionDialog.vue";

const decide = vi.fn();

vi.mock("@/composables/useDecision", () => ({
  useDecision: () => ({ submitting: ref(false), decide }),
}));

const DIGEST = "sha256-v1:abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234567";

function button(text: string): HTMLButtonElement | undefined {
  return Array.from(document.body.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === text,
  );
}

/** A real `.click()` call, which (unlike dispatching a synthetic
 *  `MouseEvent`) respects a native `disabled` attribute -- the same
 *  as an actual pointer click. */
function click(element: HTMLButtonElement | HTMLInputElement | undefined): void {
  element!.click();
}

const RECORD_TITLE = "Adopt gRPC for internal APIs";

async function mountDialog(
  action: "accepted" | "rejected" = "accepted",
  recordKind: "decision" | "erratum" = "decision",
  recordTitle: string = RECORD_TITLE,
) {
  const wrapper = mount(DecisionDialog, {
    props: {
      modelValue: true,
      recordId: "11111111-1111-1111-1111-111111111111",
      action,
      recordKind,
      recordTitle,
      digest: DIGEST,
    },
    global: { plugins: [vuetify] },
    attachTo: document.body,
  });
  await flushPromises();
  return wrapper;
}

describe("DecisionDialog", () => {
  afterEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("shows the digest short by default, with a copy button", async () => {
    await mountDialog();
    expect(document.body.textContent).toContain("sha256-v1:abcdef012345");
    expect(
      document.body.querySelector('[aria-label="Copy digest to clipboard"]'),
    ).not.toBeNull();

    // The full digest exists in the DOM (`v-show`, not `v-if`) so its
    // text can animate open, but it must stay visually hidden until
    // the disclosure is toggled.
    const toggle = button("Show full digest")!;
    const disclosureId = toggle.getAttribute("aria-controls")!;
    const disclosure = document.getElementById(disclosureId)!;
    expect(disclosure.style.display).toBe("none");
  });

  it("reveals the exact digest behind 'Show full digest'", async () => {
    await mountDialog();
    const toggle = button("Show full digest")!;
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    click(toggle);
    await flushPromises();

    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(document.body.textContent).toContain(DIGEST);
    expect(button("Hide full digest")).toBeDefined();
  });

  it("has an accessible name that includes the record's title", async () => {
    const wrapper = await mountDialog("rejected", "decision", RECORD_TITLE);

    const dialog = document.body.querySelector('[role="dialog"]')!;
    const labelledBy = dialog.getAttribute("aria-labelledby")!;
    expect(labelledBy).toBeTruthy();
    const heading = document.getElementById(labelledBy)!;
    expect(heading.tagName).toBe("H2");
    expect(heading.textContent).toContain(RECORD_TITLE);
    expect(heading.textContent).toContain("Reject");
    expect(heading.className).toContain("text-title-large");
    wrapper.unmount();
  });

  it("never submits on Cancel", async () => {
    const wrapper = await mountDialog();
    click(button("Cancel"));
    await flushPromises();

    expect(decide).not.toHaveBeenCalled();
    expect(wrapper.emitted("update:modelValue")).toEqual([[false]]);
  });

  it("never submits on Escape", async () => {
    const wrapper = await mountDialog();
    const overlay = document.body.querySelector(".v-overlay__content")!;
    overlay.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    await flushPromises();

    expect(decide).not.toHaveBeenCalled();
    expect(wrapper.emitted("update:modelValue")).toEqual([[false]]);
  });

  it("disables Reject until the confirmation checkbox is checked", async () => {
    await mountDialog("rejected");
    expect(button("Reject")!.disabled).toBe(true);

    const checkbox = document.body.querySelector<HTMLInputElement>(
      'input[type="checkbox"]',
    )!;
    click(checkbox);
    await flushPromises();

    expect(button("Reject")!.disabled).toBe(false);
  });

  it("never submits a rejection without confirming", async () => {
    await mountDialog("rejected");
    click(button("Reject"));
    await flushPromises();

    expect(decide).not.toHaveBeenCalled();
  });

  it("caps the comment counter at 2000 characters", async () => {
    await mountDialog();
    const textarea = document.body.querySelector("textarea")!;
    expect(textarea.getAttribute("maxlength")).toBe("2000");
  });

  it("submits the accept decision bound to the exact digest", async () => {
    decide.mockResolvedValue({
      kind: "success",
      event: { id: "x", action: "accepted" },
    });
    await mountDialog("accepted");
    click(button("Accept"));
    await flushPromises();

    expect(decide).toHaveBeenCalledWith(
      "11111111-1111-1111-1111-111111111111",
      "accepted",
      DIGEST,
      "",
    );
  });

  it("names the record and uses erratum wording for an erratum", async () => {
    const title = "Erratum for Adopt gRPC for internal APIs";
    await mountDialog("accepted", "erratum", title);

    expect(document.body.textContent).toContain(`Verify “${title}”?`);
    expect(document.body.textContent).toContain("the exact erratum at digest");
    expect(button("Verify")).toBeDefined();
  });

  it("uses erratum wording for a rejection on an erratum", async () => {
    const title = "Erratum for Adopt gRPC for internal APIs";
    await mountDialog("rejected", "erratum", title);

    expect(document.body.textContent).toContain(`Reject “${title}”?`);
    expect(document.body.textContent).toContain(
      "I confirm I want to reject this erratum.",
    );
  });
});
