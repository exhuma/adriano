/**
 * Ensure the fetch-based API client shapes errors, sends the session
 * cookie (same-origin credentials) and the CSRF header on unsafe
 * methods only, never sends a bearer token, and invokes the 401
 * handler.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  api,
  ApiError,
  setAuthSuccessHandler,
  setUnauthorizedHandler,
} from "@/api";

describe("api client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
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

  /** Install a fetch mock answering 200 and return it. */
  function mockFetch(status = 200): ReturnType<typeof vi.fn> {
    const fetchMock = vi
      .fn()
      .mockImplementation(
        async () => new Response(JSON.stringify({}), { status }),
      );
    globalThis.fetch = fetchMock;
    return fetchMock;
  }

  function lastInit(fetchMock: ReturnType<typeof vi.fn>): RequestInit {
    return (fetchMock.mock.calls.at(-1) as [string, RequestInit])[1];
  }

  it("sends the session cookie with same-origin credentials", async () => {
    const fetchMock = mockFetch();

    await api.get("/api/v1/records");

    expect(lastInit(fetchMock).credentials).toBe("same-origin");
  });

  it("never sends an Authorization header", async () => {
    const fetchMock = mockFetch();

    await api.get("/api/v1/records");
    await api.post("/api/v1/records", {});

    for (const [, init] of fetchMock.mock.calls as [string, RequestInit][]) {
      const headers = init.headers as Record<string, string>;
      expect(headers.Authorization).toBeUndefined();
    }
  });

  it("does not send the CSRF header on GET", async () => {
    const fetchMock = mockFetch();

    await api.get("/api/v1/records");

    const headers = lastInit(fetchMock).headers as Record<string, string>;
    expect(headers["X-Adriano-CSRF"]).toBeUndefined();
  });

  it.each([
    ["POST", () => api.post("/x", {})],
    ["PUT", () => api.put("/x", {})],
    ["PATCH", () => api.patch("/x", {})],
    ["DELETE", () => api.delete("/x")],
  ])("sends the CSRF header on %s", async (method, call) => {
    const fetchMock = mockFetch();

    await call();

    const init = lastInit(fetchMock);
    const headers = init.headers as Record<string, string>;
    expect(init.method).toBe(method);
    expect(headers["X-Adriano-CSRF"]).toBe("1");
  });

  it("sends the CSRF header on a POST without a body", async () => {
    const fetchMock = mockFetch();

    await api.post("/auth/logout");

    const headers = lastInit(fetchMock).headers as Record<string, string>;
    expect(headers["X-Adriano-CSRF"]).toBe("1");
    expect(headers["Content-Type"]).toBeUndefined();
  });

  it("surfaces a 403 csrf_failed as a plain error without redirecting", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ code: "csrf_failed" }), {
          status: 403,
        }),
      );

    await expect(api.post("/x", {})).rejects.toMatchObject({
      status: 403,
      data: { code: "csrf_failed" },
    });
    expect(handler).not.toHaveBeenCalled();
  });

  it("invokes the success handler after a 2xx response", async () => {
    const success = vi.fn();
    setAuthSuccessHandler(success);
    mockFetch();

    await api.get("/api/v1/me");

    expect(success).toHaveBeenCalledOnce();
  });

  it("skips both handlers when the request opts out of auth tracking", async () => {
    const success = vi.fn();
    const unauthorized = vi.fn();
    setAuthSuccessHandler(success);
    setUnauthorizedHandler(unauthorized);
    mockFetch();
    await api.get("/auth/session", { trackAuth: false });
    mockFetch(401);
    await expect(
      api.get("/auth/session", { trackAuth: false }),
    ).rejects.toBeInstanceOf(ApiError);

    expect(success).not.toHaveBeenCalled();
    expect(unauthorized).not.toHaveBeenCalled();
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
