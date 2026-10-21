// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { glareOf, gloomOf, LOOKS } from "./glass";

describe("glass contrast response (glare and gloom)", () => {
  it("computes glare for bright backgrounds above mid-luma", () => {
    expect(glareOf(0.45)).toBe(0);
    expect(glareOf(0.3)).toBe(0);
    expect(glareOf(0.8)).toBe(1);
    expect(glareOf(1.0)).toBe(1);

    // Smoothstep curve between 0.45 and 0.80
    const mid = glareOf(0.625);
    expect(mid).toBeGreaterThan(0.4);
    expect(mid).toBeLessThan(0.6);
  });

  it("computes gloom for dark backgrounds below mid-luma", () => {
    expect(gloomOf(0.45)).toBe(0);
    expect(gloomOf(0.7)).toBe(0);
    expect(gloomOf(0.1)).toBe(1);
    expect(gloomOf(0.0)).toBe(1);

    // Smoothstep curve between 0.45 and 0.10
    const mid = gloomOf(0.275);
    expect(mid).toBeGreaterThan(0.4);
    expect(mid).toBeLessThan(0.6);
  });

  it("has complementary glare and gloom transitions", () => {
    // Exactly at threshold 0.45, both glare and gloom are zero
    expect(glareOf(0.45)).toBe(0);
    expect(gloomOf(0.45)).toBe(0);

    // When glare > 0, gloom must be 0
    expect(glareOf(0.6)).toBeGreaterThan(0);
    expect(gloomOf(0.6)).toBe(0);

    // When gloom > 0, glare must be 0
    expect(gloomOf(0.2)).toBeGreaterThan(0);
    expect(glareOf(0.2)).toBe(0);
  });
});

describe("LOOKS liquid parameters", () => {
  it("has tight specular and chamfered rim exponent for crisp optical look", () => {
    expect(LOOKS.liquid.specPow).toBeGreaterThanOrEqual(64);
    expect(LOOKS.liquid.rimPow).toBeGreaterThanOrEqual(3.5);
  });
});
