// SPDX-License-Identifier: Apache-2.0
import { contrast, ink } from "@pinedaview/tokens";
import { describe, expect, it } from "vitest";

// Every built-in theme's quote-card color (core/src/pineda_web/themes.py).
const CARDS = [
  "#645e54",
  "#a888c4",
  "#e3c6d6",
  "#6e4258",
  "#87b4c3",
  "#563428",
  "#91af82",
  "#b98fb0",
  "#ffd8ea",
  "#e0a020",
  "#dba233",
  "#4e3d63",
  "#2c5462",
  "#3e5535",
  "#6b4a6a",
  "#5a3346",
  "#7a5210",
  "#7a5a1a",
];

describe("quote inks", () => {
  it.each(CARDS)("are readable and distinct on %s", (bg) => {
    const quote = ink(bg, 9, 0.02);
    const by = ink(bg, 4.5, 0.16);
    // 9:1, or as close as black or white gets on a mid-tone card.
    const best = Math.max(contrast("#000000", bg), contrast("#ffffff", bg));
    expect(contrast(quote, bg)).toBeGreaterThanOrEqual(
      Math.min(9, best) - 0.05,
    );
    expect(contrast(by, bg)).toBeGreaterThanOrEqual(4.5);
    expect(by).not.toBe(quote);
  });
});
