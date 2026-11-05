// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { chooseLayout, letterRange } from "./collage";

const LANDSCAPE = 2048 / 1150;

function cells(areas: string[]): string[][] {
  return areas.map((r) => r.replaceAll('"', "").split(" "));
}

/** Every named area is one filled rectangle. */
function assertRectangles(areas: string[]): void {
  const at = new Map<string, [number, number][]>();
  cells(areas).forEach((row, r) =>
    row.forEach((name, c) => at.set(name, [...(at.get(name) ?? []), [r, c]])),
  );
  for (const spots of at.values()) {
    const rs = spots.map(([r]) => r);
    const cs = spots.map(([, c]) => c);
    const h = Math.max(...rs) - Math.min(...rs) + 1;
    const w = Math.max(...cs) - Math.min(...cs) + 1;
    expect(spots).toHaveLength(w * h);
  }
}

describe("chooseLayout", () => {
  it.each([1, 2, 3, 4, 5, 6, 7, 8])(
    "fills the box with %i pictures, one slot each",
    (n) => {
      const layout = chooseLayout(Array(n).fill(1.5), LANDSCAPE);
      assertRectangles(layout.areas);
      const used = new Set(cells(layout.areas).flat());
      expect(used.size).toBe(n);
      expect(new Set(layout.slots)).toEqual(used);
    },
  );

  it("gives the first picture the biggest tile", () => {
    const layout = chooseLayout([0.6, 1.5, 1.5, 1.5, 1.5, 1.5], LANDSCAPE);
    const grid = cells(layout.areas).flat();
    const count = (name: string | undefined) =>
      grid.filter((c) => c === name).length;
    const hero = count(layout.slots[0]);
    for (const s of layout.slots.slice(1)) expect(count(s)).toBeLessThan(hero);
  });

  it("puts tall pictures in tall tiles and wide ones in wide tiles", () => {
    const layout = chooseLayout([1.5, 0.6, 1.5, 3, 1.5, 0.6], LANDSCAPE);
    const grid = cells(layout.areas);
    const shape = (name: string | undefined) => {
      const rs = new Set<number>();
      const cs = new Set<number>();
      grid.forEach((row, r) =>
        row.forEach((n, c) => {
          if (n === name) {
            rs.add(r);
            cs.add(c);
          }
        }),
      );
      return cs.size / rs.size;
    };
    expect(shape(layout.slots[1])).toBeLessThan(1);
    expect(shape(layout.slots[5])).toBeLessThan(1);
    expect(shape(layout.slots[3])).toBeGreaterThan(1);
  });

  it("reads A, B, C… left to right, top down when shapes don't decide", () => {
    const layout = chooseLayout(Array(6).fill(1.5), LANDSCAPE);
    const grid = cells(layout.areas);
    const firstSeen = grid.flat().filter((n, i, all) => all.indexOf(n) === i);
    expect(layout.slots).toEqual(firstSeen);
  });

  it("turns the templates on their side for a portrait screen", () => {
    // Landscape photos on a tall screen: the 4x3 templates' tiles would be
    // half as wide as they are tall, so the 3x4 transposes win.
    const layout = chooseLayout(Array(6).fill(1.5), 1080 / 1800);
    expect(layout.rows).toBeGreaterThan(layout.cols);
  });

  it("copes with missing aspects and more than eight pictures", () => {
    const layout = chooseLayout([0, NaN, 1, 1, 1, 1, 1, 1, 1, 1], LANDSCAPE);
    expect(layout.slots).toHaveLength(10);
    expect(layout.slots.slice(8)).toEqual(["", ""]);
    expect(chooseLayout([], LANDSCAPE).slots).toEqual([]);
  });
});

describe("letterRange", () => {
  it("reads the letters on screen", () => {
    expect(letterRange(["A"])).toBe("A");
    expect(letterRange(["A", "B"])).toBe("A and B");
    expect(letterRange(["A", "B", "C", "D", "E", "F"])).toBe("A–F");
    expect(letterRange(["A", "C", "D"])).toBe("A, C and D");
  });
});
