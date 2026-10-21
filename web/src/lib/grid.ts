// SPDX-License-Identifier: Apache-2.0
/**
 * Snap-grid layout maths for the layout builder (and the Stage that renders
 * its result). Pure functions over plain items; nothing here touches the DOM.
 *
 * The builder works in bricks, not boxes: one optional Large card pinned to
 * the top left or right, then Small (one cell) and Medium (two cells wide)
 * cards that each click into the first free spot in reading order. Cards
 * never sit anywhere by hand, so a layout can't get messy. The saved shape is
 * still a plain grid of boxes, at UNIT grid units per cell.
 */
import type { Grid, GridItem } from "@pinedaview/protocol";

export type { Grid, GridItem };

/** Each automatic-layout cell becomes this many grid units a side, so the
 *  first hand-placed layout looks exactly like the automatic one did. */
export const UNIT = 2;

export function overlaps(a: GridItem, b: GridItem): boolean {
  return (
    a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
  );
}

export function rowCount(items: readonly GridItem[]): number {
  return items.reduce((n, i) => Math.max(n, i.y + i.h), 0);
}

const byPos = (a: GridItem, b: GridItem): number => a.y - b.y || a.x - b.x;

/** The biggest box, first in reading order on a tie — the server picks the
 *  same one (Grid.hero_item) for the hero and countdown/alert takeovers. */
export function heroItem(items: readonly GridItem[]): GridItem | undefined {
  let best: GridItem | undefined;
  for (const item of [...items].sort(byPos)) {
    if (!best || item.w * item.h > best.w * best.h) best = item;
  }
  return best;
}

export function sameLayout(a: Grid, b: Grid): boolean {
  if (a.cols !== b.cols || a.items.length !== b.items.length) return false;
  return a.items.every((i) => {
    const j = b.items.find((o) => o.card === i.card);
    return !!j && j.x === i.x && j.y === i.y && j.w === i.w && j.h === i.h;
  });
}

export type Size = "s" | "m" | "l";

export interface Brick {
  card: string;
  size: Exclude<Size, "l">;
}

export interface Bricks {
  /** Columns of automatic-layout cells across the screen. */
  cells: number;
  /** The Large card's span, in cells (from the screen's layout tier). */
  heroW: number;
  heroH: number;
  /** The Large card, if there is one, and which top corner it sits in. */
  hero: string | null;
  side: "left" | "right";
  /** Everything else, in the order they fill in. */
  pieces: Brick[];
}

/** Where every brick lands, as the grid the screen draws. */
export function pack(b: Bricks): Grid {
  const cells = Math.max(1, b.cells);
  let items: GridItem[] = [];
  if (b.hero) {
    const w = Math.min(b.heroW, cells);
    const x = b.side === "right" ? cells - w : 0;
    items = [{ card: b.hero, x, y: 0, w, h: Math.max(1, b.heroH) }];
  }
  for (const p of b.pieces) {
    const w = p.size === "m" ? Math.min(2, cells) : 1;
    items = [...items, firstFree(items, cells, p.card, w, 1)];
  }
  return {
    cols: cells * UNIT,
    items: items.map((i) => ({
      card: i.card,
      x: i.x * UNIT,
      y: i.y * UNIT,
      w: i.w * UNIT,
      h: i.h * UNIT,
    })),
  };
}

/** Read a saved grid back as bricks: its biggest box is the Large card,
 *  anything two cells wide is Medium, the rest Small, in reading order. */
export function toBricks(grid: Grid, heroW: number, heroH: number): Bricks {
  const cells = Math.max(1, Math.round(grid.cols / UNIT));
  const big = heroItem(grid.items);
  const isHero = !!big && big.h > UNIT;
  const hero = isHero ? big : undefined;
  return {
    cells,
    heroW,
    heroH,
    hero: hero?.card ?? null,
    side: hero && hero.x + hero.w / 2 > grid.cols / 2 ? "right" : "left",
    pieces: [...grid.items]
      .filter((i) => i !== hero)
      .sort(byPos)
      .map((i) => ({
        card: i.card,
        size: i.w >= 2 * UNIT && cells > 1 ? "m" : "s",
      })),
  };
}

export function sizeOf(b: Bricks, card: string): Size | undefined {
  if (b.hero === card) return "l";
  return b.pieces.find((p) => p.card === card)?.size;
}

/** Give a card a new size. Making one Large sends the old Large card to the
 *  spot (and size) it came from; shrinking the Large card makes it the first
 *  brick, leaving no Large card. */
export function setSize(b: Bricks, card: string, size: Size): Bricks {
  const now = sizeOf(b, card);
  if (!now || now === size) return b;
  if (size === "l") {
    const i = b.pieces.findIndex((p) => p.card === card);
    const pieces = [...b.pieces];
    const old = pieces[i];
    if (b.hero && old) pieces[i] = { card: b.hero, size: old.size };
    else pieces.splice(i, 1);
    return { ...b, hero: card, pieces };
  }
  if (now === "l") {
    return { ...b, hero: null, pieces: [{ card, size }, ...b.pieces] };
  }
  return {
    ...b,
    pieces: b.pieces.map((p) => (p.card === card ? { card, size } : p)),
  };
}

/** Two cards trade spots; the spots (and their sizes) stay where they are. */
export function swap(b: Bricks, a: string, c: string): Bricks {
  if (a === c) return b;
  const other = (x: string) => (x === a ? c : x === c ? a : x);
  return {
    ...b,
    hero: b.hero && other(b.hero),
    pieces: b.pieces.map((p) => ({ ...p, card: other(p.card) })),
  };
}

/** Move a brick one place earlier (-1) or later (+1) in the fill order. */
export function shift(b: Bricks, card: string, by: -1 | 1): Bricks {
  const i = b.pieces.findIndex((p) => p.card === card);
  const j = i + by;
  if (i < 0 || j < 0 || j >= b.pieces.length) return b;
  const pieces = [...b.pieces];
  [pieces[i], pieces[j]] = [pieces[j]!, pieces[i]!];
  return { ...b, pieces };
}

export function addBrick(b: Bricks, card: string): Bricks {
  if (sizeOf(b, card)) return b;
  return { ...b, pieces: [...b.pieces, { card, size: "s" }] };
}

export function removeBrick(b: Bricks, card: string): Bricks {
  return {
    ...b,
    hero: b.hero === card ? null : b.hero,
    pieces: b.pieces.filter((p) => p.card !== card),
  };
}

/** The bricks version of what the automatic layout shows today: the hero
 *  Large on the left, every other card Small, in card_stack order. */
export function fromStack(
  cards: readonly string[],
  hero: string | null,
  cells: number,
  heroW: number,
  heroH: number,
): Bricks {
  return {
    cells: Math.max(1, cells),
    heroW,
    heroH,
    hero,
    side: "left",
    pieces: cards
      .filter((c) => c !== hero)
      .map((card) => ({ card, size: "s" as const })),
  };
}

function firstFree(
  items: readonly GridItem[],
  cols: number,
  card: string,
  w: number,
  h: number,
): GridItem {
  for (let y = 0; ; y++) {
    for (let x = 0; x + w <= cols; x++) {
      const at = { card, x, y, w, h };
      if (!items.some((i) => overlaps(i, at))) return at;
    }
  }
}

/** Column count of a CSS grid-template-columns value from a layout tier. */
export function columnCount(spec: string): number {
  const repeated = spec.match(/^repeat\((\d+),/);
  return repeated ? Number(repeated[1]) : spec.trim().split(/\s+/).length;
}

/**
 * How many columns the last card of an automatic layout should span so it
 * doesn't end up alone in an otherwise-empty trailing row. The hero's 2D span
 * means the card count rarely divides evenly into the grid; without this a
 * lone last card sits in column 1 with the rest of its row empty. Only covers
 * the *last* row — a smaller gap next to the hero itself (too few cards to
 * fill even that) is left alone rather than reshuffling cards out of their
 * configured order.
 */
export function trailingSpan(
  cols: number,
  heroColSpan: number,
  heroRowSpan: number,
  cards: number,
): number {
  if (cols <= 1 || cards === 0) return 1;
  const heroCapacity = Math.max(0, cols - heroColSpan) * heroRowSpan;
  const lastRowCount = Math.max(0, cards - heroCapacity) % cols;
  return lastRowCount === 0 ? 1 : cols - lastRowCount + 1;
}

/** Which theme colour (`--card-<slot>`) each card is painted in, in the
 *  layout builder and the Settings miniature (mirrors the menu's mini map). */
export const TINT_SLOT: Readonly<Record<string, string>> = {
  clock: "clock",
  weather: "weather",
  forecast: "forecast",
  affirmation: "affirmation",
  traffic: "affirmation",
  phrase: "phrase",
  "now-playing": "nowPlaying",
  moon: "moon",
  "moon-climate": "moon",
  "home-cams": "moon",
  radar: "radar",
};
