// SPDX-License-Identifier: Apache-2.0
/**
 * The picture frame a screen hangs in: the share of its width the frame
 * hides on each side (the phone menu's Screen shape → Picture frame). Photos,
 * wallpaper and tints still fill the whole panel, under the frame's lip; the
 * time, date, cards and buttons move in by this much at their full size,
 * never scaled down. App mirrors it to `--frame-x` on <html> for CSS.
 */
export const frame = $state({ inset: 0 });

/** The hidden strip on each side of a box this wide, px. */
export function frameX(width: number): number {
  return width * frame.inset;
}
