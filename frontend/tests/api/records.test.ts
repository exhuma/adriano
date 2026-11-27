/**
 * Ensure the records API client addresses an ADR by UUID, a
 * candidate by a path remainder that keeps slashes, and passes a
 * row's ref to the diff and decision routes as a query parameter.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { postDecision } from "@/api/decisions";
import { getRecord, getRecordDiff } from "@/api/records";

const UUID = "22222222-2222-2222-2222-222222222222";

describe("records api", () => {
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

  it("fetches the ADR page by UUID", async () => {
    const fetchMock = mockFetch();

    await getRecord(UUID);

    expect(fetchMock.mock.calls[0][0]).toBe(`/api/v1/records/${UUID}`);
  });

  it("fetches a candidate with a slashed ref as a path remainder", async () => {
    const fetchMock = mockFetch();

    await getRecord(UUID, "feature/a b");

    expect(fetchMock.mock.calls[0][0]).toBe(
      `/api/v1/records/${UUID}/candidates/feature/a%20b`,
    );
  });

  it("sends the ref of a diff as a query parameter", async () => {
    const fetchMock = mockFetch();

    await getRecordDiff(UUID, { ref: "feature/x", from: "d1" });

    expect(fetchMock.mock.calls[0][0]).toBe(
      `/api/v1/records/${UUID}/diff?ref=feature%2Fx&from=d1`,
    );
  });

  it("sends the ref of a decision as a query parameter, none for the published row", async () => {
    const fetchMock = mockFetch();
    const body = { action: "accepted" as const, expected_digest: "d1" };

    await postDecision(UUID, body, "feature/x");
    await postDecision(UUID, body);

    expect(fetchMock.mock.calls[0][0]).toBe(
      `/api/v1/records/${UUID}/decisions?ref=feature%2Fx`,
    );
    expect(fetchMock.mock.calls[1][0]).toBe(
      `/api/v1/records/${UUID}/decisions`,
    );
  });
});
