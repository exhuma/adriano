/**
 * Ensure the app shell shows the right top-level state: the sign-in
 * screen when signed out (never a dev-login entry point while the
 * build-time gate is off, which it is under the default test
 * environment), the blocking "auth not configured" screen on
 * `/healthz` `auth: "unconfigured"`, and the normal shell once
 * `/api/v1/me` resolves. Also covers the xs/sm app-bar layout: the
 * product name and the DEV LOGIN mode chip stay inline while
 * everything else collapses into `AppBarMenu` (module-ux-principles
 * "UI modes" + "Fitt's/Hick's law").
 */
import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import type { HealthPayload } from "@/types/health";
import type { MeOut } from "@/types/auth";

// `App.vue` reads the breakpoint via Vuetify's `useDisplay()`, which
// under jsdom always resolves against a real `window` size rather
// than anything a test can easily resize. Mock only `useDisplay` on
// the "vuetify" package entry (Vuetify's own internal components
// import it by relative path, not through this entry, so their
// behaviour is untouched) and drive it with a plain ref the small-
// screen tests below can flip.
const mdAndUpRef = ref(true);
vi.mock("vuetify", async (importOriginal) => {
  const actual = await importOriginal<typeof import("vuetify")>();
  return { ...actual, useDisplay: () => ({ mdAndUp: mdAndUpRef }) };
});

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

async function mountApp(
  // The app bar's menu teleports its content to `document.body`
  // (Vuetify `v-menu`/`v-overlay`), and focus returns to a real DOM
  // node on Escape -- both only observable once attached.
  attachTo?: Element,
): Promise<{ wrapper: ReturnType<typeof mount>; router: Router }> {
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
  const wrapper = mount(App, {
    global: { plugins: [router, vuetify] },
    ...(attachTo ? { attachTo } : {}),
  });
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
    mdAndUpRef.value = true;
    signInWithOidc.mockReset();
    signOut.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
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

  describe("small-screen app bar (xs/sm)", () => {
    const alice: MeOut = {
      issuer: "adriano-dev",
      subject: "alice",
      display: "Alice",
      email: null,
      roles: ["admin"],
      permissions: ["read", "operate"],
      reviewer: { eligible: false, reason: "n/a" },
    };

    beforeEach(() => {
      mdAndUpRef.value = false;
    });

    it("does not render the 'Open menu' button at md and up (unchanged layout)", async () => {
      mdAndUpRef.value = true;
      meRef.value = alice;
      const { wrapper } = await mountApp();

      expect(wrapper.find('[aria-label="Open menu"]').exists()).toBe(false);
      expect(wrapper.text()).toContain("Sign out");
    });

    it("keeps the product name and a shortened DEV chip visible, collapsing the rest behind 'Open menu'", async () => {
      authModeRef.value = "dev";
      meRef.value = alice;
      const { wrapper } = await mountApp(document.body);

      expect(wrapper.text()).toContain("adriano");
      expect(wrapper.text()).toContain("DEV");
      expect(wrapper.text()).not.toContain("DEV LOGIN");
      expect(wrapper.text()).not.toContain("Catalog");
      expect(wrapper.text()).not.toContain("Sign out");

      const devChip = document.querySelector(".v-chip");
      expect(devChip?.getAttribute("aria-label")).toContain("DEV LOGIN");

      expect(
        document.querySelector('button[aria-label="Open menu"]'),
      ).not.toBeNull();
    });

    it("opens to reveal Catalog/Sources, backend status, the configuration warning, and the signed-in user's name/Sign out", async () => {
      healthPayload.value = {
        status: "ok",
        database: "ok",
        auth: "dev",
        rbac: "configured",
        config: "invalid",
      };
      meRef.value = alice;
      await mountApp(document.body);

      const menuButton = document.querySelector(
        'button[aria-label="Open menu"]',
      ) as HTMLButtonElement;
      menuButton.click();
      await flushPromises();

      expect(document.body.textContent).toContain("Catalog");
      expect(document.body.textContent).toContain("Sources");
      expect(document.body.textContent).toContain("Backend online");
      expect(document.body.textContent).toContain("Configuration issue");
      expect(document.body.textContent).toContain("Alice");
      expect(document.body.textContent).toContain("Sign out");
    });

    it("closes on Escape and returns focus to the 'Open menu' button", async () => {
      meRef.value = alice;
      await mountApp(document.body);

      const menuButton = document.querySelector(
        'button[aria-label="Open menu"]',
      ) as HTMLButtonElement;
      // Focus the button first, as a keyboard user would (Tab, then
      // Enter/Space) -- a plain `.click()` in jsdom does not move
      // focus, which Vuetify relies on to know focus should return
      // here once the menu closes.
      menuButton.focus();
      menuButton.click();
      await flushPromises();
      expect(document.querySelector(".v-overlay--active")).not.toBeNull();

      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      await flushPromises();

      expect(document.querySelector(".v-overlay--active")).toBeNull();
      expect(document.activeElement).toBe(menuButton);
    });
  });
});
