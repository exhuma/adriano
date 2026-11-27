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

  it("reports OIDC as disabled when the runtime config does not say otherwise", async () => {
    const { oidcEnabled } = await import("@/config");

    expect(oidcEnabled).toBe(false);
  });

  it("reports OIDC as enabled when the backend's runtime config says so", async () => {
    window.__APP_CONFIG__ = { apiBaseUrl: "", oidcEnabled: true };
    const { oidcEnabled } = await import("@/config");

    expect(oidcEnabled).toBe(true);
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
