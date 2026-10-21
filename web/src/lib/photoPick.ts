// SPDX-License-Identifier: Apache-2.0
// The Photo Clock's next photo: a shuffle that doesn't come back to a photo
// until most of the library has had its turn, skips the near-copies of a
// burst, and leans (gently: it's still a slideshow) towards photos that suit
// the hour — bright ones by day, warm ones round sunrise and sunset, dark and
// warm ones at night, and any photo taken near this time of day.
import type { Photo } from "@pinedaview/protocol";
import { DEFAULT_SUNRISE, DEFAULT_SUNSET } from "./daypart";

/** A photo's look from its dominant colours (Photo.colours): mean luma and
    warmth (red over blue), both 0–1. Unknown: middling. */
export function photoLook(colours: readonly string[] | undefined): {
  luma: number;
  warmth: number;
} {
  const rgbs = (colours ?? [])
    .map((h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255))
    .filter((c) => c.every((v) => Number.isFinite(v)));
  if (!rgbs.length) return { luma: 0.5, warmth: 0.5 };
  let luma = 0;
  let warmth = 0;
  for (const [r = 0, g = 0, b = 0] of rgbs) {
    luma += 0.2126 * r + 0.7152 * g + 0.0722 * b;
    warmth += (r - b + 1) / 2;
  }
  return { luma: luma / rgbs.length, warmth: warmth / rgbs.length };
}

/** Hours between two times of day, the short way round the clock. */
function hoursApart(a: number, b: number): number {
  const d = Math.abs(a - b) % 1440;
  return Math.min(d, 1440 - d) / 60;
}

/** 0–1: how well a photo suits this minute of the day. */
export function timeFit(
  p: Photo,
  minuteOfDay: number,
  sunrise: number | null,
  sunset: number | null,
): number {
  const rise = sunrise ?? DEFAULT_SUNRISE;
  const set = sunset ?? DEFAULT_SUNSET;
  const { luma, warmth } = photoLook(p.colours);
  const t = minuteOfDay;
  let fit: number;
  if (hoursApart(t, rise) <= 1 || hoursApart(t, set) <= 1) fit = warmth;
  else if (t > rise && t < set) fit = luma;
  else fit = 0.6 * (1 - luma) + 0.4 * warmth;
  if (p.taken_at) {
    const at = new Date(p.taken_at * 1000);
    const took = at.getHours() * 60 + at.getMinutes();
    fit = Math.max(fit, 1 - hoursApart(t, took) / 3);
  }
  return Math.min(1, Math.max(0, fit));
}

/** Most of the library has its turn before a photo comes round again. */
export function recentLimit(count: number): number {
  return Math.floor(count * 0.75);
}

/** Photos taken this close together (seconds) are one burst. */
const BURST_S = 10 * 60;

/** The index of the photo to show after `current`, or -1 with none to
    pick. `recent` is the names shown lately, newest last. */
export function pickNext(
  photos: readonly Photo[],
  current: number,
  recent: readonly string[],
  now: Date,
  sunrise: number | null,
  sunset: number | null,
  random: () => number = Math.random,
): number {
  if (photos.length < 2) return photos.length - 1;
  const lately = new Set(recent.slice(-recentLimit(photos.length)));
  const was = photos[current];
  let pool = photos
    .map((p, i) => i)
    .filter((i) => i !== current && !lately.has(photos[i]!.name));
  if (!pool.length) pool = photos.map((p, i) => i).filter((i) => i !== current);
  const minute = now.getHours() * 60 + now.getMinutes();
  const weights = pool.map((i) => {
    const p = photos[i]!;
    let w = 1 + 2 * timeFit(p, minute, sunrise, sunset);
    if (
      was?.taken_at &&
      p.taken_at &&
      Math.abs(was.taken_at - p.taken_at) < BURST_S
    )
      w *= 0.1;
    return w;
  });
  let r = random() * weights.reduce((a, b) => a + b, 0);
  for (let k = 0; k < pool.length; k++) {
    r -= weights[k]!;
    if (r <= 0) return pool[k]!;
  }
  return pool[pool.length - 1]!;
}
