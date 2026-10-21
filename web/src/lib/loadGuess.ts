// SPDX-License-Identifier: Apache-2.0
/**
 * A loading percentage for something whose real progress can't be seen —
 * a battery camera waking and starting its stream. It follows a guess at
 * how long that takes: quick at first, ~80% by the typical time, then ever
 * slower, and it never passes CAP on its own; the caller shows 100% when
 * the thing actually arrives.
 */

/** The typical wait, ms: Home Assistant's ~2 s to start the stream plus
    ~1–2 s for the first frame (measured 2026-10-15; a sleeping doorbell
    takes ~6 s). */
export const TYPICAL_MS = 4000;
export const CAP = 95;

/** Percent (0–CAP, whole) after `elapsedMs`: 1 − e^(−t/τ), τ set so the
    typical wait reads 80%. */
export function loadGuess(elapsedMs: number, typicalMs = TYPICAL_MS): number {
  if (elapsedMs <= 0) return 0;
  const tau = typicalMs / Math.log(5); // e^(−typical/τ) = 0.2
  return Math.min(CAP, Math.floor(100 * (1 - Math.exp(-elapsedMs / tau))));
}
