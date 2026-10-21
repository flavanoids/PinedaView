// SPDX-License-Identifier: Apache-2.0
/**
 * What the layout builder warns about before a layout goes on a screen.
 * Pure: given the draft and roughly how big the screen is, list the problems.
 */
import { rowCount, type Grid, type GridItem } from "../lib/grid";

export interface Warning {
  /** "stop" warnings get a confirmation before saving; "note" ones don't. */
  level: "stop" | "note";
  card?: string;
  text: string;
}

/** Below these, on the real screen, a card stops being readable. */
const MIN_BOX_PX = { w: 150, h: 100 };
/** A phone camera needs about this much photo to pick out the QR badge. */
const MIN_QR_BOX_PX = 220;

export interface ScreenSize {
  /** Screen width in CSS px, when the screen has reported it. */
  width: number | null;
  height: number | null;
  /** True when the screen splits its height evenly into the layout's rows
   *  (a locked wall display) rather than scrolling. */
  fills: boolean;
}

/** Roughly how big one grid unit comes out on the screen, in CSS px. */
export function unitPx(
  grid: Grid,
  screen: ScreenSize,
): { w: number; h: number } | null {
  if (!screen.width) return null;
  const w = screen.width / grid.cols;
  const rows = Math.max(1, rowCount(grid.items));
  const h = screen.fills && screen.height ? screen.height / rows : w * 0.75;
  return { w, h };
}

export function layoutWarnings(
  grid: Grid,
  screen: ScreenSize,
  name: (card: string) => string,
  /** The kitchen screen, whose photo badge is how phones find the menu. */
  home = true,
): Warning[] {
  const out: Warning[] = [];
  if (grid.items.length === 0) {
    return [{ level: "stop", text: "There are no cards on the screen." }];
  }
  const photo = home ? grid.items.find((i) => i.card === "photo") : undefined;
  if (home && !photo) {
    out.push({
      level: "stop",
      text: "Without the photo card there's no QR code on this screen to get back to these settings.",
    });
  }
  const unit = unitPx(grid, screen);
  if (!unit) return out;
  const px = (i: GridItem) => ({ w: i.w * unit.w, h: i.h * unit.h });
  if (photo) {
    const { w, h } = px(photo);
    if (Math.min(w, h) < MIN_QR_BOX_PX) {
      out.push({
        level: "stop",
        card: "photo",
        text: "The photo is small enough that its QR code may be hard to scan.",
      });
    }
  }
  for (const item of grid.items) {
    const { w, h } = px(item);
    const short = h < MIN_BOX_PX.h;
    const narrow = w < MIN_BOX_PX.w;
    if (!short && !narrow) continue;
    const how =
      short && narrow ? "very small" : short ? "very short" : "very narrow";
    out.push({
      level: "note",
      card: item.card,
      text: `${name(item.card)} will be ${how} on the screen.`,
    });
  }
  return out;
}
