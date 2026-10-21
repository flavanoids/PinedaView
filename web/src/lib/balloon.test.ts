// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { backIn, deflate, inflate, spring } from "./balloon";

describe("balloon", () => {
  it("inflates from small, swells past full size, and settles at 1", () => {
    expect(spring(0, 0.1)).toBeCloseTo(0.1);
    const peak = Math.max(
      ...Array.from({ length: 100 }, (_, i) => spring(i / 100, 0.1)),
    );
    expect(peak).toBeGreaterThan(1.03);
    expect(peak).toBeLessThan(1.12);
    expect(spring(1, 0.1)).toBeCloseTo(1, 2);
  });

  it("lets the height trail the width", () => {
    expect(spring(0.05, 0.1, 0.06)).toBeCloseTo(0.1);
    expect(spring(0.05, 0.1)).toBeGreaterThan(0.1);
  });

  it("puffs up a little before it shrinks away", () => {
    expect(backIn(0)).toBe(0);
    expect(backIn(0.2)).toBeLessThan(0);
    expect(backIn(1)).toBeCloseTo(1);
  });

  it("starts and ends in the corner, square when full", () => {
    const grow = inflate(document.body);
    expect(grow.duration).toBeGreaterThanOrEqual(1000);
    expect(grow.duration).toBeLessThanOrEqual(2000);
    expect(grow.css(0)).toContain("scale(0.1000, 0.1200)");
    expect(grow.css(1)).toMatch(/scale\(1\.00\d\d, 1\.0\d\d\d\)/);
    expect(grow.css(1)).toContain("border-radius: 0.0px / 0.0px");
    expect(grow.css(0)).toContain("transform-origin: calc(100% - 3vmin)");
    const shrink = deflate(document.body);
    expect(shrink.css(1)).toContain("scale(1.0000, 1.0000)");
    expect(shrink.css(0)).toContain("scale(0.1000, 0.1200)");
  });
});
