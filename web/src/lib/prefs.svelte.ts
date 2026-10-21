// SPDX-License-Identifier: Apache-2.0
/**
 * The household's, profile's and screen's preferences, as the server sends
 * them on every view (`view.prefs`). Module state rather than a prop so the
 * formatting helpers and card timings can read it without threading the
 * view model through every call; reading it inside a `$derived` tracks it,
 * so a change in Settings lands live.
 */
import type { ScreenPrefs } from "@pinedaview/protocol";

export const DEFAULT_PREFS: ScreenPrefs = {
  time_format: "12h",
  date_style: "long",
  pace: "normal",
  photo_hold_s: 20,
  photo_order: "manual",
  photo_fit: "fill",
  accent: null,
  wallpaper_everywhere: false,
  night_weeknight_start: "00:00",
  night_weekend_start: "02:00",
  night_end: "05:00",
  peek_s: 60,
  dynamic_shuffle: false,
  shuffle_hold_s: 15,
  ambient_cycle_m: 5,
};

export const prefs = $state<ScreenPrefs>({ ...DEFAULT_PREFS });

/** Copy changed keys only, so an unchanged view doesn't wake every reader. */
export function applyPrefs(next: Partial<ScreenPrefs> | undefined): void {
  const merged = { ...DEFAULT_PREFS, ...next } as Record<string, unknown>;
  const target = prefs as unknown as Record<string, unknown>;
  for (const key of Object.keys(DEFAULT_PREFS)) {
    if (target[key] !== merged[key]) target[key] = merged[key];
  }
}

const PACE: Record<ScreenPrefs["pace"], number> = {
  relaxed: 1.5,
  normal: 1,
  brisk: 0.6,
};

/** A rotating card's hold time, scaled by Settings → Cards → Rotation speed. */
export function paced(ms: number): number {
  return Math.round(ms * (PACE[prefs.pace] ?? 1));
}
