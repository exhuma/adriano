/**
 * Ensure the not-indexed client sends filters as query parameters,
 * drops empty ones, and passes an entry's location (which contains
 * slashes) as four query parameters, never as path segments.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { getNotIndexedEntry, listNotIndexed } from "@/api/notIndexed";

describe("not-indexed api", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  function mockFetch(): ReturnType<typeof vi.fn> {
    const fetchMock = vi
      .fn()
      .mockImplementation(
        async () => new Response(JSON.stringify({}), { status: 200 }),
      );
    globalThis.fetch = fetchMock;
    return fetchMock;
  }

  it("lists with only the filters that are set", async () => {
    const fetchMock = mockFetch();

    await listNotIndexed({
      source_id: "central",
      project: "",
      reason: "duplicate_uuid",
      origin: "push",
      page: 2,
    });

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/not-indexed?source_id=central&reason=duplicate_uuid&origin=push&page=2",
    );
  });

  it("lists without a query string when nothing is set", async () => {
    const fetchMock = mockFetch();

    await listNotIndexed();

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/not-indexed");
  });

  it("fetches an entry by its location as query parameters", async () => {
    const fetchMock = mockFetch();

    await getNotIndexedEntry({
      source_id: "central",
      project: "group/platform",
      path: "doc/adr/0001.md",
      ref: "feature/x",
    });

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/not-indexed/entry?source_id=central&project=group%2Fplatform" +
        "&path=doc%2Fadr%2F0001.md&ref=feature%2Fx",
    );
  });
});
