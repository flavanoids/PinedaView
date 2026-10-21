// SPDX-License-Identifier: Apache-2.0
// The day-part tint (App.svelte): an amber flare around sunrise and sunset and
// an indigo wash over the night, as layer opacities. Pure minutes-past-midnight
// math so it tests without Dates. The server already flips themes to their
// night twins at the sun moments — this is the gradual wash between those
// switches, so it stays faint.

// Tuning knobs — guesses from taste; adjust against the real wallpaper and
// night twins on the kiosk.
export const DEFAULT_SUNRISE = 6 * 60 + 45; // until the weather store answers
export const DEFAULT_SUNSET = 18 * 60 + 15;
const WARM_RISE_PEAK = 0.18;
const WARM_SET_PEAK = 0.15;
const WARM_HALF_WIDTH = 45; // minutes either side of the sun moment
const COOL_PEAK = 0.14;
const COOL_LEAD = 15; // night starts draining/building this far inside the day
const COOL_TAIL = 60; // …and finishes this far into the night side

export interface DayTints {
  /** Opacity of the dawn/dusk amber layer, 0–1. */
  warm: number;
  /** Opacity of the night indigo layer, 0–1. */
  cool: number;
}

/** Clamped linear 0→1 as t goes from `from` to `to`. */
function ramp(t: number, from: number, to: number): number {
  if (to <= from) return t >= to ? 1 : 0;
  return Math.min(1, Math.max(0, (t - from) / (to - from)));
}

function triangle(t: number, centre: number, halfWidth: number): number {
  return Math.max(0, 1 - Math.abs(t - centre) / halfWidth);
}

export function dayTints(
  minuteOfDay: number,
  sunriseMin: number | null,
  sunsetMin: number | null,
): DayTints {
  const rise = sunriseMin ?? DEFAULT_SUNRISE;
  const set = sunsetMin ?? DEFAULT_SUNSET;
  const t = minuteOfDay;
  const warm = Math.max(
    WARM_RISE_PEAK * triangle(t, rise, WARM_HALF_WIDTH),
    WARM_SET_PEAK * triangle(t, set, WARM_HALF_WIDTH),
  );
  const morning = 1 - ramp(t, rise - COOL_TAIL, rise + COOL_LEAD);
  const evening = ramp(t, set - COOL_LEAD, set + COOL_TAIL);
  return { warm, cool: COOL_PEAK * Math.max(morning, evening) };
}
