// SPDX-License-Identifier: Apache-2.0
// The Photo Clock's colour looks (mesh, match, opposite, chrome, print,
// neon): the inks for one photo, from its vivid tint and dominant colours
// (Photo.tint, Photo.colours, both worked out on the server). Bright enough
// to read over a photo; the dark edge in each look does the rest.

export interface Inks {
  /** The photo's own colour, lifted to read as a light ink. */
  main: string;
  /** The colour opposite it on the wheel. */
  opposite: string;
  /** The main colour, deep: an edge or a second print ink. */
  deep: string;
  /** Four colours for the blend: the photo's most different ones, then
      the opposite. */
  mesh: [string, string, string, string];
}

type HSV = [number, number, number];

function toHsv(hex: string): HSV | null {
  const m = /^#([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const n = parseInt(m[1]!, 16);
  const r = (n >> 16) / 255;
  const g = ((n >> 8) & 255) / 255;
  const b = (n & 255) / 255;
  const max = Math.max(r, g, b);
  const d = max - Math.min(r, g, b);
  let h = 0;
  if (d) {
    if (max === r) h = ((g - b) / d + 6) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
  }
  return [h / 6, max ? d / max : 0, max];
}

function toHex([h, s, v]: HSV): string {
  const f = (n: number): number => {
    const k = (n + h * 6) % 6;
    return v - v * s * Math.max(0, Math.min(k, 4 - k, 1));
  };
  return (
    "#" +
    [f(5), f(3), f(1)]
      .map((c) =>
        Math.round(c * 255)
          .toString(16)
          .padStart(2, "0"),
      )
      .join("")
  );
}

const clamp = (x: number, lo: number, hi: number): number =>
  Math.min(hi, Math.max(lo, x));

/** Hue distance, 0–0.5. */
const apart = (a: number, b: number): number => {
  const d = Math.abs(a - b) % 1;
  return Math.min(d, 1 - d);
};

/** The inks for a photo. `base` (a chosen tint) wins over the photo's
    own; with neither, a cool sky blue. */
export function photoInks(
  base: string | null | undefined,
  colours: readonly string[] | null | undefined,
): Inks {
  const own = (colours ?? []).map(toHsv).filter((c): c is HSV => c != null);
  const vivid = [...own].sort((a, b) => b[1] * b[2] - a[1] * a[2]);
  const [h0, s] = toHsv(base ?? "") ?? vivid[0] ?? [0.56, 0.45, 1];
  const grey = s < 0.08; // black and white: soft, cool inks
  const h = grey ? 0.56 : h0;
  const ss = grey ? 0.25 : clamp(s, 0.45, 0.75);
  const main = toHex([h, ss, 0.97]);
  const opposite = toHex([(h + 0.5) % 1, grey ? 0.3 : clamp(s, 0.5, 0.8), 1]);
  const deep = toHex([h, grey ? 0.2 : 0.7, 0.35]);
  // The blend: the main hue, then the photo's colours furthest from what's
  // already in, lifted like the main; too few, and neighbours fill in.
  const hues = [h];
  for (const c of vivid) {
    if (hues.length >= 3) break;
    if (c[1] < 0.15) continue;
    if (hues.every((x) => apart(x, c[0]) > 0.06)) hues.push(c[0]);
  }
  for (const step of [0.08, -0.08])
    if (hues.length < 3) hues.push((h + step + 1) % 1);
  const mesh = hues.map((x) => toHex([x, ss, 0.97])) as [
    string,
    string,
    string,
  ];
  return { main, opposite, deep, mesh: [...mesh, opposite] };
}
