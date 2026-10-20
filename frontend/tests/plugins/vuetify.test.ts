/**
 * Ensure every status colour in the theme (`error`, `warning`,
 * `success`, `info`) is readable as *text*: at least 4.5:1 against
 * the opaque `surface` colour, and at least 4.5:1 against that same
 * colour's 12% tonal tint composited over `surface` -- the
 * background `StatusChip` and every status `v-alert` actually render
 * behind the text, under this app's `variant="tonal"` convention
 * (see `plugins/vuetify.ts`'s theme comment and
 * `vuetify/lib/styles/tools/_variant.sass`'s `activated-opacity`).
 * Checked for both the light and the dark theme (docs/ui-review
 * G-01, G-06).
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
