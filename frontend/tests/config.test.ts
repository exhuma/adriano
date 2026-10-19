/**
 * Ensure runtime config (window.__APP_CONFIG__) takes precedence over
 * the build-time VITE_* fallback, and that the fallback alone still
 * works for local dev (module-runtime-config-spa).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// `Window.__APP_CONFIG__`'s type comes from `src/config.ts`'s own
// `declare global` (included in the same TS program as this test
// file via tsconfig.vitest.json); redeclaring it here with a
// narrower shape would conflict.

describe("config", () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.__APP_CONFIG__;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete window.__APP_CONFIG__;
  });

  it("falls back to an empty string when nothing is configured", async () => {
    const { apiBaseUrl } = await import("@/config");

    expect(apiBaseUrl).toBe("");
  });

  it("uses the VITE_* build-time fallback when the runtime global is absent", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://build-time.example");
    const { apiBaseUrl } = await import("@/config");

    expect(apiBaseUrl).toBe("https://build-time.example");
  });

  it("prefers the runtime global over the build-time fallback", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://build-time.example");
    window.__APP_CONFIG__ = { apiBaseUrl: "https://runtime.example" };
    const { apiBaseUrl } = await import("@/config");

    expect(apiBaseUrl).toBe("https://runtime.example");
  });

  it("reports OIDC as unconfigured when neither authority nor client id is set", async () => {
    const { oidcConfigured } = await import("@/config");

    expect(oidcConfigured).toBe(false);
  });

  it("reports OIDC as configured once both an authority and a client id are present", async () => {
    window.__APP_CONFIG__ = {
      oidcAuthority: "https://idp.example.com",
      oidcClientId: "adriano-spa",
    };
    const { oidcConfigured, oidcAuthority, oidcClientId } = await import("@/config");

    expect(oidcConfigured).toBe(true);
    expect(oidcAuthority).toBe("https://idp.example.com");
    expect(oidcClientId).toBe("adriano-spa");
  });

  it("defaults the OIDC scope when unset", async () => {
    const { oidcScope } = await import("@/config");

    expect(oidcScope).toBe("openid profile email");
  });

  it("the dev-auth gate is never read from runtime config (security boundary)", async () => {
    // `RuntimeConfig` (the type of `window.__APP_CONFIG__`) has no
    // `devAuth`-shaped key at all -- this asserts there is nothing
    // for a runtime-injected object to switch on, not merely that a
    // particular value was ignored.
    const path = await import("node:path");
    const fs = await import("node:fs/promises");
    const configSource = await fs.readFile(
      path.join(process.cwd(), "src", "config.ts"),
      "utf-8",
    );
    const runtimeConfigBlock = configSource.slice(
      configSource.indexOf("interface RuntimeConfig"),
      configSource.indexOf("declare global"),
    );
    expect(runtimeConfigBlock).not.toMatch(/devAuth/i);
  });
});
