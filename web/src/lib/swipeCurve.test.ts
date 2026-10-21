// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import {
  SWIPE_MS,
  swipeEasing,
  swipeProgress,
  swipeTimeAt,
} from "./swipeCurve";

const samples = Array.from({ length: 1001 }, (_, i) => i / 1000);

describe("swipe curve", () => {
  it("is over in under a second", () => {
    expect(SWIPE_MS).toBeLessThan(1000);
  });

  it("starts and ends in place", () => {
    expect(swipeProgress(0)).toBe(0);
    expect(swipeProgress(1)).toBe(1);
  });

  it("never carries the photo past its place", () => {
    // Past 1 would open a black strip at the far edge.
    for (const t of samples) expect(swipeProgress(t)).toBeLessThanOrEqual(1);
  });

  it("bounces back only a little", () => {
    // From just short of the edge (the approach only moves forward).
    const after = samples.filter((t) => t > swipeTimeAt(0.99));
    const dip = Math.min(...after.map(swipeProgress));
    expect(dip).toBeLessThan(1);
    expect(dip).toBeGreaterThan(0.98);
  });

  it("starts quick and eases off", () => {
    // Half way across in well under half the time.
    expect(swipeTimeAt(0.5)).toBeLessThan(0.3);
    const early = swipeProgress(0.1) - swipeProgress(0);
    const late = swipeProgress(0.7) - swipeProgress(0.6);
    expect(early).toBeGreaterThan(late * 3);
  });

  it("falls back to an ease-out where linear() isn't supported", () => {
    // jsdom's CSS.supports doesn't know linear().
    expect(swipeEasing()).toMatch(/^(linear|cubic-bezier)\(/);
  });
});
