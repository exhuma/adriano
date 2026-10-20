/**
 * Ensure `stripLeadingTitleHeading` drops a leading `<h1>` only when
 * its text matches the record title (whitespace/case-insensitively),
 * leaves every other case byte-for-byte unchanged, and never touches
 * anything beyond that single leading element (R-03: no duplicate
 * title, without otherwise mutating the server's sanitized HTML).
 */
import { describe, expect, it } from "vitest";

import { stripLeadingTitleHeading } from "@/utils/renderedHtml";

describe("stripLeadingTitleHeading", () => {
  it("drops a leading h1 that exactly matches the title", () => {
    const html = "<h1>Use PostgreSQL</h1><p>Context</p>";
    expect(stripLeadingTitleHeading(html, "Use PostgreSQL")).toBe("<p>Context</p>");
  });

  it("matches case- and whitespace-insensitively", () => {
    const html = "<h1>  Use   POSTGRESQL  </h1><p>Context</p>";
    expect(stripLeadingTitleHeading(html, "use postgresql")).toBe("<p>Context</p>");
  });

  it("leaves the html unchanged when the leading h1 text differs", () => {
    const html = "<h1>Something else</h1><p>Context</p>";
    expect(stripLeadingTitleHeading(html, "Use PostgreSQL")).toBe(html);
  });

  it("leaves the html unchanged when the first element is not an h1", () => {
    const html = "<h2>Use PostgreSQL</h2><p>Context</p>";
    expect(stripLeadingTitleHeading(html, "Use PostgreSQL")).toBe(html);
  });

  it("leaves the html unchanged when it has no elements at all", () => {
    expect(stripLeadingTitleHeading("", "Use PostgreSQL")).toBe("");
  });

  it("only removes the matching leading h1, keeping later content untouched", () => {
    const html = "<h1>Use PostgreSQL</h1><h2>Context</h2><p>Body text.</p>";
    expect(stripLeadingTitleHeading(html, "Use PostgreSQL")).toBe(
      "<h2>Context</h2><p>Body text.</p>",
    );
  });

  it("does not remove a later h1 matching the title, only a leading one", () => {
    const html = "<p>Intro</p><h1>Use PostgreSQL</h1>";
    expect(stripLeadingTitleHeading(html, "Use PostgreSQL")).toBe(html);
  });
});
