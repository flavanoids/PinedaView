// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { DEFAULT_SUNRISE, DEFAULT_SUNSET, dayTints } from "./daypart";

const RISE = 7 * 60 + 13;
const SET = 19 * 60 + 2;

describe("dayTints", () => {
  it("is a full indigo wash in deep night", () => {
    expect(dayTints(2 * 60, RISE, SET)).toEqual({ warm: 0, cool: 0.14 });
  });
  it("peaks amber at sunrise with the night mostly drained", () => {
    const { warm, cool } = dayTints(RISE, RISE, SET);
    expect(warm).toBeCloseTo(0.18);
    expect(cool).toBeCloseTo(0.028);
  });
  it("is clear at midday", () => {
    expect(dayTints(13 * 60, RISE, SET)).toEqual({ warm: 0, cool: 0 });
  });
  it("peaks amber at sunset", () => {
    expect(dayTints(SET, RISE, SET).warm).toBeCloseTo(0.15);
  });
  it("is fully night an hour after sunset", () => {
    const { warm, cool } = dayTints(SET + 60, RISE, SET);
    expect(warm).toBe(0);
    expect(cool).toBeCloseTo(0.14);
  });
  it("falls back to default sun times before weather arrives", () => {
    expect(dayTints(DEFAULT_SUNRISE, null, null).warm).toBeCloseTo(0.18);
    expect(dayTints(DEFAULT_SUNSET, null, null).warm).toBeCloseTo(0.15);
  });
  it("stays within its peaks all day", () => {
    for (let t = 0; t < 24 * 60; t++) {
      const { warm, cool } = dayTints(t, RISE, SET);
      expect(warm).toBeGreaterThanOrEqual(0);
      expect(warm).toBeLessThanOrEqual(0.18);
      expect(cool).toBeGreaterThanOrEqual(0);
      expect(cool).toBeLessThanOrEqual(0.14);
    }
  });
});
