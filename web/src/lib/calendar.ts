// SPDX-License-Identifier: Apache-2.0
// Pure time math for the calendar card: the server sends a fixed window of
// events (a day back, eight ahead) and the card cuts it in local time, since
// only the display knows where its own midnight is.

export type CalendarView = "next12h" | "today" | "week";

export interface CalendarEvent {
  id: string;
  title: string;
  /** ISO datetime, or a bare `YYYY-MM-DD` for an all-day event. */
  start: string | null;
  end: string | null;
  allDay: boolean;
  location?: string | null;
  calendar?: string;
  color?: string | null;
}

export interface CalendarData {
  events?: CalendarEvent[];
  view?: CalendarView;
  maxEvents?: number;
}

/** An event pinned to real instants. All-day ends are exclusive midnights. */
export interface Span {
  event: CalendarEvent;
  start: Date;
  end: Date;
}

/** A segment of an event on a track, as fractions of the track's width. */
export interface Segment {
  id: string;
  color: string | null;
  from: number;
  to: number;
}

/** "2026-10-12" must mean local midnight; `new Date()` would read it as UTC
    and slide an all-day event into the evening before, west of Greenwich. */
function parseWhen(value: string, allDay: boolean): Date {
  if (allDay) {
    const [y = 0, m = 1, d = 1] = value.slice(0, 10).split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  return new Date(value);
}

export function toSpans(events: CalendarEvent[]): Span[] {
  const spans: Span[] = [];
  for (const event of events) {
    if (!event.start) continue;
    const start = parseWhen(event.start, event.allDay);
    let end = event.end ? parseWhen(event.end, event.allDay) : start;
    if (Number.isNaN(start.getTime())) continue;
    if (Number.isNaN(end.getTime()) || end <= start) {
      end = event.allDay ? addDays(start, 1) : start;
    }
    spans.push({ event, start, end });
  }
  return spans.sort((a, b) => a.start.getTime() - b.start.getTime());
}

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

function addHours(date: Date, hours: number): Date {
  return new Date(date.getTime() + hours * 3_600_000);
}

/** Touching a window, not just starting in it — a 2pm–5pm event is still
    "today" at 3pm. A zero-length event counts if it lands inside. */
export function overlaps(span: Span, from: Date, to: Date): boolean {
  if (span.end.getTime() === span.start.getTime()) {
    return span.start >= from && span.start < to;
  }
  return span.start < to && span.end > from;
}

/** The stretch of time the 12-hour and today tracks draw. Today runs from
    6am (or earlier, if something does) to midnight. */
export function trackWindow(
  view: "next12h" | "today",
  now: Date,
  spans: Span[],
): { from: Date; to: Date } {
  if (view === "next12h") {
    const from = new Date(now);
    from.setMinutes(0, 0, 0);
    return { from, to: addHours(from, 13) };
  }
  const midnight = startOfDay(now);
  const tomorrow = addDays(midnight, 1);
  let earliest = 6;
  for (const s of spans) {
    if (s.event.allDay || !overlaps(s, midnight, tomorrow)) continue;
    const startHour = s.start < midnight ? 0 : s.start.getHours();
    earliest = Math.min(earliest, startHour);
  }
  return { from: addHours(midnight, earliest), to: tomorrow };
}

/** Where on a [from, to) track each timed event sits. A floor of 1.5% keeps
    a quick reminder from vanishing into a hairline. */
export function segments(spans: Span[], from: Date, to: Date): Segment[] {
  const total = to.getTime() - from.getTime();
  const out: Segment[] = [];
  for (const s of spans) {
    if (s.event.allDay || !overlaps(s, from, to)) continue;
    const a = Math.max(0, (s.start.getTime() - from.getTime()) / total);
    const b = Math.min(1, (s.end.getTime() - from.getTime()) / total);
    out.push({
      id: `${s.event.id}@${s.start.getTime()}`,
      color: s.event.color ?? null,
      from: a,
      to: Math.min(1, Math.max(b, a + 0.015)),
    });
  }
  return out;
}

/** Fraction of the way through [from, to) — for the now marker. */
export function position(at: Date, from: Date, to: Date): number {
  const f = (at.getTime() - from.getTime()) / (to.getTime() - from.getTime());
  return Math.min(1, Math.max(0, f));
}

/** Events still to come (or under way) in the list views: all-day ones that
    touch the window first, then timed ones in start order. */
export function upcoming(
  spans: Span[],
  view: "next12h" | "today",
  now: Date,
): { allDay: Span[]; timed: Span[] } {
  const to =
    view === "next12h" ? addHours(now, 12) : addDays(startOfDay(now), 1);
  const live = spans.filter((s) => overlaps(s, now, to));
  return {
    allDay: live.filter((s) => s.event.allDay),
    timed: live.filter((s) => !s.event.allDay),
  };
}

export interface WeekDay {
  date: Date;
  /** Every event touching this day, all-day ones first. */
  spans: Span[];
  segments: Segment[];
}

/** Seven rows from today. Each day's track runs 6am to midnight; an event
    before 6 is pinned to the left edge rather than widening every row. */
export function weekDays(spans: Span[], now: Date): WeekDay[] {
  const today = startOfDay(now);
  return Array.from({ length: 7 }, (_, i) => {
    const date = addDays(today, i);
    const next = addDays(date, 1);
    const day = spans.filter((s) => overlaps(s, date, next));
    return {
      date,
      spans: [
        ...day.filter((s) => s.event.allDay),
        ...day.filter((s) => !s.event.allDay),
      ],
      segments: segments(day, addHours(date, 6), next),
    };
  });
}

/** "in 5 min", "in 1 hr 20 min", "now" — only for things inside two hours;
    past that the clock time alone reads faster. */
export function untilLabel(start: Date, end: Date, now: Date): string | null {
  if (start <= now) return end > now ? "now" : null;
  const minutes = Math.round((start.getTime() - now.getTime()) / 60_000);
  if (minutes >= 120) return null;
  if (minutes < 1) return "in a moment";
  if (minutes < 60) return `in ${minutes} min`;
  const rest = minutes - 60;
  return rest ? `in 1 hr ${rest} min` : "in 1 hr";
}

export function dayLabel(date: Date, now: Date): string {
  const diff = Math.round(
    (startOfDay(date).getTime() - startOfDay(now).getTime()) / 86_400_000,
  );
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return date.toLocaleDateString(undefined, { weekday: "short" });
}
