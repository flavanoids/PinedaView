// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { mirror, reverse, schedule } from "./handoff";

describe("handoff schedule", () => {
  it("lands every part by the end, however many cards and figures", () => {
    for (const [cells, figures] of [
      [1, 4],
      [8, 5],
      [20, 5],
      [0, 0],
    ] as const) {
      const plan = schedule(cells, figures);
      const spans = [plan.photo, plan.swap, ...plan.cells, ...plan.figures];
      for (const [start, length] of spans) {
        expect(start).toBeGreaterThanOrEqual(0);
        expect(start + length).toBeLessThanOrEqual(1);
      }
      expect(plan.cells).toHaveLength(cells);
      expect(plan.figures).toHaveLength(figures);
    }
  });

  it("staggers the cards left to right", () => {
    const starts = schedule(5, 4).cells.map(([start]) => start);
    expect(starts).toEqual([...starts].sort((a, b) => a - b));
    expect(new Set(starts).size).toBe(5);
  });

  it("runs the way back as the same moves mirrored in time", () => {
    expect(mirror([0.1, 0.5])).toEqual([0.4, 0.5]);
    expect(
      reverse([
        { offset: 0, opacity: 1 },
        { offset: 0.3, opacity: 1 },
        { offset: 1, opacity: 0 },
      ]),
    ).toEqual([
      { offset: 0, opacity: 0 },
      { offset: 0.7, opacity: 1 },
      { offset: 1, opacity: 1 },
    ]);
  });
});
