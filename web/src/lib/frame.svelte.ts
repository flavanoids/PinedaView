// SPDX-License-Identifier: Apache-2.0
/**
 * The picture frame a screen hangs in: the share of its width the frame
 * hides on each side (the phone menu's Screen shape → Picture frame). Photos,
 * wallpaper and tints still fill the whole panel, under the frame's lip; the
 * time, date, cards and buttons move in by this much at their full size,
 * never scaled down. The share is of the panel's long side, and the lip
 * covers its short ends: the sides of a wide screen, the top and bottom of
 * a tall one (a screen turned on its side in the same frame). App passes it
 * to CSS as `--frame-inset`; styles/base.css makes `--frame-x`/`--frame-y`.
 */
export const frame = $state({ inset: 0 });

/** The hidden strip on each side of a box this size, px (none when tall). */
export function frameX(width: number, height = 0): number {
  return height > width ? 0 : width * frame.inset;
}

/** The hidden strip at the top and bottom of a box this size, px (none
    when wide). */
export function frameY(width: number, height: number): number {
  return height > width ? height * frame.inset : 0;
}
