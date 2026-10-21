// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import {
  addBrick,
  fromStack,
  heroItem,
  overlaps,
  pack,
  removeBrick,
  setSize,
  shift,
  swap,
  toBricks,
  trailingSpan,
  type Bricks,
  type Grid,
  type GridItem,
} from "./grid";

const box = (card: string, x: number, y: number, w = 2, h = 2): GridItem => ({
  card,
  x,
  y,
  w,
  h,
});
const at = (g: Grid, card: string) => g.items.find((i) => i.card === card);
const noOverlaps = (g: Grid) =>
  g.items.every((a, i) => g.items.slice(0, i).every((b) => !overlaps(a, b)));

// The wide screen: 4 cells across, a 2×2 Large card.
const wide = (over: Partial<Bricks> = {}): Bricks => ({
  cells: 4,
  heroW: 2,
  heroH: 2,
  hero: "photo",
  side: "left",
  pieces: [
    { card: "clock", size: "s" },
    { card: "moon", size: "s" },
    { card: "phrase", size: "s" },
    { card: "weather", size: "s" },
  ],
  ...over,
});

describe("pack", () => {
  it("reproduces the automatic wide layout at double resolution", () => {
    const g = pack(wide());
    expect(g.cols).toBe(8);
    expect(at(g, "photo")).toMatchObject({ x: 0, y: 0, w: 4, h: 4 });
    expect(at(g, "clock")).toMatchObject({ x: 4, y: 0, w: 2, h: 2 });
    expect(at(g, "moon")).toMatchObject({ x: 6, y: 0 });
    expect(at(g, "phrase")).toMatchObject({ x: 4, y: 2 });
    expect(at(g, "weather")).toMatchObject({ x: 6, y: 2 });
    expect(noOverlaps(g)).toBe(true);
  });

  it("pins the Large card to the right", () => {
    const g = pack(wide({ side: "right" }));
    expect(at(g, "photo")).toMatchObject({ x: 4, y: 0 });
    expect(at(g, "clock")).toMatchObject({ x: 0, y: 0 });
  });

  it("clicks a Medium into the first spot two cells wide", () => {
    const g = pack(
      wide({
        pieces: [
          { card: "clock", size: "s" },
          { card: "moon", size: "m" },
          { card: "phrase", size: "s" },
        ],
      }),
    );
    // The Medium doesn't fit beside the clock, so it drops a row; the next
    // Small fills the gap it left.
    expect(at(g, "moon")).toMatchObject({ x: 4, y: 2, w: 4 });
    expect(at(g, "phrase")).toMatchObject({ x: 6, y: 0 });
    expect(noOverlaps(g)).toBe(true);
  });

  it("keeps a Medium to the screen width on a one-column screen", () => {
    const g = pack({
      cells: 1,
      heroW: 1,
      heroH: 2,
      hero: null,
      side: "left",
      pieces: [{ card: "a", size: "m" }],
    });
    expect(at(g, "a")).toMatchObject({ w: 2 });
  });
});

describe("toBricks", () => {
  it("reads a packed layout back the same", () => {
    const b = wide({
      side: "right",
      pieces: [
        { card: "clock", size: "m" },
        { card: "moon", size: "s" },
      ],
    });
    expect(toBricks(pack(b), 2, 2)).toEqual(b);
  });

  it("has no Large card when every box is one cell tall", () => {
    const b = toBricks({ cols: 8, items: [box("a", 0, 0, 4, 2)] }, 2, 2);
    expect(b.hero).toBeNull();
    expect(b.pieces).toEqual([{ card: "a", size: "m" }]);
  });
});

describe("setSize", () => {
  it("making a card Large sends the old Large card to its spot", () => {
    const b = setSize(wide(), "moon", "l");
    expect(b.hero).toBe("moon");
    expect(b.pieces[1]).toEqual({ card: "photo", size: "s" });
  });

  it("shrinking the Large card leaves none, and it goes first", () => {
    const b = setSize(wide(), "photo", "m");
    expect(b.hero).toBeNull();
    expect(b.pieces[0]).toEqual({ card: "photo", size: "m" });
  });
});

describe("swap / shift", () => {
  it("trades cards between spots without changing the shape", () => {
    const before = wide({
      pieces: [
        { card: "clock", size: "m" },
        { card: "moon", size: "s" },
      ],
    });
    const b = swap(before, "photo", "moon");
    expect(b.hero).toBe("moon");
    expect(b.pieces[1]).toEqual({ card: "photo", size: "s" });
    expect(b.pieces[0]).toEqual({ card: "clock", size: "m" });
  });

  it("moves a brick along the fill order, stopping at the ends", () => {
    expect(shift(wide(), "moon", -1).pieces[0]?.card).toBe("moon");
    expect(shift(wide(), "clock", -1)).toEqual(wide());
  });
});

describe("add / remove", () => {
  it("adds a Small at the end, once", () => {
    const b = addBrick(wide(), "radar");
    expect(b.pieces.at(-1)).toEqual({ card: "radar", size: "s" });
    expect(addBrick(b, "radar")).toBe(b);
  });

  it("removing the Large card leaves none", () => {
    expect(removeBrick(wide(), "photo").hero).toBeNull();
    expect(removeBrick(wide(), "moon").pieces).toHaveLength(3);
  });
});

describe("heroItem", () => {
  it("is the biggest box, first in reading order on a tie", () => {
    expect(heroItem([box("a", 0, 0), box("b", 2, 0)])?.card).toBe("a");
    expect(heroItem([box("a", 0, 0, 1, 1), box("b", 1, 0, 3, 3)])?.card).toBe(
      "b",
    );
  });
});

describe("fromStack", () => {
  it("starts from the automatic layout: hero Large, the rest Small", () => {
    const b = fromStack(["clock", "photo", "moon"], "photo", 4, 2, 2);
    expect(b.hero).toBe("photo");
    expect(b.pieces.map((p) => p.card)).toEqual(["clock", "moon"]);
    expect(b.pieces.every((p) => p.size === "s")).toBe(true);
  });
});

describe("trailingSpan", () => {
  it("stretches a lone last card across the rest of its row", () => {
    // 4 columns, 2×2 hero: 4 cards beside it, then 1 alone → spans 4.
    expect(trailingSpan(4, 2, 2, 5)).toBe(4);
    expect(trailingSpan(4, 2, 2, 7)).toBe(2);
  });
  it("leaves full rows and single columns alone", () => {
    expect(trailingSpan(4, 2, 2, 8)).toBe(1);
    expect(trailingSpan(1, 1, 1, 5)).toBe(1);
    expect(trailingSpan(4, 2, 2, 0)).toBe(1);
  });
});
