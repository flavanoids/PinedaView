// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { bands, RIM, type Band } from "./round";

const D = 1600;
const R = D / 2;
const Ri = R * (1 - RIM);

function corners(b: Band): [number, number][] {
  const x = b.x + b.box.x;
  const y = b.y + b.box.y;
  return [
    [x, y],
    [x + b.box.w, y],
    [x, y + b.box.h],
    [x + b.box.w, y + b.box.h],
  ];
}

describe("bands", () => {
  it("makes one band per card, in slot order", () => {
    for (const n of [1, 2, 3, 4]) {
      expect(bands(n, D).map((b) => b.slot)).toEqual([...Array(n).keys()]);
    }
    expect(bands(0, D)).toEqual([]);
  });

  it("keeps every text box inside the circle and inside its band", () => {
    for (const n of [1, 2, 3, 4]) {
      for (const b of bands(n, D)) {
        for (const [x, y] of corners(b)) {
          expect(Math.hypot(x - R, y - R)).toBeLessThanOrEqual(Ri + 0.01);
        }
        expect(b.box.x).toBeGreaterThanOrEqual(0);
        expect(b.box.y).toBeGreaterThanOrEqual(0);
        expect(b.box.x + b.box.w).toBeLessThanOrEqual(b.w + 0.01);
        expect(b.box.y + b.box.h).toBeLessThanOrEqual(b.h + 0.01);
      }
    }
  });

  it("never overlaps two bands", () => {
    for (const n of [2, 3, 4]) {
      const list = bands(n, D);
      for (const a of list)
        for (const b of list) {
          if (a === b) continue;
          const apart =
            a.x + a.w <= b.x + 0.01 ||
            b.x + b.w <= a.x + 0.01 ||
            a.y + a.h <= b.y + 0.01 ||
            b.y + b.h <= a.y + 0.01;
          expect(apart).toBe(true);
        }
    }
  });

  it("puts the centre card over the hub", () => {
    for (const n of [1, 2, 3, 4]) {
      const centre = bands(n, D)[0]!;
      expect(centre.y).toBeLessThan(R);
      expect(centre.y + centre.h).toBeGreaterThan(R);
    }
  });

  it("scales with the screen", () => {
    const small = bands(4, 400);
    const big = bands(4, 1600);
    big.forEach((b, i) => {
      expect(small[i]!.w * 4).toBeCloseTo(b.w, 6);
      expect(small[i]!.box.h * 4).toBeCloseTo(b.box.h, 0);
    });
  });
});
