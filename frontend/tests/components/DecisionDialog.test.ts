/**
 * Ensure the decide dialog never submits on Cancel/Escape, requires
 * an explicit confirmation to reject, caps the comment counter at
 * 2000 characters, and always shows the exact digest being decided
 * (not a shortened one) so a reviewer can verify it.
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

async function mountDialog(
  action: "accepted" | "rejected" = "accepted",
  recordKind: "decision" | "erratum" = "decision",
) {
  const wrapper = mount(DecisionDialog, {
    props: {
      modelValue: true,
      recordId: "11111111-1111-1111-1111-111111111111",
      action,
      recordKind,
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

  it("shows the exact digest, not a shortened one", async () => {
    await mountDialog();
    expect(document.body.textContent).toContain(DIGEST);
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

  it("uses erratum wording for the title and confirm button on an erratum", async () => {
    await mountDialog("accepted", "erratum");

    expect(document.body.textContent).toContain("Verify this erratum?");
    expect(button("Verify")).toBeDefined();
  });

  it("uses erratum wording for a rejection on an erratum", async () => {
    await mountDialog("rejected", "erratum");

    expect(document.body.textContent).toContain("Reject this erratum?");
    expect(document.body.textContent).toContain(
      "I confirm I want to reject this erratum.",
    );
  });
});
