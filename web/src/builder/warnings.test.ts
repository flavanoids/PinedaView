// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import type { Grid } from "../lib/grid";
import { layoutWarnings } from "./warnings";

const tv = { width: 1920, height: 1080, fills: true };
const name = (c: string) => c;

describe("layoutWarnings", () => {
  it("is quiet for a sensible layout", () => {
    const grid: Grid = {
      cols: 8,
      items: [
        { card: "photo", x: 0, y: 0, w: 4, h: 4 },
        { card: "clock", x: 4, y: 0, w: 4, h: 4 },
      ],
    };
    expect(layoutWarnings(grid, tv, name)).toEqual([]);
  });

  it("stops on a missing photo card (the QR lives there)", () => {
    const grid: Grid = {
      cols: 8,
      items: [{ card: "clock", x: 0, y: 0, w: 8, h: 4 }],
    };
    expect(layoutWarnings(grid, tv, name)[0]?.level).toBe("stop");
  });

  it("lets any other screen go without the photo", () => {
    const grid: Grid = {
      cols: 2,
      items: [{ card: "clock", x: 0, y: 0, w: 2, h: 2 }],
    };
    expect(layoutWarnings(grid, tv, name, false)).toEqual([]);
  });

  it("stops on an empty layout", () => {
    expect(layoutWarnings({ cols: 8, items: [] }, tv, name)).toHaveLength(1);
  });

  it("flags a tiny photo and squished cards", () => {
    const items = [
      { card: "photo", x: 0, y: 0, w: 1, h: 1 },
      ...Array.from({ length: 12 }, (_, i) => ({
        card: `c${i}`,
        x: 0,
        y: i + 1,
        w: 8,
        h: 1,
      })),
    ];
    const warnings = layoutWarnings({ cols: 8, items }, tv, name);
    expect(warnings.some((w) => w.card === "photo" && w.level === "stop")).toBe(
      true,
    );
    expect(
      warnings.some((w) => w.card === "c0" && w.text.includes("very short")),
    ).toBe(true);
  });

  it("skips size checks when the screen hasn't reported its size", () => {
    const grid: Grid = {
      cols: 8,
      items: [{ card: "photo", x: 0, y: 0, w: 1, h: 1 }],
    };
    expect(
      layoutWarnings(grid, { width: null, height: null, fills: false }, name),
    ).toEqual([]);
  });
});
