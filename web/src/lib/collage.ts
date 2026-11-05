// SPDX-License-Identifier: Apache-2.0
// Layout for the image search collage: which tile each picture gets.
//
// The collage always fills the screen exactly — no ragged last row — so it
// picks from a few hand-made templates for the number of pictures, laid
// out on a small grid. Each template is also tried transposed (for a
// portrait screen). The first picture, the search's best, always takes the
// biggest tile; the rest go where their shape is cropped least, weighted by
// tile size, so a tall photo lands in a tall tile and a panorama in a wide
// one.

export interface Layout {
  /** CSS grid-template-areas rows, e.g. ['"a a b"', '"a a c"']. */
  areas: string[];
  cols: number;
  rows: number;
  /** The grid area name for each picture, in input order. */
  slots: string[];
}

// Rows of slot names; "a" is always the biggest.
const TEMPLATES: Record<number, string[][]> = {
  1: [["a"]],
  2: [["a b"], ["a a b"]],
  3: [["a a b", "a a c"], ["a b c"], ["a a", "b c"]],
  4: [
    ["a a b", "a a c", "a a d"],
    ["a a b c", "a a d d"],
    ["a a b", "a a c", "d d c"],
  ],
  5: [
    ["a a b c", "a a d e"],
    ["a a b", "a a c", "d e c"],
    ["a a b b", "a a c d", "e e c d"],
  ],
  6: [
    ["a a b c", "a a b d", "e f f d"],
    ["a a b b", "a a c c", "d d e f"],
    ["a a b c", "a a d e", "f f d e"],
  ],
  7: [
    ["a a b c", "a a d e", "f g d e"],
    ["a a b c", "a a d d", "e f g g"],
  ],
  8: [
    ["a a b c", "a a d e", "f g h h"],
    ["a a b c", "a a d e", "f f g h"],
  ],
};

interface Slot {
  name: string;
  w: number;
  h: number;
  /** Reading order of the slot's top-left corner. */
  at: number;
}

/** What one letter out of reading order costs, against cropping: a near
 * tie goes to the layout that reads A, B, C… left to right, top down. */
const OUT_OF_ORDER = 0.12;

function parse(rows: string[]): string[][] {
  return rows.map((r) => r.trim().split(/\s+/));
}

function transpose(grid: string[][]): string[][] {
  return (grid[0] ?? []).map((_, c) => grid.map((row) => row[c] ?? ""));
}

function slotsOf(grid: string[][]): Slot[] {
  const found = new Map<string, Slot>();
  const cols = new Map<string, Set<number>>();
  const rows = new Map<string, Set<number>>();
  const at = new Map<string, number>();
  grid.forEach((row, r) =>
    row.forEach((name, c) => {
      if (!cols.has(name)) {
        cols.set(name, new Set());
        rows.set(name, new Set());
        at.set(name, at.size);
      }
      cols.get(name)!.add(c);
      rows.get(name)!.add(r);
    }),
  );
  for (const [name, cs] of cols) {
    found.set(name, {
      name,
      w: cs.size,
      h: rows.get(name)!.size,
      at: at.get(name)!,
    });
  }
  return [...found.values()].sort(
    (x, y) => y.w * y.h - x.w * x.h || x.name.localeCompare(y.name),
  );
}

function permutations<T>(items: T[]): T[][] {
  if (items.length <= 1) return [items];
  return items.flatMap((item, i) =>
    permutations([...items.slice(0, i), ...items.slice(i + 1)]).map((p) => [
      item,
      ...p,
    ]),
  );
}

/** How badly `aspect` is cropped in a slot of `slotAspect`, by its area. */
function crop(slotAspect: number, aspect: number, area: number): number {
  return area * Math.abs(Math.log(slotAspect / aspect));
}

/**
 * The layout for pictures of the given aspect ratios (width / height) in a
 * box of `boxAspect`. Pictures beyond eight are left out (slots "").
 */
export function chooseLayout(aspects: number[], boxAspect: number): Layout {
  const n = Math.min(aspects.length, 8);
  if (n === 0) return { areas: [], cols: 0, rows: 0, slots: [] };
  const safe = aspects.map((a) => (a > 0 && Number.isFinite(a) ? a : 1));
  let best: { cost: number; layout: Layout } | null = null;
  for (const rows of TEMPLATES[n] ?? []) {
    const base = parse(rows);
    for (const grid of [base, transpose(base)]) {
      const nRows = grid.length;
      const nCols = grid[0]?.length ?? 1;
      const cell = boxAspect * (nRows / nCols);
      const slots = slotsOf(grid);
      const [hero, ...rest] = slots;
      if (!hero) continue;
      const heroCost = crop(
        (hero.w / hero.h) * cell,
        safe[0] ?? 1,
        hero.w * hero.h,
      );
      let bestRest = Infinity;
      let order: Slot[] = rest;
      for (const perm of permutations(rest)) {
        let c = 0;
        perm.forEach((s, i) => {
          c += crop((s.w / s.h) * cell, safe[i + 1] ?? 1, s.w * s.h);
          for (const later of perm.slice(i + 1)) {
            if (later.at < s.at) c += OUT_OF_ORDER;
          }
        });
        if (c < bestRest) {
          bestRest = c;
          order = perm;
        }
      }
      const cost = heroCost + bestRest;
      if (!best || cost < best.cost - 1e-9) {
        best = {
          cost,
          layout: {
            areas: grid.map((r) => `"${r.join(" ")}"`),
            cols: nCols,
            rows: nRows,
            slots: [
              hero.name,
              ...order.map((s) => s.name),
              ...Array(aspects.length - n).fill(""),
            ],
          },
        };
      }
    }
  }
  return best?.layout ?? { areas: [], cols: 0, rows: 0, slots: [] };
}

/** "A–F", "A and B", "A, C and D" for the ids on screen. */
export function letterRange(ids: string[]): string {
  if (ids.length <= 1) return ids.join("");
  const codes = ids.map((id) => id.toUpperCase().charCodeAt(0));
  const contiguous = codes.every(
    (c, i) => i === 0 || c === (codes[i - 1] ?? 0) + 1,
  );
  if (contiguous && ids.length > 2) return `${ids[0]}–${ids[ids.length - 1]}`;
  return `${ids.slice(0, -1).join(", ")} and ${ids[ids.length - 1]}`;
}
