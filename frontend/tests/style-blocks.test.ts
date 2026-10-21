/**
 * Guard against undocumented or hard-coded-colour custom CSS creeping
 * back into `<style>` blocks
 * (Vuetify first, ladder step 6: "every rule carries a one-line
 * comment explaining why steps 1-5 could not express it", and "no
 * hex, rgb or named colours outside plugins/vuetify.ts"). For every `<style>`
 * block under `src/`, this
 * scans each top-level CSS rule and fails the suite if:
 *
 *  - the rule contains a hex (`#abc`, `#aabbcc`, ...) colour literal,
 *    or an `rgb()`/`rgba()`/`hsl()`/`hsla()` call whose first argument
 *    is not a Vuetify theme variable. A theme reference always starts
 *    with `var(--v-` immediately inside the function, e.g.
 *    `rgb(var(--v-theme-primary))` or
 *    `rgba(var(--v-border-color), var(--v-border-opacity))` -- both
 *    allowed; or
 *  - the rule has no justification comment anywhere that explains it.
 *    A rule counts as justified when a `/* ... *\/` comment sits
 *    directly above its selector (blank lines in between are
 *    ignored, so a comment covering a short run of related sibling
 *    rules -- e.g. DiffPanel.vue's three `.diff-line--*` variants, or
 *    the five `:deep(h1..h6)` rules in RecordDecisionCard.vue /
 *    ErratumTextBlocks.vue -- justifies the whole run, not just the
 *    first rule), or when the comment sits inside the rule's own
 *    body, next to the declaration it explains (the style some files
 *    use instead of one block comment, e.g.
 *    `.rendered-markdown`/`.erratum-text-blocks`'s per-property
 *    comments).
 *
 * This is a line-based heuristic, not a real CSS parser: it assumes
 * one selector/declaration/comment per line and plain `/* *\/`
 * comments (no `//` line comments, which are invalid CSS anyway) --
 * true of every `<style>` block in this project today. A file that
 * breaks those assumptions should be reformatted to fit them rather
 * than the checker being made to understand arbitrary CSS.
 */
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const SRC_DIR = path.join(process.cwd(), "src");

/** Recursively collect every `.vue` file path under `dir`. */
function collectVueFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectVueFiles(entryPath));
    } else if (entry.name.endsWith(".vue")) {
      files.push(entryPath);
    }
  }
  return files;
}

/** Extract every `<style ...>...</style>` block's inner text. */
function extractStyleBlocks(content: string): string[] {
  const blocks: string[] = [];
  const pattern = /<style[^>]*>([\s\S]*?)<\/style>/g;
  for (const match of content.matchAll(pattern)) {
    blocks.push(match[1]);
  }
  return blocks;
}

/** A colour function call whose first argument is not a theme
 *  variable, e.g. `rgb(0, 0, 0)` -- but not `rgb(var(--v-theme-x))`
 *  or `rgba(var(--v-border-color), var(--v-border-opacity))`. */
const LITERAL_COLOR_FUNCTION = /\b(?:rgb|rgba|hsl|hsla)\(\s*(?!var\()/;
/** A hex colour literal (`#abc`, `#aabbcc`, `#aabbccdd`). */
const HEX_COLOR = /#[0-9a-fA-F]{3,8}\b/;

/** Find hex/rgb/rgba/hsl/hsla colour literals, ignoring text inside
 *  `/* *\/` comments (so prose mentioning a colour name or an
 *  unrelated `#id` never false-positives). */
function findColorViolations(css: string): string[] {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const violations: string[] = [];
  for (const line of withoutComments.split("\n")) {
    if (HEX_COLOR.test(line) || LITERAL_COLOR_FUNCTION.test(line)) {
      violations.push(line.trim());
    }
  }
  return violations;
}

/**
 * Find every top-level rule (a line that opens a `{` while not
 * nested inside another rule) that has no justification comment,
 * either directly above it (chained through blank lines and through
 * sibling rules that were themselves justified) or inside its own
 * body next to a declaration. Returns each offending selector line.
 */
function findUnjustifiedRules(css: string): string[] {
  const violations: string[] = [];
  const lines = css.split("\n");

  let depth = 0;
  let inComment = false;
  /** Whether the next top-level rule is justified by a comment that
   *  appeared above it (directly, or chained from a prior justified
   *  sibling rule with no unjustified rule breaking the chain). */
  let chainJustified: boolean = false;
  /** Whether the rule currently being scanned (depth > 0) had a
   *  comment above it when it opened. */
  let justifiedBeforeOpen: boolean = false;
  /** Whether the rule currently being scanned has a comment inside
   *  its own body. */
  let bodyHasComment: boolean = false;
  let pendingSelector = "";

  for (const line of lines) {
    if (inComment) {
      if (line.includes("*/")) {
        inComment = false;
        if (depth === 0) {
          chainJustified = true;
        } else {
          bodyHasComment = true;
        }
      } else if (depth > 0) {
        bodyHasComment = true;
      }
      continue;
    }

    const trimmed = line.trim();
    if (trimmed === "") {
      continue; // Blank lines never change justification state.
    }

    if (trimmed.startsWith("/*")) {
      if (trimmed.includes("*/")) {
        if (depth === 0) {
          chainJustified = true;
        } else {
          bodyHasComment = true;
        }
      } else {
        inComment = true;
      }
      continue;
    }

    const opens = (line.match(/\{/g) ?? []).length;
    const closes = (line.match(/\}/g) ?? []).length;

    if (depth === 0) {
      if (opens === 0) {
        // A bare selector-continuation line (ends with a comma):
        // leave justification state untouched.
        continue;
      }
      pendingSelector = trimmed;
      justifiedBeforeOpen = chainJustified;
      bodyHasComment = line.includes("/*");
      depth += opens - closes;
      if (depth === 0) {
        // Opened and closed on the same line -- no body to scan.
        const finalJustified: boolean = justifiedBeforeOpen || bodyHasComment;
        if (!finalJustified) {
          violations.push(pendingSelector);
        }
        chainJustified = finalJustified;
      }
      continue;
    }

    // Inside a rule body (depth > 0).
    if (line.includes("/*")) {
      bodyHasComment = true;
    }
    depth += opens - closes;
    if (depth === 0) {
      const finalJustified: boolean = justifiedBeforeOpen || bodyHasComment;
      if (!finalJustified) {
        violations.push(pendingSelector);
      }
      chainJustified = finalJustified;
    }
  }

  return violations;
}

describe("custom CSS guard", () => {
  const vueFiles = collectVueFiles(SRC_DIR);

  it("found source files to scan", () => {
    // A guard against the scan itself silently finding nothing, e.g.
    // from a wrong path, which would make every check below vacuous.
    expect(vueFiles.length).toBeGreaterThan(30);
  });

  const filesWithStyle = vueFiles
    .map((filePath) => ({
      filePath,
      relativePath: filePath.slice(SRC_DIR.length + 1),
      blocks: extractStyleBlocks(readFileSync(filePath, "utf-8")),
    }))
    .filter((entry) => entry.blocks.length > 0);

  it("found <style> blocks to scan", () => {
    // Same rationale as above, for the <style>-block scan.
    expect(filesWithStyle.length).toBeGreaterThan(5);
  });

  for (const { relativePath, blocks } of filesWithStyle) {
    describe(relativePath, () => {
      blocks.forEach((block, index) => {
        const label =
          blocks.length > 1 ? `<style> block ${index + 1}` : "<style> block";

        it(`${label} has no literal colour outside the theme`, () => {
          expect(findColorViolations(block)).toEqual([]);
        });

        it(`${label} has a justification comment on every rule`, () => {
          expect(findUnjustifiedRules(block)).toEqual([]);
        });
      });
    });
  }
});
