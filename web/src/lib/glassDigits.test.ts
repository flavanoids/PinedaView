// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { liquidEase } from "./glassDigits";

describe("the minute's melt", () => {
  it("starts at the old figures and settles exactly on the new", () => {
    expect(liquidEase(0)).toBeCloseTo(0);
    expect(liquidEase(1)).toBe(1);
    expect(liquidEase(0.5)).toBeCloseTo(0.5);
  });

  it("draws back a touch first and overshoots a touch before settling", () => {
    expect(liquidEase(0.1)).toBeLessThan(0);
    expect(liquidEase(0.9)).toBeGreaterThan(1);
    expect(liquidEase(0.9)).toBeLessThan(1.06);
  });
});
