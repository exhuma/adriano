/**
 * Ensure every reason the filter offers has a plain-language label
 * and that the origin labels are plain words.
 */
import { describe, expect, it } from "vitest";

import {
  NOT_INDEXED_REASON_CODES,
  issueCodeLabel,
  notIndexedReasonOptions,
  originLabel,
} from "@/utils/labels";

describe("not-indexed labels", () => {
  it("offers a reason filter option, with its plain headline, for every reason code", () => {
    const options = notIndexedReasonOptions();

    expect(options.map((o) => o.value)).toEqual(NOT_INDEXED_REASON_CODES);
    for (const option of options) {
      expect(option.title).toBe(issueCodeLabel(option.value));
      expect(option.title.length).toBeGreaterThan(10);
      expect(option.title).not.toContain("_");
    }
  });

  it("covers the intake refusals a poll or a push can queue", () => {
    expect(NOT_INDEXED_REASON_CODES).toEqual(
      expect.arrayContaining([
        "duplicate_uuid",
        "fetch_failed",
        "uuid_mismatch",
        "published_ref_not_allowed",
        "content_too_large",
        "bad_encoding",
        "missing_uuid",
      ]),
    );
  });

  it("words the origin plainly", () => {
    expect(originLabel("poll")).toBe("Polled");
    expect(originLabel("push")).toBe("Pushed");
  });
});
