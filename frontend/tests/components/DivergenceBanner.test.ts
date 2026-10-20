/**
 * Ensure `DivergenceBanner` uses neutral wording that works for both
 * a decision and an erratum, and picks the right competing-candidate
 * chip vocabulary for each.
 */
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import DivergenceBanner from "@/components/DivergenceBanner.vue";
import type { CompetingCandidateOut } from "@/types/approval";

function candidate(): CompetingCandidateOut {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    ref: "feature-x",
    path: "doc/decisions/2025-05-01-fix.md",
    digest: "sha256-v1:abc",
    approval_state: "pending",
  };
}

async function mountBanner(recordKind: "decision" | "erratum") {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/records/:id", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  const wrapper = mount(DivergenceBanner, {
    props: {
      divergence: null,
      competingCandidates: [candidate()],
      recordKind,
    },
    global: { plugins: [router, vuetify] },
  });
  return wrapper;
}

describe("DivergenceBanner", () => {
  it("never calls the competing identity 'this same decision' (neutral wording works for errata too)", async () => {
    const wrapper = await mountBanner("erratum");

    expect(wrapper.text()).not.toContain("this same decision");
    expect(wrapper.text()).toContain("this same record");
  });

  it("uses the erratum chip vocabulary for a competing candidate on an erratum page", async () => {
    const wrapper = await mountBanner("erratum");

    expect(wrapper.text()).toContain("Reported — Proposed (branch feature-x)");
  });

  it("uses the plain decision chip vocabulary for a competing candidate on a decision page", async () => {
    const wrapper = await mountBanner("decision");

    expect(wrapper.text()).toContain("Pending approval");
    expect(wrapper.text()).not.toContain("Reported");
  });
});
