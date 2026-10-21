#!/usr/bin/env node
/**
 * Regenerate `src/types/openapi.ts` from the backend's OpenAPI schema.
 *
 * Tries the running dev backend first (`OPENAPI_URL`, default
 * `http://localhost:8100/openapi.json`); on failure (backend not
 * running) falls back to the committed snapshot `frontend/openapi.json`
 * so the generator still works offline/in CI. When the live fetch
 * succeeds, the snapshot is refreshed so it stays in sync and is
 * committed alongside the generated types.
 */
import { writeFile, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

import openapiTS, { astToString } from "openapi-typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const snapshotPath = path.join(root, "openapi.json");
const outPath = path.join(root, "src", "types", "openapi.ts");
const liveUrl = process.env.OPENAPI_URL ?? "http://localhost:8100/openapi.json";

async function loadSchema() {
  try {
    const response = await fetch(liveUrl, { signal: AbortSignal.timeout(2000) });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    await writeFile(snapshotPath, `${text}\n`, "utf-8");
    console.log(`Fetched live schema from ${liveUrl}; snapshot refreshed.`);
    return JSON.parse(text);
  } catch (error) {
    console.warn(
      `Could not fetch ${liveUrl} (${error.message}); using committed ` +
        `snapshot ${path.relative(root, snapshotPath)}.`,
    );
    const text = await readFile(snapshotPath, "utf-8");
    return JSON.parse(text);
  }
}

/**
 * Hoist any schema whose generated type recursively refers to
 * itself (e.g. the backend's `JsonValue`) out of the `components`
 * interface into a standalone top-level `export type` alias.
 *
 * openapi-typescript renders every schema as a property accessed via
 * `components["schemas"]["Name"]`. TypeScript accepts a *named*
 * recursive type alias (`type Json = Json[] | ...`), but rejects the
 * equivalent self-reference through an indexed-access type on the
 * interface currently being defined (`TS2502: 'Name' is referenced
 * directly or indirectly in its own type annotation`). Rewriting the
 * self-referencing property to point at a hoisted named alias avoids
 * that without changing the schema's shape.
 *
 * :param source: Generated TypeScript source (`astToString` output).
 * :returns: The source with any self-referential schema hoisted.
 */
function hoistSelfReferentialSchemas(source) {
  const marker = "schemas: {";
  const markerIndex = source.indexOf(marker);
  if (markerIndex === -1) {
    return source;
  }
  const bodyStart = markerIndex + marker.length;

  // Find the matching closing brace for the `schemas` object,
  // skipping over `/** ... */` comments so stray punctuation in
  // prose can never confuse the depth count.
  let depth = 1;
  let i = bodyStart;
  while (i < source.length && depth > 0) {
    if (source.startsWith("/*", i)) {
      const end = source.indexOf("*/", i + 2);
      i = end === -1 ? source.length : end + 2;
      continue;
    }
    if (source[i] === "{") depth++;
    else if (source[i] === "}") depth--;
    i++;
  }
  const bodyEnd = i - 1;
  const schemasBody = source.slice(bodyStart, bodyEnd);

  // Split into top-level entries (one property, with its leading
  // comment), tracking nesting depth so a `;` inside a nested
  // object/array/union type never splits an entry early.
  const entries = [];
  let entryStart = 0;
  let entryDepth = 0;
  let j = 0;
  while (j < schemasBody.length) {
    if (schemasBody.startsWith("/*", j)) {
      const end = schemasBody.indexOf("*/", j + 2);
      j = end === -1 ? schemasBody.length : end + 2;
      continue;
    }
    const ch = schemasBody[j];
    if (ch === "{" || ch === "(" || ch === "[") {
      entryDepth++;
    } else if (ch === "}" || ch === ")" || ch === "]") {
      entryDepth--;
    } else if (ch === ";" && entryDepth === 0) {
      entries.push(schemasBody.slice(entryStart, j + 1));
      entryStart = j + 1;
    }
    j++;
  }

  // Each schema property is rendered at a fixed 8-space indent as
  // `NAME: <body>;`; its leading JSDoc comment (if any) uses a
  // different indent (` * ...`), so this pattern cannot match inside
  // a comment.
  const propertyPattern = /\n {8}([A-Za-z0-9_]+): ([\s\S]*);\s*$/;
  const hoisted = [];
  const rewritten = entries.map((entry) => {
    const match = entry.match(propertyPattern);
    if (!match) {
      return entry;
    }
    const [whole, name, body] = match;
    const selfRef = new RegExp(`components\\["schemas"\\]\\["${name}"\\]`, "g");
    if (!selfRef.test(body)) {
      return entry;
    }
    hoisted.push(`export type ${name} = ${body.replace(selfRef, name)};\n`);
    return entry.slice(0, entry.length - whole.length) + `\n        ${name}: ${name};`;
  });

  if (hoisted.length === 0) {
    return source;
  }
  const newSource =
    source.slice(0, bodyStart) + rewritten.join("") + source.slice(bodyEnd);
  return `${hoisted.join("\n")}\n${newSource}`;
}

const schema = await loadSchema();
const ast = await openapiTS(schema);
const banner =
  "/**\n" +
  " * Generated from the backend OpenAPI schema. Do not hand-edit.\n" +
  " * Regenerate with `npm run gen:types` (see scripts/gen-types.mjs).\n" +
  " */\n\n";
const generated = hoistSelfReferentialSchemas(astToString(ast));
await writeFile(outPath, banner + generated, "utf-8");
console.log(`Wrote ${path.relative(root, outPath)}.`);
