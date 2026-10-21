// SPDX-License-Identifier: Apache-2.0
/**
 * Circle mode's geometry (RoundStage): a disc the height of the screen, a
 * chapter ring around its rim, and up to four cards in rows that run out to
 * the rim — the top row, a tall centre row, and the bottom row (split in two
 * for a fourth card). Numbers are fractions of the radius, tuned on the
 * 2560×1600 kiosk prototype (2026-10-14), so any size of screen gets the same
 * face.
 */

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Band extends Rect {
  /** Index into `view.circle`: 0 is the centre, then top, then bottom L→R. */
  slot: number;
  /** Where the card's text goes, relative to the band: the biggest box of
   *  the card's shape that stays inside the circle. */
  box: Rect;
}

/** The chapter ring's width — numerals and hour ticks live here. */
export const RIM = 52 / 800;
/** Half the centre row's height. */
export const CENTRE_H = 0.52;
/** The gap between rows, and between the two bottom cards. */
const GAP = 26 / 800;

/** Where the hour ticks and numerals sit, as a fraction of the radius. */
export function tickRadius(): number {
  return 1 - Math.max(14 / 800, RIM / 2);
}

const chord = (r: number, y: number): number =>
  2 * Math.sqrt(Math.max(0, r * r - y * y));

/**
 * The bands for `count` cards on a disc of `diameter` px. `aspect(slot)` is
 * the card's natural text-block width/height, used to fit its text box.
 */
export function bands(
  count: number,
  diameter: number,
  aspect: (slot: number) => number = () => 2.6,
): Band[] {
  const R = diameter / 2;
  const Ri = R * (1 - RIM);
  const h = CENTRE_H * R;
  const g = GAP * R;
  const out: Band[] = [];
  // ya/yb are measured from the centre; each band is as wide as the circle
  // along its inner edge and runs out to the rim (the disc clips it).
  const add = (slot: number, ya: number, yb: number, split = false): void => {
    const near = ya <= 0 && yb >= 0 ? 0 : Math.min(Math.abs(ya), Math.abs(yb));
    const w = chord(Ri, near);
    const x = R - w / 2;
    const y = R + ya;
    const parts: Rect[] = split
      ? [
          { x, y, w: (w - g) / 2, h: yb - ya },
          { x: x + (w + g) / 2, y, w: (w - g) / 2, h: yb - ya },
        ]
      : [{ x, y, w, h: yb - ya }];
    parts.forEach((rect, i) => {
      const s = slot + i;
      out.push({ ...rect, slot: s, box: contentBox(rect, aspect(s), R, Ri) });
    });
  };
  if (count <= 0) return out;
  if (count === 1) {
    const rect = { x: R - Ri, y: R - Ri, w: 2 * Ri, h: 2 * Ri };
    out.push({ ...rect, slot: 0, box: contentBox(rect, aspect(0), R, Ri) });
  } else if (count === 2) {
    add(0, -Ri, h);
    add(1, h + g, Ri);
  } else {
    add(1, -Ri, -h - g);
    add(0, -h, h);
    add(2, h + g, Ri, count >= 4);
  }
  return out.sort((a, b) => a.slot - b.slot);
}

/**
 * The biggest `aspect`-shaped box inside `band` (disc coordinates) whose
 * corners stay inside the circle of radius `Ri` about (R, R). It hugs the
 * band's inner edge, the side nearest the centre where the band is widest.
 * A band across the middle centres it.
 */
export function contentBox(
  band: Rect,
  aspect: number,
  R: number,
  Ri: number,
): Rect {
  const xa = band.x - R;
  const xb = xa + band.w;
  const ya = band.y - R;
  const yb = ya + band.h;
  const pad = Math.max(R * 0.0225, Math.min(R * 0.06, band.h * 0.07));
  let best: (Rect & { score: number }) | null = null;
  const steps = 80;
  for (let i = 1; i <= steps; i++) {
    const ch = ((band.h - 2 * pad) * i) / steps;
    let y0: number;
    if (ya >= 0) y0 = ya + pad;
    else if (yb <= 0) y0 = yb - pad - ch;
    else y0 = Math.min(Math.max(-ch / 2, ya + pad), yb - pad - ch);
    const worst = Math.max(Math.abs(y0), Math.abs(y0 + ch));
    const r = Ri - pad;
    if (worst >= r) continue;
    const hw = Math.sqrt(r * r - worst * worst);
    const x0 = Math.max(xa + pad, -hw);
    const x1 = Math.min(xb - pad, hw);
    const w = x1 - x0;
    if (w <= 0) continue;
    const score = Math.min(ch, w / aspect);
    if (!best || score > best.score * 1.001)
      best = { score, x: x0 - xa, y: y0 - ya, w, h: ch };
  }
  if (!best)
    return {
      x: pad,
      y: pad,
      w: Math.max(1, band.w - 2 * pad),
      h: Math.max(1, band.h - 2 * pad),
    };
  const { score: _score, ...box } = best;
  return box;
}

/** A card's natural text-block shape (width / height), for its text box. */
export function cardAspect(id: string | undefined): number {
  switch (id) {
    case "photo":
    case "on-this-day":
      return 1.8;
    case "news":
      return 2.4;
    case "moon":
    case "moon-climate":
      return 2.2;
    case "weather":
      return 2.7;
    case "phrase":
    case "affirmation":
      return 2.8;
    default:
      return 2.6;
  }
}
