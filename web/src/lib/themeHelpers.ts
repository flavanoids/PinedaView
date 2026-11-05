// SPDX-License-Identifier: Apache-2.0
import type { CustomColours } from "@pinedaview/protocol";

export const LIGHT_INK = "#f7f2ea";
export const DARK_INK = "#221d1a";

/**
 * Validates a 6-digit hex color string with leading '#'.
 */
export function isValidHex(hex: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(hex.trim());
}

/**
 * Normalizes hex string to lowercase with '#'.
 */
export function normalizeHex(hex: string, fallback = "#000000"): string {
  const trimmed = hex.trim();
  const withHash = trimmed.startsWith("#") ? trimmed : `#${trimmed}`;
  return isValidHex(withHash) ? withHash.toLowerCase() : fallback;
}

export type Rgb = [number, number, number];

export function hexToRgb(hex: string): Rgb {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

export function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) =>
    Math.max(0, Math.min(255, Math.round(v)))
      .toString(16)
      .padStart(2, "0");
  return `#${clamp(r)}${clamp(g)}${clamp(b)}`;
}

/**
 * WCAG relative luminance, 0 (black) to 1 (white).
 * Matches python `pineda_web.themes._luminance`.
 */
export function luminance(hex: string): number {
  if (!isValidHex(hex)) return 0;
  const rgb = hexToRgb(hex);
  const r = toLinear(rgb[0]);
  const g = toLinear(rgb[1]);
  const b = toLinear(rgb[2]);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function toLinear(c: number): number {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

/**
 * Light or dark text, whichever reads better on average across the given backgrounds.
 * Matches python `pineda_web.themes.ink_for`.
 */
export function inkFor(...backgrounds: string[]): string {
  if (!backgrounds.length) return LIGHT_INK;
  const valid = backgrounds.filter(isValidHex);
  if (!valid.length) return LIGHT_INK;
  const meanLum =
    valid.reduce((acc, h) => acc + luminance(h), 0) / valid.length;
  const darkLum = luminance(DARK_INK);
  const lightLum = luminance(LIGHT_INK);
  const onLight = (meanLum + 0.05) / (darkLum + 0.05);
  const onDark = (lightLum + 0.05) / (meanLum + 0.05);
  return onLight > onDark ? DARK_INK : LIGHT_INK;
}

/**
 * WCAG contrast ratio between two colors, from 1 to 21.
 */
export function contrastRatio(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/**
 * Scales each RGB channel by factor (<1 darkens, >1 lightens).
 * Matches python `pineda_web.themes._shade`.
 */
export function shade(hex: string, factor: number): string {
  if (!isValidHex(hex)) return hex;
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(r * factor, g * factor, b * factor);
}

export interface Hsv {
  h: number; // 0..360
  s: number; // 0..1
  v: number; // 0..1
}

export function hexToHsv(hex: string): Hsv {
  const rgb = hexToRgb(hex);
  const r = rgb[0] / 255;
  const g = rgb[1] / 255;
  const b = rgb[2] / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  let h = 0;
  if (delta !== 0) {
    if (max === r) h = ((g - b) / delta + (g < b ? 6 : 0)) % 6;
    else if (max === g) h = (b - r) / delta + 2;
    else h = (r - g) / delta + 4;
    h *= 60;
  }
  const s = max === 0 ? 0 : delta / max;
  return { h, s, v: max };
}

export function hsvToHex(h: number, s: number, v: number): string {
  const normH = ((h % 360) + 360) % 360;
  const c = v * s;
  const x = c * (1 - Math.abs(((normH / 60) % 2) - 1));
  const m = v - c;
  let r1 = 0;
  let g1 = 0;
  let b1 = 0;
  if (normH < 60) {
    r1 = c;
    g1 = x;
  } else if (normH < 120) {
    r1 = x;
    g1 = c;
  } else if (normH < 180) {
    g1 = c;
    b1 = x;
  } else if (normH < 240) {
    g1 = x;
    b1 = c;
  } else if (normH < 300) {
    r1 = x;
    b1 = c;
  } else {
    r1 = c;
    b1 = x;
  }
  return rgbToHex((r1 + m) * 255, (g1 + m) * 255, (b1 + m) * 255);
}

/**
 * Generate a complete, balanced theme palette starting from a single seed color.
 */
export function generateHarmoniousPalette(
  seedHex: string,
  mode:
    "monochromatic" | "analogous" | "complementary" | "vibrant" = "analogous",
  label = "My Palette",
): CustomColours {
  const base = isValidHex(seedHex) ? seedHex : "#283548";
  const hsv = hexToHsv(base);
  const isDark = hsv.v < 0.5;

  let stage = base;
  let accent = "#e7a34a";
  let weather = "#3a3732";
  let clock = "#282622";
  let affirmation = "#645e54";

  if (mode === "monochromatic") {
    stage = hsvToHex(hsv.h, Math.min(0.2, hsv.s), isDark ? 0.08 : 0.96);
    weather = hsvToHex(hsv.h, Math.max(0.25, hsv.s), isDark ? 0.28 : 0.82);
    clock = hsvToHex(hsv.h, Math.max(0.35, hsv.s), isDark ? 0.2 : 0.88);
    affirmation = hsvToHex(
      hsv.h,
      Math.max(0.2, hsv.s * 0.8),
      isDark ? 0.35 : 0.75,
    );
    accent = hsvToHex((hsv.h + 25) % 360, 0.75, isDark ? 0.95 : 0.85);
  } else if (mode === "analogous") {
    stage = hsvToHex(hsv.h, Math.min(0.25, hsv.s * 0.4), isDark ? 0.09 : 0.95);
    weather = hsvToHex(
      hsv.h,
      Math.min(0.65, Math.max(0.3, hsv.s)),
      isDark ? 0.32 : 0.82,
    );
    clock = hsvToHex(
      (hsv.h + 30) % 360,
      Math.min(0.65, Math.max(0.3, hsv.s)),
      isDark ? 0.26 : 0.86,
    );
    affirmation = hsvToHex(
      (hsv.h - 30 + 360) % 360,
      Math.min(0.6, Math.max(0.25, hsv.s)),
      isDark ? 0.36 : 0.78,
    );
    accent = hsvToHex((hsv.h + 180) % 360, 0.78, 0.92);
  } else if (mode === "complementary") {
    stage = hsvToHex(hsv.h, Math.min(0.2, hsv.s * 0.3), isDark ? 0.08 : 0.96);
    weather = hsvToHex(hsv.h, 0.5, isDark ? 0.32 : 0.82);
    clock = hsvToHex(hsv.h, 0.35, isDark ? 0.24 : 0.88);
    const compH = (hsv.h + 180) % 360;
    affirmation = hsvToHex(compH, 0.4, isDark ? 0.35 : 0.8);
    accent = hsvToHex(compH, 0.85, 0.92);
  } else {
    // vibrant
    stage = isDark ? "#0f1118" : "#f5f6fa";
    weather = hsvToHex(hsv.h, 0.65, isDark ? 0.42 : 0.84);
    clock = hsvToHex((hsv.h + 45) % 360, 0.6, isDark ? 0.34 : 0.86);
    affirmation = hsvToHex((hsv.h + 90) % 360, 0.55, isDark ? 0.4 : 0.8);
    accent = hsvToHex((hsv.h + 180) % 360, 0.82, 0.94);
  }

  return {
    label,
    stage: stage.toLowerCase(),
    accent: accent.toLowerCase(),
    weather: weather.toLowerCase(),
    clock: clock.toLowerCase(),
    affirmation: affirmation.toLowerCase(),
    phrase: affirmation.toLowerCase(),
    font: null,
  };
}

/**
 * Calculates a darkened, dusk-to-night twin from a daytime palette.
 * Follows the recipe used for built-in themes in themes.py: keeps hue,
 * drops stage to a near-black tinted with the theme's own color, deepens cards
 * so light text sits on them, and lifts accent saturation.
 */
export function generateNightTwin(colours: CustomColours): CustomColours {
  const stageHsv = hexToHsv(colours.stage);
  // Near-black stage tinted with the theme's own hue
  const nightStage = hsvToHex(
    stageHsv.h,
    Math.min(0.4, Math.max(0.15, stageHsv.s)),
    0.09,
  );

  const deepen = (hex: string) => {
    const h = hexToHsv(hex);
    return hsvToHex(
      h.h,
      Math.min(0.7, Math.max(0.35, h.s)),
      Math.min(0.35, Math.max(0.18, h.v * 0.4)),
    );
  };

  const accentHsv = hexToHsv(colours.accent);
  const nightAccent = hsvToHex(
    accentHsv.h,
    Math.min(0.85, accentHsv.s * 1.1),
    Math.max(0.88, accentHsv.v),
  );

  return {
    label: `${colours.label} (Night)`,
    stage: nightStage.toLowerCase(),
    accent: nightAccent.toLowerCase(),
    weather: deepen(colours.weather).toLowerCase(),
    clock: deepen(colours.clock).toLowerCase(),
    affirmation: deepen(colours.affirmation).toLowerCase(),
    phrase: colours.phrase ? deepen(colours.phrase).toLowerCase() : null,
    font: colours.font ?? null,
  };
}
