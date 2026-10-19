/**
 * Ensure the fetch-based API client shapes errors, attaches bearer
 * tokens via the TokenProvider seam, and invokes the 401 handler.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  api,
  ApiError,
  setAuthSuccessHandler,
  setTokenProvider,
  setUnauthorizedHandler,
} from "@/api";

describe("api client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setTokenProvider({ getToken: () => null });
    setUnauthorizedHandler(() => {});
    setAuthSuccessHandler(() => {});
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("resolves with the parsed JSON body on a 2xx response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );

    const result = await api.get<{ status: string }>("/healthz");

    expect(result).toEqual({ status: "ok" });
  });

  it("throws an ApiError carrying the status and body on failure", async () => {
    globalThis.fetch = vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify({ detail: "nope" }), { status: 422 }),
    );

    await expect(api.get("/api/v1/records")).rejects.toMatchObject({
      status: 422,
      data: { detail: "nope" },
    });
    await expect(api.get("/api/v1/records")).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it("attaches an Authorization header from the active TokenProvider", async () => {
    setTokenProvider({ getToken: () => "test-token" });
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    globalThis.fetch = fetchMock;

    await api.get("/api/v1/records");

    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = requestInit.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("omits the Authorization header when no token is available", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    globalThis.fetch = fetchMock;

    await api.get("/api/v1/records");

    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = requestInit.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("invokes the unauthorized handler on a 401 response", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 401 }));

    await expect(api.get("/api/v1/me")).rejects.toBeInstanceOf(ApiError);
    expect(handler).toHaveBeenCalledOnce();
  });
});
