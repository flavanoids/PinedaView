// SPDX-License-Identifier: Apache-2.0
/**
 * Small hours: the dashboard gives way to a lone clock. Each night is named
 * for the morning it ends on — before a weekday (Monday–Friday) morning it
 * starts at `weeknightStart`, before a Saturday or Sunday morning at
 * `weekendStart`, and it always ends at `end`. A start after the end time
 * ("23:00" → "06:00") begins the evening before; a start equal to the end
 * means that night has no night clock. Defaults: midnight on weeknights, 2am
 * at the weekend, both until 5am.
 */
export interface NightSchedule {
  weeknightStart: string;
  weekendStart: string;
  end: string;
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
  const end = minutes(schedule.end);
  const t = now.getHours() * 60 + now.getMinutes();
  // Before the end time it's this morning's night; after, tomorrow's.
  const morning = t < end ? now.getDay() : (now.getDay() + 1) % 7;
  const weekend = morning === 0 || morning === 6;
  const start = minutes(
    weekend ? schedule.weekendStart : schedule.weeknightStart,
  );
  if (start === end) return false;
  if (start < end) return t >= start && t < end; // starts after midnight
  return t >= start || t < end; // starts the evening before
}
