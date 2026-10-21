// SPDX-License-Identifier: Apache-2.0
/**
 * The Photo Clock's swipe: the next photo comes in quick and eases off,
 * meets the edge still moving, bounces back a few pixels and settles, all
 * well under a second.
 *
 * The bounce only ever pulls the photo back towards where it came from,
 * never past its place: going past would open a black strip at the far
 * edge, while backing off shows only the outgoing photo, which rides
 * alongside.
 *
 * Written out as a CSS `linear()` easing, so the whole thing still runs on
 * the compositor as a plain transform transition, off the main thread.
 */

export const SWIPE_MS = 850;

/** The approach: a weighted cubic ease-out (quick start) blended with a
    little linear, so it reaches the edge with some speed left to bounce. */
const EASE = 0.7;
/** The first bounce, as a share of the screen's width (≈ 20 px on the
    kiosk); each later one keeps RESTITUTION² of the height before. */
const BOUNCE = 0.01;
const RESTITUTION = 0.45;
const BOUNCES = 2;

interface Arc {
  start: number;
  length: number;
  height: number;
}

/** The approach's share of the time, and the arcs after it (in raw time,
    before it's stretched to fit 0–1). */
function plan(): { approach: number; arcs: Arc[]; total: number } {
  const approach = 1;
  let speed = 1 - EASE; // dp/du at u = 1
  let height = BOUNCE;
  let t = approach;
  const arcs: Arc[] = [];
  for (let i = 0; i < BOUNCES; i++) {
    // A parabola that leaves at `speed` and rises `height`: 4h / v long.
    const length = (4 * height) / speed;
    arcs.push({ start: t, length, height });
    t += length;
    speed *= RESTITUTION;
    height *= RESTITUTION * RESTITUTION;
  }
  return { approach, arcs, total: t };
}

const PLAN = plan();

/** How far across the photo is at time t (both 0–1). */
export function swipeProgress(t: number): number {
  const raw = Math.min(1, Math.max(0, t)) * PLAN.total;
  if (raw <= PLAN.approach) {
    const u = raw / PLAN.approach;
    return EASE * (1 - (1 - u) ** 3) + (1 - EASE) * u;
  }
  for (const a of PLAN.arcs) {
    if (raw <= a.start + a.length) {
      const s = (raw - a.start) / a.length;
      return 1 - 4 * a.height * s * (1 - s);
    }
  }
  return 1;
}

/** The first moment the photo is at least `share` of the way across. */
export function swipeTimeAt(share: number): number {
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 24; i++) {
    const mid = (lo + hi) / 2;
    if (swipeProgress(mid) >= share) hi = mid;
    else lo = mid;
  }
  return hi;
}

function easing(): string {
  const points: string[] = [];
  const add = (t: number) =>
    points.push(`${swipeProgress(t).toFixed(4)} ${(t * 100).toFixed(2)}%`);
  // Denser where it curves: the approach's start and each arc.
  const end = PLAN.approach / PLAN.total;
  for (let i = 0; i <= 24; i++) add(end * (i / 24) ** 1.6);
  for (const a of PLAN.arcs)
    for (let i = 1; i <= 8; i++)
      add((a.start + (a.length * i) / 8) / PLAN.total);
  return `linear(${points.join(", ")})`;
}

/** The curve for CSS; browsers without `linear()` get a plain ease-out. */
export function swipeEasing(): string {
  const curve = easing();
  return typeof CSS !== "undefined" &&
    CSS.supports("transition-timing-function", curve)
    ? curve
    : "cubic-bezier(0.22, 1, 0.36, 1)";
}
