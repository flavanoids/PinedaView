// SPDX-License-Identifier: Apache-2.0
// Geometry for the weather card's "next hours" page: which slots to plot,
// the temperature curve through them, and where sunrise/sunset fall on it.
// Every x is a percentage across the plot, with slot i centred in column i
// of n, so the curve's points sit directly over the rain-chance columns.
import { parseClockTime } from "./format";
import type { WeatherDay, WeatherHour } from "../cards/types";

/** The provider's list starts at the hour it polled; drop any slot the
    clock has since passed, then keep `count`. */
export function upcoming(
  hourly: WeatherHour[],
  nowHour: number,
  count: number,
): WeatherHour[] {
  const start = hourly.slice(0, 3).findIndex((h) => h.hour === nowHour);
  return hourly.slice(Math.max(start, 0), Math.max(start, 0) + count);
}

/** Centre of column `i` of `n`, as a percentage. */
export function columnX(i: number, n: number): number {
  return ((i + 0.5) / n) * 100;
}

export interface Point {
  x: number;
  y: number;
}

/** A smooth path through `points` that never overshoots them (monotone
    cubic, Fritsch–Carlson), so the curve's peak is the labelled high and
    never pokes above it. */
export function curvePath(points: Point[]): string {
  const n = points.length;
  if (n === 0) return "";
  if (n === 1) return `M${points[0]!.x},${points[0]!.y}`;
  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    dx.push(points[i + 1]!.x - points[i]!.x);
    slope.push((points[i + 1]!.y - points[i]!.y) / dx[i]!);
  }
  const tangent: number[] = [slope[0]!];
  for (let i = 1; i < n - 1; i++) {
    const a = slope[i - 1]!;
    const b = slope[i]!;
    tangent.push(
      a * b <= 0
        ? 0
        : (3 * (dx[i - 1]! + dx[i]!)) /
            ((2 * dx[i]! + dx[i - 1]!) / a + (dx[i]! + 2 * dx[i - 1]!) / b),
    );
  }
  tangent.push(slope[n - 2]!);
  let d = `M${points[0]!.x},${points[0]!.y}`;
  for (let i = 0; i < n - 1; i++) {
    const p = points[i]!;
    const q = points[i + 1]!;
    const h = dx[i]! / 3;
    d += `C${p.x + h},${p.y + h * tangent[i]!} ${q.x - h},${q.y - h * tangent[i + 1]!} ${q.x},${q.y}`;
  }
  return d;
}

export interface SunMark {
  kind: "Sunrise" | "Sunset";
  /** "6:58 PM", as the provider sends it. */
  time: string;
  /** Position across the plot, percent. */
  x: number;
}

/** Sunrises and sunsets that land inside the plotted window, which starts
    at the top of `startHour` today and runs `n` hours. */
export function sunMarks(
  days: WeatherDay[],
  startHour: number,
  n: number,
): SunMark[] {
  const marks: SunMark[] = [];
  days.slice(0, 2).forEach((day, offset) => {
    for (const kind of ["Sunrise", "Sunset"] as const) {
      const time = kind === "Sunrise" ? day.sunrise : day.sunset;
      const minutes = parseClockTime(time);
      if (minutes == null || !time) continue;
      const hours = (offset * 1440 + minutes) / 60 - startHour;
      // Column i is centred on hour i, so the plot spans -0.5 … n - 0.5.
      if (hours < -0.5 || hours > n - 0.5) continue;
      marks.push({ kind, time, x: ((hours + 0.5) / n) * 100 });
    }
  });
  return marks;
}

/** Runs of consecutive after-dark slots, as [from, to) column indexes. */
export function nightRuns(hours: WeatherHour[]): [number, number][] {
  const runs: [number, number][] = [];
  hours.forEach((h, i) => {
    if (h.isDay !== false) return;
    const last = runs[runs.length - 1];
    if (last && last[1] === i) last[1] = i + 1;
    else runs.push([i, i + 1]);
  });
  return runs;
}

export interface SunNext {
  kind: "Sunrise" | "Sunset";
  time: string;
  tomorrow: boolean;
}

/** The next sunrise and next sunset after `nowMinutes` (minutes past
    today's midnight), soonest first — for the times the chart can't show. */
export function nextSun(days: WeatherDay[], nowMinutes: number): SunNext[] {
  const ahead: (SunNext & { at: number })[] = [];
  days.slice(0, 2).forEach((day, offset) => {
    for (const kind of ["Sunrise", "Sunset"] as const) {
      const time = kind === "Sunrise" ? day.sunrise : day.sunset;
      const minutes = parseClockTime(time);
      if (minutes == null || !time) continue;
      const at = offset * 1440 + minutes;
      if (at > nowMinutes && !ahead.some((e) => e.kind === kind))
        ahead.push({ kind, time, tomorrow: offset === 1, at });
    }
  });
  return ahead
    .sort((a, b) => a.at - b.at)
    .map(({ kind, time, tomorrow }) => ({ kind, time, tomorrow }));
}
