// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { placeSteps, type Place } from "./stepLadder";

describe("placeSteps", () => {
  // 5 steps, step 3 being read, a 1000px ladder: current at 100px (300px
  // tall), sides at 52px, the one before 130px tall.
  const ladder = placeSteps(5, 2, 1000, 100, 52, 300, 130);

  it("puts the current step at its anchor, full size and strength", () => {
    expect(ladder.steps[2]).toEqual({
      top: 250,
      size: 100,
      opacity: 1,
      role: "current",
    });
  });

  it("stacks the steps either side clear of it, smaller and dimmed", () => {
    const [prev, cur, next] = ladder.steps.slice(1, 4) as [Place, Place, Place];
    expect(prev.top + 130).toBeLessThan(cur.top); // ends above it
    expect(next.top).toBeGreaterThan(cur.top + 300); // starts below it
    expect(prev.size).toBe(52);
    expect(next.opacity).toBeGreaterThan(prev.opacity);
  });

  it("parks the rest out of sight just past either end", () => {
    const [first, prev, , , last] = ladder.steps as Place[] & { length: 5 };
    expect(first?.opacity).toBe(0);
    expect(first!.top).toBeLessThan(prev!.top);
    expect(last?.opacity).toBe(0);
    expect(last!.top).toBeGreaterThanOrEqual(1000);
  });

  it("shows the end note only on the last step, where the next would be", () => {
    expect(ladder.end.opacity).toBe(0);
    const last = placeSteps(3, 2, 1000, 100, 52, 300, 130);
    expect(last.end.opacity).toBeGreaterThan(0);
    expect(last.end.top).toBe(250 + 300 + 55);
  });

  it("keeps the current step's place on step one, with nothing above", () => {
    const first = placeSteps(3, 0, 1000, 100, 52, 300, 0);
    expect(first.steps[0]?.top).toBe(250);
  });
});
