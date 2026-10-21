// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { isNightClock } from "./nightClock";

// Local-time constructor: month is 0-based. 2026-09-28 is a Monday.
const at = (day: number, hour: number, minute = 0): Date =>
  new Date(2026, 8, day, hour, minute);

describe("isNightClock", () => {
  it("runs midnight to 5am on weekday mornings", () => {
    expect(isNightClock(at(28, 0, 0))).toBe(true); // Mon 00:00
    expect(isNightClock(at(29, 4, 59))).toBe(true); // Tue 04:59
    expect(isNightClock(at(29, 5, 0))).toBe(false); // Tue 05:00
    expect(isNightClock(at(27, 23, 59))).toBe(false); // Sun 23:59
  });

  it("waits until 2am on Saturday and Sunday mornings", () => {
    expect(isNightClock(at(26, 1, 59))).toBe(false); // Sat 01:59
    expect(isNightClock(at(26, 2, 0))).toBe(true); // Sat 02:00
    expect(isNightClock(at(27, 4, 30))).toBe(true); // Sun 04:30
    expect(isNightClock(at(27, 5, 0))).toBe(false); // Sun 05:00
    expect(isNightClock(at(25, 23, 0))).toBe(false); // Fri 23:00
  });
});

describe("isNightClock with a custom schedule", () => {
  const evening = {
    weeknightStart: "22:30",
    weekendStart: "23:30",
    end: "06:30",
  };

  it("starts the evening before a weekday morning", () => {
    expect(isNightClock(at(27, 22, 29), evening)).toBe(false); // Sun 22:29 (→ Mon)
    expect(isNightClock(at(27, 22, 30), evening)).toBe(true); // Sun 22:30
    expect(isNightClock(at(28, 6, 29), evening)).toBe(true); // Mon 06:29
    expect(isNightClock(at(28, 6, 30), evening)).toBe(false); // Mon 06:30
  });

  it("uses the weekend start before Saturday and Sunday mornings", () => {
    expect(isNightClock(at(25, 23, 0), evening)).toBe(false); // Fri 23:00 (→ Sat)
    expect(isNightClock(at(25, 23, 30), evening)).toBe(true); // Fri 23:30
    expect(isNightClock(at(27, 0, 30), evening)).toBe(true); // Sun 00:30
  });

  it("skips a night whose start equals its end", () => {
    const noWeekends = { ...evening, weekendStart: "06:30" };
    expect(isNightClock(at(26, 2, 0), noWeekends)).toBe(false); // Sat 02:00
    expect(isNightClock(at(28, 2, 0), noWeekends)).toBe(true); // Mon 02:00
  });
});
