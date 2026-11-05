// SPDX-License-Identifier: Apache-2.0
// The Photo Clock's geometry: where a photo's subject lands on screen once
// it's cropped to cover, how much of a box (the time's figures, a corner
// for the date) the subject would hide, and how bright and busy a box of
// the photo is. Pure maths on coarse grids, so it can be tested apart from
// the component.

/** A coarse alpha mask of a cutout: where the subject is, and the top of
    it (as a fraction of the photo's height). */
export interface Mask {
  w: number;
  h: number;
  alpha: Uint8Array;
  top: number;
  /** The middle of the subject's width, 0–1 across the photo. */
  mid: number;
}

/** A slot's photo as a small grid of brightness (0–1), cropped and laid
    out as the screen shows it. */
export interface Luma {
  w: number;
  h: number;
  L: Float32Array;
}

/** A box on screen, px. */
export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Where the subject's top should land, as a fraction of the screen
    height: low enough to leave the time some sky, high enough that heads
    overlap the figures. */
export const HEAD_AT = 0.24;

/** A mask from a cutout's RGBA pixels: on where alpha is over half. */
export function maskFrom(rgba: ArrayLike<number>, w: number, h: number): Mask {
  const alpha = new Uint8Array(w * h);
  let top = 1;
  const cols = new Uint32Array(w);
  for (let y = 0; y < h; y++) {
    let row = 0;
    for (let x = 0; x < w; x++) {
      const on = (rgba[(y * w + x) * 4 + 3] ?? 0) > 127 ? 1 : 0;
      alpha[y * w + x] = on;
      row += on;
      cols[x]! += on;
    }
    if (top === 1 && row > w * 0.02) top = y / h;
  }
  // The subject's sides: the outermost columns it really fills, so a
  // stray speck doesn't widen it.
  const first = cols.findIndex((n) => n > h * 0.02);
  const last = w - 1 - [...cols].reverse().findIndex((n) => n > h * 0.02);
  const mid = first < 0 ? 0.5 : (first + last + 1) / 2 / w;
  return { w, h, alpha, top, mid };
}

/** object-fit: cover's scale and offset for a mask in a `width` × `height`
    box, with the crop slid down or up so the subject's top sits at HEAD_AT,
    and across so the subject stands in the middle (a wide photo on a tall
    screen loses most of its width). */
export function fit(m: Mask, width: number, height: number) {
  const scale = Math.max(width / m.w, height / m.h);
  const spare = m.h * scale - height; // px cropped off vertically
  const want = m.top * m.h * scale - HEAD_AT * height;
  const dy = spare > 0 ? Math.min(Math.max(want, 0), spare) : spare / 2;
  const spareX = m.w * scale - width; // px cropped off across
  const wantX = m.mid * m.w * scale - width / 2;
  const dx = spareX > 0 ? Math.min(Math.max(wantX, 0), spareX) : spareX / 2;
  const px = spareX > 0 ? (dx / spareX) * 100 : 50;
  const py = spare > 0 ? (dy / spare) * 100 : 50;
  return { scale, x: -dx, y: -dy, pos: `${px}% ${py}%` };
}

/** The share of a screen box the subject covers, sampled every `step` px. */
export function covered(
  m: Mask,
  width: number,
  height: number,
  b: Box,
  step = 8,
): number {
  const { scale, x, y } = fit(m, width, height);
  let on = 0;
  let all = 0;
  for (let cy = b.top; cy < b.top + b.height; cy += step) {
    for (let cx = b.left; cx < b.left + b.width; cx += step) {
      const mx = Math.floor((cx - x) / scale);
      const my = Math.floor((cy - y) / scale);
      all++;
      if (mx >= 0 && my >= 0 && mx < m.w && my < m.h)
        on += m.alpha[my * m.w + mx] ?? 0;
    }
  }
  return all ? on / all : 0;
}

/** How much of the time's figures in box `b` the subject would hide: the
    share of the whole box, and of the worst-covered character in it. One
    digit gone (a shoe over the "3") makes the time unreadable even when the
    box as a whole is mostly clear. `chars` is the time as drawn: "10:41",
    or "10\n41" stacked (four cells, two rows of two). */
export function figuresCovered(
  m: Mask,
  width: number,
  height: number,
  b: Box,
  chars: string,
): { all: number; worst: number } {
  const { scale, x, y } = fit(m, width, height);
  const isStack = chars.includes("\n");
  const cells = isStack ? 4 : chars.length;
  const on = new Array<number>(cells).fill(0);
  const all = new Array<number>(cells).fill(0);
  const step = Math.max(8, Math.round(scale));
  const midY = b.top + b.height / 2;
  for (let cy = b.top; cy < b.top + b.height; cy += step) {
    for (let cx = b.left; cx < b.left + b.width; cx += step) {
      const across = (cx - b.left) / b.width;
      const cell = isStack
        ? (cy < midY ? 0 : 2) + Math.min(1, Math.floor(across * 2))
        : Math.min(cells - 1, Math.floor(across * cells));
      const mx = Math.floor((cx - x) / scale);
      const my = Math.floor((cy - y) / scale);
      all[cell] = (all[cell] ?? 0) + 1;
      if (mx >= 0 && my >= 0 && mx < m.w && my < m.h)
        on[cell] = (on[cell] ?? 0) + (m.alpha[my * m.w + mx] ?? 0);
    }
  }
  const total = all.reduce((a, b) => a + b, 0);
  let worst = 0;
  all.forEach((n, i) => {
    if (n && (isStack || chars[i] !== ":"))
      worst = Math.max(worst, (on[i] ?? 0) / n);
  });
  return {
    all: total ? on.reduce((a, b) => a + b, 0) / total : 0,
    worst,
  };
}

/** A screen box's mean brightness, and how busy it is: the mean step
    between neighbouring cells, which is low for sky and wall and high for
    leaves, crowds and brickwork. */
export function lumaIn(lm: Luma, width: number, height: number, b: Box) {
  const sx = lm.w / width;
  const sy = lm.h / height;
  const x0 = Math.min(lm.w - 1, Math.max(0, Math.floor(b.left * sx)));
  const y0 = Math.min(lm.h - 1, Math.max(0, Math.floor(b.top * sy)));
  const x1 = Math.min(
    lm.w,
    Math.max(x0 + 1, Math.ceil((b.left + b.width) * sx)),
  );
  const y1 = Math.min(
    lm.h,
    Math.max(y0 + 1, Math.ceil((b.top + b.height) * sy)),
  );
  let sum = 0;
  let busy = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const v = lm.L[y * lm.w + x]!;
      sum += v;
      busy +=
        Math.abs(v - lm.L[y * lm.w + Math.min(x + 1, lm.w - 1)]!) +
        Math.abs(v - lm.L[Math.min(y + 1, lm.h - 1) * lm.w + x]!);
    }
  }
  const n = (x1 - x0) * (y1 - y0);
  return { luma: sum / n, busy: busy / n };
}

/** CSS's ease-out, for following the drift's keyframes. */
export function easeOut(x: number): number {
  const bez = (t: number, p1: number, p2: number) =>
    3 * p1 * t * (1 - t) ** 2 + 3 * p2 * t * t * (1 - t) + t ** 3;
  let lo = 0;
  let hi = 1;
  for (let k = 0; k < 18; k++) {
    const m = (lo + hi) / 2;
    if (bez(m, 0, 0.58) < x) lo = m;
    else hi = m;
  }
  return bez((lo + hi) / 2, 0, 1);
}
