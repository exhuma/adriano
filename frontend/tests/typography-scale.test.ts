/**
 * Guard against MD2 (Vuetify 2/3 "Material Design 2") typography
 * classes creeping back into `src/`. Vuetify 4's stylesheet
 * (`vuetify/lib/styles/main.css`) only defines the MD3 classes
 * (`text-display-*`, `text-headline-*`, `text-title-*`,
 * `text-body-*`, `text-label-*`); the old MD2 names
 * (`text-h5`, `text-subtitle-1`, `text-subtitle-2`, `text-body-1`,
 * `text-body-2`, `text-caption`, `text-overline`) are not defined at
 * all, so a component that still uses one renders at the browser's
 * unstyled default instead of the app's type scale (docs/ui-review
 * G-05, R-07; mapping documented in `phases/DECISIONS.md` Phase 11).
 * This scans every `.vue`/`.ts` file under `src/` for those literal
 * class names and fails if any remain.
 */
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const SRC_DIR = path.join(process.cwd(), "src");

/** The retired MD2 class names, matched with a word boundary so, for
 *  example, `text-body-1` does not also match `text-body-large`. */
const MD2_CLASSES = [
  "text-h5",
  "text-subtitle-1",
  "text-subtitle-2",
  "text-body-1",
  "text-body-2",
  "text-caption",
  "text-overline",
] as const;

const MD2_CLASS_PATTERN = new RegExp(
  `\\b(?:${MD2_CLASSES.join("|")})\\b`,
);

/** Recursively collect every `.vue`/`.ts` file path under `dir`. */
function collectSourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectSourceFiles(entryPath));
    } else if (entry.name.endsWith(".vue") || entry.name.endsWith(".ts")) {
      files.push(entryPath);
    }
  }
  return files;
}

describe("MD2 typography class guard", () => {
  const sourceFiles = collectSourceFiles(SRC_DIR);

  it("found source files to scan", () => {
    // A guard against the scan itself silently finding nothing, e.g.
    // from a wrong path, which would make every check below vacuous.
    expect(sourceFiles.length).toBeGreaterThan(50);
  });

  for (const filePath of sourceFiles) {
    const relativePath = filePath.slice(SRC_DIR.length + 1);

    it(`${relativePath} uses no retired MD2 typography class`, () => {
      const content = readFileSync(filePath, "utf-8");
      const match = content.match(MD2_CLASS_PATTERN);

      expect(match?.[0]).toBeUndefined();
    });
  }
});
