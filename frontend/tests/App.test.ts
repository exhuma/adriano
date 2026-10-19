/**
 * Ensure the app shell shows the right top-level state: the sign-in
 * screen when signed out (never a dev-login entry point while the
 * build-time gate is off, which it is under the default test
 * environment), the blocking "auth not configured" screen on
 * `/healthz` `auth: "unconfigured"`, and the normal shell once
 * `/api/v1/me` resolves.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import type { HealthPayload } from "@/types/health";
import type { MeOut } from "@/types/auth";

// Real `ref()`s, not plain objects: `App.vue`'s template relies on
// Vue's automatic ref-unwrapping, which only applies to actual
// `Ref` instances -- a plain `{ value: ... }` object would be
// (incorrectly) truthy in a `v-if` by itself, regardless of its
// `.value`.
const healthState = ref<"checking" | "ok" | "degraded" | "error">("ok");
const healthPayload = ref<HealthPayload | null>(null);
const meRef = ref<MeOut | null>(null);
const meErrorRef = ref<{ kind: string; detail: string } | null>(null);
const authModeRef = ref<"oidc" | "dev" | null>(null);
const authErrorRef = ref<string | null>(null);

const signInWithOidc = vi.fn();
const signOut = vi.fn();
const initAuth = vi.fn();

vi.mock("@/composables/useHealth", () => ({
  useHealth: () => ({
    state: healthState,
    payload: healthPayload,
    check: vi.fn(),
  }),
}));

vi.mock("@/composables/useAuth", () => ({
  useAuth: () => ({
    me: meRef,
    meError: meErrorRef,
    authMode: authModeRef,
    authError: authErrorRef,
    oidcConfigured: true,
    initAuth,
    signInWithOidc,
    signOut,
  }),
}));

async function mountApp(): Promise<{ wrapper: ReturnType<typeof mount>; router: Router }> {
  const App = (await import("@/App.vue")).default;
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "search", component: { template: "<div>catalog</div>" } },
      { path: "/sources", name: "sources", component: { template: "<div>sources</div>" } },
      { path: "/auth/callback", name: "auth-callback", component: { template: "<div>callback</div>" } },
    ],
  });
  await router.push("/");
  await router.isReady();
  const wrapper = mount(App, { global: { plugins: [router, vuetify] } });
  await flushPromises();
  return { wrapper, router };
}

describe("App", () => {
  beforeEach(() => {
    healthState.value = "ok";
    healthPayload.value = { status: "ok", database: "ok", auth: "dev", rbac: "configured" };
    meRef.value = null;
    meErrorRef.value = null;
    authModeRef.value = null;
    authErrorRef.value = null;
    signInWithOidc.mockReset();
    signOut.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the sign-in screen when signed out, with no dev-login entry point", async () => {
    const { wrapper } = await mountApp();

    expect(wrapper.text()).toContain("Sign in to browse the decision catalog");
    // The build-time dev-auth gate is off under the default test
    // environment (VITE_DEV_AUTH is unset), so no dev-login button
    // or dialog markup is rendered at all.
    expect(wrapper.text()).not.toContain("Dev sign-in");
    expect(wrapper.findComponent({ name: "DevLoginDialog" }).exists()).toBe(false);
  });

  it("shows a blocking screen when /healthz reports auth is unconfigured", async () => {
    healthPayload.value = { status: "ok", database: "ok", auth: "unconfigured", rbac: "empty" };
    const { wrapper } = await mountApp();

    expect(wrapper.text()).toContain("Authentication is not configured");
    expect(wrapper.text()).not.toContain("Sign in to browse the decision catalog");
  });

  it("shows the normal shell once signed in", async () => {
    meRef.value = {
      issuer: "adriano-dev",
      subject: "alice",
      display: "Alice",
      email: null,
      roles: ["admin"],
      permissions: ["read", "operate"],
      reviewer: { eligible: false, reason: "n/a" },
    };
    const { wrapper } = await mountApp();

    expect(wrapper.text()).toContain("Alice");
    expect(wrapper.text()).toContain("Sign out");
    expect(wrapper.text()).not.toContain("Sign in to browse the decision catalog");
  });

  it("shows a blocking dialog instead of looping when the re-auth guard fails", async () => {
    authErrorRef.value = "Your session could not be authenticated.";
    const { wrapper } = await mountApp();

    expect(wrapper.text()).toContain("Sign-in could not be completed");
    expect(wrapper.text()).toContain("Sign out and try again");
  });
});
