// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import {
  contrastRatio,
  DARK_INK,
  generateHarmoniousPalette,
  generateNightTwin,
  hexToHsv,
  hsvToHex,
  inkFor,
  isValidHex,
  LIGHT_INK,
  luminance,
  shade,
} from "./themeHelpers";

describe("themeHelpers", () => {
  it("validates hex color strings", () => {
    expect(isValidHex("#ffffff")).toBe(true);
    expect(isValidHex("#000000")).toBe(true);
    expect(isValidHex("#12ab34")).toBe(true);
    expect(isValidHex("12ab34")).toBe(false);
    expect(isValidHex("#fff")).toBe(false);
    expect(isValidHex("invalid")).toBe(false);
  });

  it("calculates relative luminance consistently", () => {
    expect(luminance("#000000")).toBeCloseTo(0, 3);
    expect(luminance("#ffffff")).toBeCloseTo(1, 3);
    expect(luminance("#808080")).toBeGreaterThan(0.2);
    expect(luminance("#808080")).toBeLessThan(0.3);
  });

  it("computes ink_for exactly matching server logic", () => {
    expect(inkFor("#000000")).toBe(LIGHT_INK);
    expect(inkFor("#ffffff")).toBe(DARK_INK);
    expect(inkFor("#f3d9d2", "#e8aebe")).toBe(DARK_INK);
  });

  it("computes WCAG contrast ratio", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 0);
    expect(contrastRatio("#000000", "#000000")).toBeCloseTo(1, 1);
  });

  it("shades colors correctly", () => {
    expect(shade("#808080", 0.5)).toBe("#404040");
    expect(shade("#102030", 2.0)).toBe("#204060");
  });

  it("converts hex to hsv and back cleanly", () => {
    const orig = "#d84882";
    const hsv = hexToHsv(orig);
    const roundtrip = hsvToHex(hsv.h, hsv.s, hsv.v);
    expect(roundtrip.toLowerCase()).toBe(orig.toLowerCase());
  });

  it("generates harmonious palettes with valid hex colors", () => {
    const palette = generateHarmoniousPalette(
      "#2e4057",
      "analogous",
      "Oceanic",
    );
    expect(palette.label).toBe("Oceanic");
    expect(isValidHex(palette.stage)).toBe(true);
    expect(isValidHex(palette.accent)).toBe(true);
    expect(isValidHex(palette.weather)).toBe(true);
    expect(isValidHex(palette.clock)).toBe(true);
    expect(isValidHex(palette.affirmation)).toBe(true);
  });

  it("generates night twin variants that are darker than daytime", () => {
    const day = generateHarmoniousPalette("#e8f0f5", "monochromatic", "Day");
    const night = generateNightTwin(day);
    expect(night.label).toContain("(Night)");
    expect(luminance(night.stage)).toBeLessThan(luminance(day.stage));
    expect(luminance(night.weather)).toBeLessThan(luminance(day.weather));
  });
});
