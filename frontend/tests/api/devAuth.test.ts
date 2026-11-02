/**
 * Ensure the dev login posts the identity with the CSRF header and
 * same-origin credentials, and treats the 204 answer as success.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { createDevSession } from "@/api/devAuth";

describe("createDevSession", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("posts the identity to /auth/dev/login with the CSRF header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    globalThis.fetch = fetchMock;

    await createDevSession({ sub: "alice", roles: ["admin"] });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(url).toBe("/auth/dev/login");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(headers["X-Adriano-CSRF"]).toBe("1");
    expect(JSON.parse(init.body as string)).toEqual({
      sub: "alice",
      roles: ["admin"],
    });
  });
});
