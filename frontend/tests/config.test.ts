/**
 * Ensure runtime config (window.__APP_CONFIG__) takes precedence over
 * the build-time VITE_* fallback, and that the fallback alone still
 * works for local dev (module-runtime-config-spa).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

declare global {
  interface Window {
    __APP_CONFIG__?: { apiBaseUrl?: string };
  }
}

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
});
