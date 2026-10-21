// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";
import { curvePath, nextSun, nightRuns, sunMarks, upcoming } from "./hourly";

const slots = (from: number, n: number) =>
  Array.from({ length: n }, (_, i) => ({ hour: (from + i) % 24 }));

describe("upcoming", () => {
  it("drops slots the clock has passed since the poll", () => {
    expect(upcoming(slots(14, 24), 15, 3).map((h) => h.hour)).toEqual([
      15, 16, 17,
    ]);
  });
  it("keeps the list as-is when the current hour isn't near its start", () => {
    expect(upcoming(slots(14, 24), 9, 2).map((h) => h.hour)).toEqual([14, 15]);
  });
});

describe("curvePath", () => {
  it("passes through every point without overshooting a peak", () => {
    const d = curvePath([
      { x: 0, y: 50 },
      { x: 10, y: 20 },
      { x: 20, y: 50 },
    ]);
    expect(d.startsWith("M0,50")).toBe(true);
    expect(d).toContain(" 10,20");
    // The peak's tangent is flat, so both control points sit at its height.
    expect(d).toMatch(/C[\d.]+,[\d.]+ [\d.]+,20 10,20C[\d.]+,20 /);
  });
});

describe("sunMarks", () => {
  const days = [
    { index: 0, date: "d0", sunrise: "7:20 AM", sunset: "6:58 PM" },
    { index: 1, date: "d1", sunrise: "7:21 AM", sunset: "6:57 PM" },
  ];
  it("places tonight's sunset in an afternoon window", () => {
    const marks = sunMarks(days, 15, 12);
    expect(marks.map((m) => m.kind)).toEqual(["Sunset"]);
    // 18:58 is 3.97h past the 15:00 column centre.
    expect(marks[0]!.x).toBeCloseTo(((3.9667 + 0.5) / 12) * 100, 1);
  });
  it("finds tomorrow's sunrise in an overnight window", () => {
    expect(sunMarks(days, 21, 12).map((m) => `${m.kind} ${m.time}`)).toEqual([
      "Sunrise 7:21 AM",
    ]);
  });
});

describe("nightRuns", () => {
  it("groups consecutive dark slots", () => {
    const hours = [true, false, false, true, false].map((isDay, hour) => ({
      hour,
      isDay,
    }));
    expect(nightRuns(hours)).toEqual([
      [1, 3],
      [4, 5],
    ]);
  });
});

describe("nextSun", () => {
  const days = [
    { index: 0, date: "d0", sunrise: "7:20 AM", sunset: "6:58 PM" },
    { index: 1, date: "d1", sunrise: "7:21 AM", sunset: "6:57 PM" },
  ];
  it("rolls over to tomorrow once the sun is down", () => {
    expect(nextSun(days, 19 * 60 + 30)).toEqual([
      { kind: "Sunrise", time: "7:21 AM", tomorrow: true },
      { kind: "Sunset", time: "6:57 PM", tomorrow: true },
    ]);
  });
  it("gives today's sunset in the afternoon", () => {
    expect(nextSun(days, 15 * 60)[0]).toEqual({
      kind: "Sunset",
      time: "6:58 PM",
      tomorrow: false,
    });
  });
});
