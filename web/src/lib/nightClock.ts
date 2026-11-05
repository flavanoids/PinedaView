// SPDX-License-Identifier: Apache-2.0
/**
 * Small hours: the dashboard gives way to a lone clock. Each night is named
 * for the morning it ends on — before a weekday (Monday–Friday) morning it
 * runs from `weeknightStart` to `end`, before a Saturday or Sunday morning
 * from `weekendStart` to `weekendEnd` (or `end`, if that's not set). A start
 * after its end ("23:00" → "06:00") begins the evening before; a start equal
 * to its end means that night has no night clock. Defaults: midnight on
 * weeknights, 2am at the weekend, both until 5am.
 */
export interface NightSchedule {
  weeknightStart: string;
  weekendStart: string;
  end: string;
  weekendEnd?: string | null;
}

export const DEFAULT_NIGHT: NightSchedule = {
  weeknightStart: "00:00",
  weekendStart: "02:00",
  end: "05:00",
};

function minutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

export function isNightClock(
  now: Date,
  schedule: NightSchedule = DEFAULT_NIGHT,
): boolean {
  // The night ending on day d's morning (0 = Sunday): [start, end].
  const night = (d: number): [number, number] => {
    const weekend = d === 0 || d === 6;
    return [
      minutes(weekend ? schedule.weekendStart : schedule.weeknightStart),
      minutes((weekend && schedule.weekendEnd) || schedule.end),
    ];
  };
  const t = now.getHours() * 60 + now.getMinutes();
  // Before this morning's end it's this morning's night...
  const [start, end] = night(now.getDay());
  if (t < end) {
    if (start === end) return false;
    // ...which either began after midnight, or the evening before.
    return start < end ? t >= start : true;
  }
  // ...after it, tomorrow's, which can only have begun if it starts tonight.
  const [next, nextEnd] = night((now.getDay() + 1) % 7);
  return next > nextEnd && t >= next;
}
