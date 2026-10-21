// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import {
  segments,
  toSpans,
  trackWindow,
  untilLabel,
  upcoming,
  weekDays,
  type CalendarEvent,
} from "./calendar";

const ev = (over: Partial<CalendarEvent>): CalendarEvent => ({
  id: over.title ?? "e",
  title: "e",
  start: null,
  end: null,
  allDay: false,
  ...over,
});

// Local wall-clock times throughout, so the tests mean the same thing in any TZ.
const at = (d: number, h: number, m = 0) => new Date(2026, 9, d, h, m);
const iso = (d: Date) => d.toISOString();

describe("toSpans", () => {
  it("reads an all-day date as local midnight, not UTC", () => {
    const [s] = toSpans([
      ev({ start: "2026-10-14", end: "2026-10-15", allDay: true }),
    ]);
    expect(s?.start).toEqual(new Date(2026, 9, 14));
    expect(s?.end).toEqual(new Date(2026, 9, 15));
  });

  it("skips events with no start and sorts the rest", () => {
    const spans = toSpans([
      ev({ title: "b", start: iso(at(12, 15)), end: iso(at(12, 16)) }),
      ev({ title: "none" }),
      ev({ title: "a", start: iso(at(12, 9)), end: iso(at(12, 10)) }),
    ]);
    expect(spans.map((s) => s.event.title)).toEqual(["a", "b"]);
  });
});

describe("upcoming", () => {
  const now = at(12, 14);
  const spans = toSpans([
    ev({ title: "done", start: iso(at(12, 9)), end: iso(at(12, 10)) }),
    ev({ title: "under way", start: iso(at(12, 13)), end: iso(at(12, 15)) }),
    ev({ title: "tonight", start: iso(at(12, 20)), end: iso(at(12, 21)) }),
    ev({ title: "early tomorrow", start: iso(at(13, 1)), end: iso(at(13, 2)) }),
    ev({ title: "bday", start: "2026-10-12", end: "2026-10-13", allDay: true }),
  ]);

  it("today keeps what's under way or ahead, up to midnight", () => {
    const { allDay, timed } = upcoming(spans, "today", now);
    expect(timed.map((s) => s.event.title)).toEqual(["under way", "tonight"]);
    expect(allDay.map((s) => s.event.title)).toEqual(["bday"]);
  });

  it("next 12 hours crosses midnight", () => {
    const { timed } = upcoming(spans, "next12h", now);
    expect(timed.map((s) => s.event.title)).toContain("early tomorrow");
  });
});

describe("trackWindow", () => {
  it("today starts at 6am unless something starts earlier", () => {
    const now = at(12, 14);
    expect(trackWindow("today", now, []).from).toEqual(at(12, 6));
    const early = toSpans([
      ev({ start: iso(at(12, 4, 30)), end: iso(at(12, 5)) }),
    ]);
    expect(trackWindow("today", now, early).from).toEqual(at(12, 4));
  });
});

describe("segments", () => {
  it("places events as fractions and clips to the window", () => {
    const spans = toSpans([
      ev({ title: "x", start: iso(at(12, 4)), end: iso(at(12, 9)) }),
      ev({ title: "y", start: iso(at(12, 12)), end: iso(at(12, 12)) }),
    ]);
    const segs = segments(spans, at(12, 6), at(12, 18));
    expect(segs[0]?.from).toBe(0);
    expect(segs[0]?.to).toBeCloseTo(0.25);
    // zero-length gets a visible floor
    const [, y] = segs;
    expect(y && y.to - y.from).toBeCloseTo(0.015);
  });
});

describe("weekDays", () => {
  it("gives seven days and spreads a multi-day event across them", () => {
    const spans = toSpans([
      ev({
        title: "trip",
        start: "2026-10-13",
        end: "2026-10-16",
        allDay: true,
      }),
    ]);
    const days = weekDays(spans, at(12, 9));
    expect(days).toHaveLength(7);
    expect(days.map((d) => d.spans.length)).toEqual([0, 1, 1, 1, 0, 0, 0]);
  });
});

describe("untilLabel", () => {
  const now = at(12, 14);
  it("counts down inside two hours", () => {
    expect(untilLabel(at(12, 14, 40), at(12, 15), now)).toBe("in 40 min");
    expect(untilLabel(at(12, 15, 20), at(12, 16), now)).toBe("in 1 hr 20 min");
    expect(untilLabel(at(12, 17), at(12, 18), now)).toBeNull();
  });
  it("says now for something under way", () => {
    expect(untilLabel(at(12, 13), at(12, 15), now)).toBe("now");
  });
});
