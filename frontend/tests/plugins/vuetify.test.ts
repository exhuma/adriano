/**
 * Ensure every status colour in the theme (`error`, `warning`,
 * `success`, `info`) is readable as *text*: at least 4.5:1 against
 * the opaque `surface` colour, and at least 4.5:1 against that same
 * colour's 12% tonal tint composited over `surface` -- the
 * background `StatusChip` and every status `v-alert` actually render
 * behind the text, under this app's `variant="tonal"` convention
 * (see `plugins/vuetify.ts`'s theme comment and
 * `vuetify/lib/styles/tools/_variant.sass`'s `activated-opacity`).
 * Checked for both the light and the dark theme.
 */
import { describe, expect, it } from "vitest";

import { dark, light } from "@/plugins/vuetify";

/** Vuetify's default tonal-variant background opacity
 *  (`--v-activated-opacity`; see `composables/theme.js`'s
 *  `genDefaults`). Neither theme below overrides it. */
const TONAL_OPACITY = 0.12;

/** Minimum contrast ratio WCAG 2.2 SC 1.4.3 requires for normal-size
 *  text. */
const MIN_TEXT_CONTRAST = 4.5;

type Rgb = [number, number, number];

function hexToRgb(hex: string): Rgb {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

/** WCAG relative luminance of one sRGB channel (0-255). */
function linearize(channel: number): number {
  const c = channel / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

/** WCAG relative luminance of an sRGB colour. */
function relativeLuminance([r, g, b]: Rgb): number {
  return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b);
}

/** WCAG contrast ratio between two sRGB colours (order-independent). */
function contrastRatio(a: Rgb, b: Rgb): number {
  const l1 = relativeLuminance(a);
  const l2 = relativeLuminance(b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/** `fg` painted at `alpha` opacity over opaque `bg` (plain sRGB
 *  alpha compositing, matching how a browser paints a CSS
 *  translucent overlay). */
function compositeOver(fg: Rgb, bg: Rgb, alpha: number): Rgb {
  return [0, 1, 2].map(
    (i) => alpha * fg[i] + (1 - alpha) * bg[i],
  ) as Rgb;
}

const STATUS_COLOR_KEYS = ["error", "warning", "success", "info"] as const;

describe("theme status colours", () => {
  for (const [themeName, definition] of [
    ["light", light],
    ["dark", dark],
  ] as const) {
    const colors = definition.colors;
    if (!colors) {
      throw new Error(`${themeName} theme has no colors`);
    }
    const surfaceHex = colors.surface;
    // Every colour below is a literal hex string in plugins/vuetify.ts
    // (never a number or an {h,s,v}/{r,g,b} object); this just gives
    // the test a plain `string` to work with instead of Vuetify's
    // wider `ColorValue` type.
    if (typeof surfaceHex !== "string") {
      throw new Error(`${themeName} theme has no hex surface colour`);
    }
    const surfaceRgb = hexToRgb(surfaceHex);

    for (const key of STATUS_COLOR_KEYS) {
      const colorHex = colors[key];

      const label = `${themeName} "${key}"`;

      it(`${label} reaches ${MIN_TEXT_CONTRAST}:1 as text on surface`, () => {
        expect(typeof colorHex).toBe("string");
        const colorRgb = hexToRgb(colorHex as string);

        expect(contrastRatio(colorRgb, surfaceRgb)).toBeGreaterThanOrEqual(
          MIN_TEXT_CONTRAST,
        );
      });

      it(`${label} reaches ${MIN_TEXT_CONTRAST}:1 on its tonal tint`, () => {
        expect(typeof colorHex).toBe("string");
        const colorRgb = hexToRgb(colorHex as string);
        const tintRgb = compositeOver(colorRgb, surfaceRgb, TONAL_OPACITY);

        expect(contrastRatio(colorRgb, tintRgb)).toBeGreaterThanOrEqual(
          MIN_TEXT_CONTRAST,
        );
      });
    }
  }
});

/**
 * P11-R-03: Vuetify applies `medium-emphasis-opacity` as a literal
 * CSS `opacity` on the whole element (`.v-list-item-subtitle`'s
 * `opacity: var(--v-list-item-subtitle-opacity,
 * var(--v-medium-emphasis-opacity))`; `.v-label`'s field-label rule
 * is the same variable) -- a true alpha blend of the on-surface
 * colour toward whatever sits behind it, not a partial colour-mix of
 * text alone. That "behind it" also carries any `StatusChip` nested
 * inside the subtitle (the "Inferred from filename" chip in
 * `RecordMetadataCard.vue`): CSS `opacity` applies to an element and
 * its whole subtree as one group, so the chip blends along with its
 * label text, at the same ratio.
 *
 * `on-surface` is Vuetify's auto-derived colour for the on-surface
 * key neither theme sets explicitly: pure black for light's white
 * surface, pure white for dark's near-black surface
 * (`hasLightForeground`, `composables/theme.js`). The 4% hover tint
 * is Vuetify's default list-item hover overlay (`--v-hover-opacity`),
 * painted in the item's own text colour (`background: currentColor`)
 * behind the subtitle/chip's own opacity.
 */
describe("medium-emphasis text contrast (P11-R-03)", () => {
  const HOVER_OPACITY = 0.04;
  const DEFAULT_MEDIUM_EMPHASIS = 0.6;

  for (const [themeName, definition, onSurface] of [
    ["light", light, [0, 0, 0] as Rgb],
    ["dark", dark, [255, 255, 255] as Rgb],
  ] as const) {
    const colors = definition.colors;
    const surfaceHex = colors?.surface;
    if (typeof surfaceHex !== "string") {
      throw new Error(`${themeName} theme has no hex surface colour`);
    }
    const surfaceRgb = hexToRgb(surfaceHex);
    const mediumEmphasis =
      (definition.variables?.["medium-emphasis-opacity"] as
        | number
        | undefined) ?? DEFAULT_MEDIUM_EMPHASIS;

    it(`${themeName} medium-emphasis text reaches ${MIN_TEXT_CONTRAST}:1 on surface`, () => {
      const blended = compositeOver(onSurface, surfaceRgb, mediumEmphasis);

      expect(contrastRatio(blended, surfaceRgb)).toBeGreaterThanOrEqual(
        MIN_TEXT_CONTRAST,
      );
    });

    it(`${themeName} medium-emphasis text reaches ${MIN_TEXT_CONTRAST}:1 over the 4% hover tint`, () => {
      const hoverBg = compositeOver(onSurface, surfaceRgb, HOVER_OPACITY);
      const blended = compositeOver(onSurface, hoverBg, mediumEmphasis);

      expect(contrastRatio(blended, hoverBg)).toBeGreaterThanOrEqual(
        MIN_TEXT_CONTRAST,
      );
    });
  }
});

/**
 * a plain `<a>` or an unstyled `router-link`
 * (e.g. `RecordLinksCard.vue`'s sidebar relationship links, the
 * "View errata" anchor, and server-rendered markdown links) carried
 * no colour of its own, so the browser painted its built-in link
 * colour instead of the theme -- 4.14:1 on the dark theme's
 * `surface`, under 4.5:1. Each one now gets Vuetify's own
 * `text-primary` utility class (or, for markdown links with no
 * class hook, a scoped `:deep(a) { color:
 * rgb(var(--v-theme-primary)) }` rule). This guards the premise of
 * that fix: `primary` itself has to clear 4.5:1 as text on both the
 * opaque `surface` colour (most of these links sit on a card) and
 * the page's own `background` colour (a link directly in `v-main`)
 * in both themes, so the fix cannot regress if either colour
 * changes later.
 */
describe("theme primary colour as link text", () => {
  for (const [themeName, definition] of [
    ["light", light],
    ["dark", dark],
  ] as const) {
    const colors = definition.colors;
    if (!colors) {
      throw new Error(`${themeName} theme has no colors`);
    }
    const primaryHex = colors.primary;
    if (typeof primaryHex !== "string") {
      throw new Error(`${themeName} theme has no hex primary colour`);
    }
    const primaryRgb = hexToRgb(primaryHex);

    for (const bgKey of ["surface", "background"] as const) {
      const bgHex = colors[bgKey];
      const label = `${themeName} "primary" reaches ` +
        `${MIN_TEXT_CONTRAST}:1 as link text on ${bgKey}`;

      it(label, () => {
        expect(typeof bgHex).toBe("string");
        const bgRgb = hexToRgb(bgHex as string);

        expect(contrastRatio(primaryRgb, bgRgb)).toBeGreaterThanOrEqual(
          MIN_TEXT_CONTRAST,
        );
      });
    }
  }
});
