// SPDX-License-Identifier: Apache-2.0
import type { components, Theme } from "@pinedaview/protocol";

import "./tokens.css";

/** The colour CSS variables applyTheme() writes directly. The `-soft` / `-faint`
    tiers are derived from these in tokens.css so the Accessibility "High
    contrast" toggle can override the derivation. */
export const COLOR_VARS = [
  "--stage",
  "--on-stage",
  "--accent",
  "--on-card",
  "--card-weather",
  "--card-clock",
  "--card-affirmation",
  "--card-phrase",
  "--card-forecast",
  "--card-nowPlaying",
  "--card-countdown",
  "--card-moon",
  "--card-generic",
] as const;

/** Perceived brightness of a `#rrggbb` hex color, 0 (black) to 1 (white) —
    good enough for a light/dark switch, not colour-managed rendering. */
function luminance(hex: string): number {
  const h = hex.replace("#", "");
  if (h.length !== 6) return 1;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

type Rgb = [number, number, number];

const hexToRgb = (hex: string): Rgb => {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255) as Rgb;
};
const rgbToHex = (rgb: Rgb): string =>
  "#" +
  rgb
    .map((c) =>
      Math.round(Math.min(Math.max(c, 0), 1) * 255)
        .toString(16)
        .padStart(2, "0"),
    )
    .join("");

/** WCAG contrast ratio of two `#rrggbb` colors, 1 to 21. */
export function contrast(a: string, b: string): number {
  const rel = (hex: string) => {
    const [r, g, bl] = hexToRgb(hex).map((c) =>
      c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
    ) as Rgb;
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [x, y] = [rel(a), rel(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

/** sRGB ↔ OKLCH (Björn Ottosson's OKLab), for hue-preserving tints. */
function toOklch([r, g, b]: Rgb): Rgb {
  const lin = (c: number) =>
    c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  const [R, G, B] = [lin(r), lin(g), lin(b)];
  const l = Math.cbrt(0.4122214708 * R + 0.5363325363 * G + 0.0514459929 * B);
  const m = Math.cbrt(0.2119034982 * R + 0.6806995451 * G + 0.1073969566 * B);
  const s = Math.cbrt(0.0883024619 * R + 0.2817188376 * G + 0.6299787005 * B);
  const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
  const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const bb = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  return [L, Math.hypot(a, bb), Math.atan2(bb, a)];
}
function fromOklch([L, C, H]: Rgb): Rgb | null {
  const a = C * Math.cos(H);
  const b = C * Math.sin(H);
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const lin = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  if (lin.some((c) => c < -0.001 || c > 1.001)) return null;
  return lin.map((c) =>
    c <= 0.0031308 ? 12.92 * c : 1.055 * Math.max(c, 0) ** (1 / 2.4) - 0.055,
  ) as Rgb;
}

/** Text for a card of color `bg`: its hue with `chroma`, stepped darker
    (or lighter, on a dark card) just far enough to reach `target`
    contrast. chroma 0 gives a near-neutral ink. */
export function ink(bg: string, target: number, chroma = 0): string {
  if (bg.replace("#", "").length !== 6) return bg;
  const [L0, , H] = toOklch(hexToRgb(bg));
  const dir = contrast(bg, "#000000") >= contrast(bg, "#ffffff") ? -1 : 1;
  let out = dir < 0 ? "#000000" : "#ffffff";
  for (let L = L0; L >= 0 && L <= 1; L += dir * 0.01) {
    // Pull chroma back until the color fits in sRGB.
    let rgb: Rgb | null = null;
    for (let c = chroma; c >= 0 && !rgb; c -= 0.01) rgb = fromOklch([L, c, H]);
    if (!rgb) continue;
    const hex = rgbToHex(rgb);
    if (contrast(hex, bg) >= target) {
      out = hex;
      break;
    }
  }
  return out;
}

/** The themes a person picks from: every theme that isn't another's night
    twin. The server swaps a twin in at sunset and back at sunrise, so
    listing it too would just be a duplicate of its daytime self. */
export function pickableThemes(themes: Theme[]): Theme[] {
  const twins = new Set(themes.map((t) => t.night).filter(Boolean));
  return themes.filter((t) => !twins.has(t.name));
}

/** Push a server Theme onto a root element's custom properties. */
export function applyTheme(
  theme: Theme,
  root: HTMLElement = document.documentElement,
): void {
  const set = (name: string, value: string) =>
    root.style.setProperty(name, value);

  // Named so tokens.css can key a theme-specific override off it (so far
  // just the "groovy" theme's typeface — see its [data-theme="groovy"]
  // block); every other visual is driven by the color variables below.
  root.dataset.theme = theme.name;

  set("--stage", theme.stage);
  set("--on-stage", theme.on_stage);
  set("--accent", theme.accent);
  set("--on-card", theme.on_card);
  set("--card-moon", "#2d3455");
  set("--card-generic", theme.cards.weather ?? "#3a3732");

  for (const [slot, hex] of Object.entries(theme.cards)) {
    set(`--card-${slot}`, hex);
  }

  // The quote card's two inks, from its own color so every theme gets a
  // readable pair: the quote a near-neutral ink, the author the card's own
  // hue, saturated, at a softer contrast.
  const quoteBg = theme.cards.affirmation;
  if (quoteBg) {
    set("--quote-ink", ink(quoteBg, 9, 0.02));
    set("--quote-by", ink(quoteBg, 4.5, 0.16));
  }

  // "glass" swaps the whole card surface treatment (see tokens.css); "solid"
  // is the default and needs no attribute.
  if (theme.surface === "glass") {
    root.dataset.surface = "glass";
  } else {
    delete root.dataset.surface;
  }

  // Derived from the stage color rather than the theme name, so any theme
  // (present or future — night variants, quiet_canvas, cocoa_ember) that
  // paints a dark stage gets the same dark-mode-only touches (see the
  // moon card's brighter lit face in tokens.css) without listing names.
  if (luminance(theme.stage) < 0.4) {
    root.dataset.dark = "true";
  } else {
    delete root.dataset.dark;
  }
}

/** A pickable typeface's id; "" (the theme's own) is the only other value. */
export type FontId = Exclude<
  NonNullable<components["schemas"]["ProfileUpdate"]["font"]>,
  ""
>;

export interface FontChoice {
  id: FontId;
  label: string;
  /** The --font-display / --font-body stack it sets. */
  stack: string;
  /** One line on what it is, for the picker. */
  note: string;
}

const SANS = '"Helvetica Neue", system-ui, sans-serif';
const SERIF = '"Iowan Old Style", Palatino, Georgia, serif';
const MONO = 'ui-monospace, Menlo, Consolas, monospace';

/** Typefaces a profile can wear over any theme (Profile.font), and a theme
    of your own can come with (Theme.font). Mirrors FONTS in core's
    themes.py; the @font-face rules are in web/src/styles/fonts.css, and each
    file only downloads once something draws in it. Sans, display, serif,
    then the playful ones. */
export const FONTS: readonly FontChoice[] = [
  {
    id: "google_sans_flex",
    label: "Google Sans Flex",
    stack: `"Google Sans Flex", ${SANS}`,
    note: "Google's own interface sans, open-sourced in 2025.",
  },
  {
    id: "atkinson_next",
    label: "Atkinson Hyperlegible Next",
    stack: `"Atkinson Hyperlegible Next", ${SANS}`,
    note: "Braille Institute, 2025. Drawn so similar letters never blur together.",
  },
  {
    id: "zalando_sans",
    label: "Zalando Sans",
    stack: `"Zalando Sans", ${SANS}`,
    note: "Zalando's brand grotesk, released free in 2025.",
  },
  {
    id: "geist",
    label: "Geist",
    stack: `"Geist", ${SANS}`,
    note: "Vercel's crisp, even sans.",
  },
  {
    id: "mona_sans",
    label: "Mona Sans",
    stack: `"Mona Sans", ${SANS}`,
    note: "GitHub's sturdy grotesk.",
  },
  {
    id: "inter",
    label: "Inter",
    stack: `"Inter", ${SANS}`,
    note: "The screen-interface workhorse, version 4.",
  },
  {
    id: "instrument_sans",
    label: "Instrument Sans",
    stack: `"Instrument Sans", ${SANS}`,
    note: "Compact and precise, a designer favourite.",
  },
  {
    id: "hanken_grotesk",
    label: "Hanken Grotesk",
    stack: `"Hanken Grotesk", ${SANS}`,
    note: "A friendly geometric grotesk, easy at a glance.",
  },
  {
    id: "schibsted_grotesk",
    label: "Schibsted Grotesk",
    stack: `"Schibsted Grotesk", ${SANS}`,
    note: "A newsroom's sans, sturdy and warm.",
  },
  {
    id: "host_grotesk",
    label: "Host Grotesk",
    stack: `"Host Grotesk", ${SANS}`,
    note: "A neat 2024 grotesk with soft, open curves.",
  },
  {
    id: "parkinsans",
    label: "Parkinsans",
    stack: `"Parkinsans", ${SANS}`,
    note: "Rounded and upbeat, from 2024.",
  },
  {
    id: "funnel_display",
    label: "Funnel Display",
    stack: `"Funnel Display", ${SANS}`,
    note: "Sharp, geometric headline type, from 2024.",
  },
  {
    id: "unbounded",
    label: "Unbounded",
    stack: `"Unbounded", ${SANS}`,
    note: "Very wide and a little futuristic.",
  },
  {
    id: "bricolage",
    label: "Bricolage Grotesque",
    stack: `"Bricolage Grotesque", ${SANS}`,
    note: "Groovy's typeface: a grotesk with a little wonk.",
  },
  {
    id: "fredoka",
    label: "Fredoka",
    stack: `"Fredoka", ${SANS}`,
    note: "Big, round and bubbly.",
  },
  {
    id: "instrument_serif",
    label: "Instrument Serif",
    stack: `"Instrument Serif", ${SERIF}`,
    note: "The slim, elegant serif all over design sites lately.",
  },
  {
    id: "young_serif",
    label: "Young Serif",
    stack: `"Young Serif", ${SERIF}`,
    note: "A heavy, warm serif with a retro bounce.",
  },
  {
    id: "playfair",
    label: "Playfair",
    stack: `"Playfair", ${SERIF}`,
    note: "High-contrast and classical, newly redrawn.",
  },
  {
    id: "newsreader",
    label: "Newsreader",
    stack: `"Newsreader", ${SERIF}`,
    note: "A serif made for reading on screens.",
  },
  {
    id: "geist_mono",
    label: "Geist Mono",
    stack: `"Geist Mono", ${MONO}`,
    note: "Every letter the same width, like a terminal.",
  },
  {
    id: "caveat",
    label: "Caveat",
    stack: `"Caveat", ${SANS}`,
    note: "Handwritten, like a note on the fridge.",
  },
  {
    id: "pixelify_sans",
    label: "Pixelify Sans",
    stack: `"Pixelify Sans", ${MONO}`,
    note: "Chunky pixels, straight out of an old game.",
  },
  {
    id: "jacquard_24",
    label: "Jacquard 24",
    stack: `"Jacquard 24", ${SERIF}`,
    note: "Pixel blackletter. Spooky; best for Halloween.",
  },
  {
    id: "roboto",
    label: "Roboto",
    stack: `"Roboto", ${SANS}`,
    note: "What most themes use.",
  },
  {
    id: "aileron",
    label: "Aileron",
    stack: `"Aileron", ${SANS}`,
    note: "Liquid Glass's clean Swiss-style sans.",
  },
];

/** Put a typeface (the profile's, else the theme's own pick) over whatever
    the theme's CSS chose, or hand the type back to the theme. Inline on the root, so it outranks every theme rule in
    tokens.css (groovy's, glass's). The clock's --font-clock is left alone. */
export function applyFont(
  id: string | null | undefined,
  root: HTMLElement = document.documentElement,
): void {
  const font = FONTS.find((f) => f.id === id);
  for (const name of ["--font-display", "--font-body"]) {
    if (font) root.style.setProperty(name, font.stack);
    else root.style.removeProperty(name);
  }
}
