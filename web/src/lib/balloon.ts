// SPDX-License-Identifier: Apache-2.0
/**
 * The camera card's entrance and exit: it inflates out of the screen's
 * bottom-right corner like a rectangular balloon (a quick swell past full
 * size, a wobble where width and height settle a beat apart) and, when it's
 * done, swells a touch and shrinks back into the same corner.
 *
 * Svelte transitions with `css`, so each runs as one CSS animation of
 * transform and opacity, on the compositor: the kiosk's Pi keeps decoding
 * the video on the main thread while it plays. The rounded corners shrink
 * to square as it fills the screen (border-radius divided by the scale, so
 * they look the same size whatever the scale).
 */

export const INFLATE_MS = 1400;
export const DEFLATE_MS = 1000;

/** How small it starts, as a share of the screen. */
const FROM_X = 0.1;
const FROM_Y = 0.12;
/** The corner's radius while it's small, in px on screen. */
const RADIUS = 36;
/** Where it grows from: the bottom-right corner, a little in. */
export const ORIGIN = "calc(100% - 3vmin) calc(100% - 3vmin)";

/** A damped spring from `from` to 1: it overshoots ~8% and settles. `lag`
    holds it back a moment (the height trails the width). */
export function spring(p: number, from: number, lag = 0): number {
  const q = Math.max(0, (p - lag) / (1 - lag));
  return 1 - (1 - from) * Math.exp(-7 * q) * Math.cos(9 * q);
}

/** Ease-in with a back swell: dips a little below 0 first (the card puffs
    up ~3%), crosses back by halfway, then accelerates to 1. */
export function backIn(u: number): number {
  const c = 0.9;
  return (c + 1) * u * u * u - c * u * u;
}

function frame(sx: number, sy: number, opacity: number, round: number): string {
  const r = RADIUS * round;
  return (
    `transform-origin: ${ORIGIN};` +
    `transform: scale(${sx.toFixed(4)}, ${sy.toFixed(4)});` +
    `border-radius: ${(r / Math.max(sx, 0.01)).toFixed(1)}px / ${(r / Math.max(sy, 0.01)).toFixed(1)}px;` +
    `opacity: ${opacity.toFixed(3)};`
  );
}

const still = () =>
  typeof matchMedia === "function" &&
  matchMedia("(prefers-reduced-motion: reduce)").matches;

/** in: the balloon inflating. */
export function inflate(_node: Element) {
  if (still()) return { duration: 200, css: (t: number) => `opacity: ${t}` };
  return {
    duration: INFLATE_MS,
    css: (t: number) =>
      frame(
        spring(t, FROM_X),
        spring(t, FROM_Y, 0.06),
        Math.min(1, t * 6),
        Math.max(0, 1 - t * 1.6),
      ),
  };
}

/** out: back into the corner. Svelte runs `t` from 1 down to 0. */
export function deflate(_node: Element) {
  if (still()) return { duration: 200, css: (t: number) => `opacity: ${t}` };
  return {
    duration: DEFLATE_MS,
    css: (t: number) => {
      const u = backIn(1 - t);
      return frame(
        1 - (1 - FROM_X) * u,
        1 - (1 - FROM_Y) * backIn(Math.max(0, 1 - t - 0.04) / 0.96),
        Math.min(1, t * 7),
        Math.min(1, (1 - t) * 1.6),
      );
    },
  };
}
