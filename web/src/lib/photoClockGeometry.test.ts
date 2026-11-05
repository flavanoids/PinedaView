// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import {
  covered,
  easeOut,
  figuresCovered,
  fit,
  HEAD_AT,
  lumaIn,
  maskFrom,
  type Mask,
} from "./photoClockGeometry";

/** A w × h mask with the subject filling the given cells. */
function mask(
  w: number,
  h: number,
  on: (x: number, y: number) => boolean,
): Mask {
  const rgba = new Uint8Array(w * h * 4);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) rgba[(y * w + x) * 4 + 3] = on(x, y) ? 255 : 0;
  return maskFrom(rgba, w, h);
}

describe("maskFrom", () => {
  it("finds the subject's top and the middle of its width", () => {
    const m = mask(100, 100, (x, y) => x >= 60 && x < 80 && y >= 30);
    expect(m.top).toBeCloseTo(0.3);
    expect(m.mid).toBeCloseTo(0.7);
  });

  it("an empty cutout stands in the middle, its top at the bottom", () => {
    const m = mask(10, 10, () => false);
    expect(m.top).toBe(1);
    expect(m.mid).toBe(0.5);
  });
});

describe("fit", () => {
  it("slides a tall photo's crop so the subject's top lands at HEAD_AT", () => {
    // A portrait photo on a wide screen: plenty to crop off top and bottom.
    const m = mask(100, 200, (_x, y) => y >= 120);
    const { scale, y } = fit(m, 1000, 500);
    expect(scale).toBe(10);
    expect(0.6 * 200 * scale + y).toBeCloseTo(HEAD_AT * 500);
  });

  it("centres the subject across when the photo is wider than the screen", () => {
    const m = mask(200, 100, (x) => x >= 150 && x < 170);
    const { scale, x, pos } = fit(m, 500, 1000);
    expect(0.8 * 200 * scale + x).toBeCloseTo(250);
    expect(pos.endsWith("50%")).toBe(true);
  });
});

describe("covered", () => {
  it("is the share of the box the subject fills", () => {
    const m = mask(100, 100, (x) => x < 50);
    const box = { left: 0, top: 0, width: 100, height: 100 };
    expect(covered(m, 100, 100, box, 1)).toBeCloseTo(0.5);
  });
});

describe("figuresCovered", () => {
  const m = mask(100, 100, (x) => x < 20);
  const box = { left: 0, top: 0, width: 100, height: 100 };

  it("rates the worst digit, not the colon", () => {
    // Five cells of 20 px: the subject fills the first ("1") alone.
    const r = figuresCovered(m, 100, 100, box, "12:34");
    expect(r.worst).toBeCloseTo(1);
    expect(r.all).toBeCloseTo(0.2, 1);
  });

  it("stacked, the time is four cells, two rows of two", () => {
    const r = figuresCovered(m, 100, 100, box, "12\n34");
    expect(r.worst).toBeCloseTo(0.4, 1);
    expect(r.all).toBeCloseTo(0.2, 1);
  });

  it("ignores a subject over the colon", () => {
    const colon = mask(100, 100, (x) => x >= 40 && x < 60);
    const r = figuresCovered(colon, 100, 100, box, "12:34");
    expect(r.worst).toBe(0);
  });
});

describe("lumaIn", () => {
  it("is bright and calm over a flat white box, busy over stripes", () => {
    const w = 10;
    const flat = { w, h: w, L: new Float32Array(w * w).fill(1) };
    const box = { left: 0, top: 0, width: 100, height: 100 };
    expect(lumaIn(flat, 100, 100, box)).toEqual({ luma: 1, busy: 0 });
    const stripes = {
      w,
      h: w,
      L: Float32Array.from({ length: w * w }, (_, k) => k % 2),
    };
    expect(lumaIn(stripes, 100, 100, box).busy).toBeGreaterThan(0.5);
  });
});

describe("easeOut", () => {
  it("runs from 0 to 1, ahead of linear", () => {
    expect(easeOut(0)).toBeCloseTo(0);
    expect(easeOut(1)).toBeCloseTo(1);
    expect(easeOut(0.5)).toBeGreaterThan(0.5);
  });
});
