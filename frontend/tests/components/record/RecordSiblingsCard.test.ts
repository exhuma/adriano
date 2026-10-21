/**
 * Ensure the "Other revisions" card shows each sibling's own approval
 * chip, and the neutral "Blocked" status (not "Pending approval")
 * for a sibling whose content cannot be decided (R-02).
 */
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordSiblingsCard from "@/components/record/RecordSiblingsCard.vue";
import type { SiblingOut } from "@/types/records";

function sibling(overrides: Partial<SiblingOut> = {}): SiblingOut {
  return {
    id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
    kind: "candidate",
    source_id: "central",
    project: "platform",
    path: "doc/decisions/2024-12-24-use-postgres.md",
    ref: "feature/x",
    digest: "sha256-v1:abc",
    title: "Use PostgreSQL",
    decision_date: "2024-12-24",
    decision_date_inferred: false,
    approval_state: "pending",
    approvable: true,
    ...overrides,
  };
}

async function mountCard(siblings: SiblingOut[]) {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  return mount(RecordSiblingsCard, {
    props: { siblings },
    global: { plugins: [router, vuetify] },
  });
}

describe("RecordSiblingsCard", () => {
  it("shows an approvable sibling's own approval state", async () => {
    const wrapper = await mountCard([sibling()]);

    expect(wrapper.text()).toContain("Pending approval");
    expect(wrapper.text()).not.toContain("Blocked");
  });

  it("shows 'Blocked' for a sibling that cannot be decided", async () => {
    const wrapper = await mountCard([sibling({ approvable: false })]);

    expect(wrapper.text()).toContain("Blocked");
    expect(wrapper.text()).not.toContain("Pending approval");
  });
});
