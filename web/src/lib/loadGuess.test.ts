// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { CAP, TYPICAL_MS, loadGuess } from "./loadGuess";

describe("loadGuess", () => {
  it("starts at 0, reads 80% at the typical wait, and never passes the cap", () => {
    expect(loadGuess(0)).toBe(0);
    expect(loadGuess(500)).toBeGreaterThan(10);
    expect(loadGuess(TYPICAL_MS)).toBe(80);
    expect(loadGuess(6000)).toBeGreaterThan(90);
    expect(loadGuess(60_000)).toBe(CAP);
  });

  it("only ever climbs", () => {
    let last = -1;
    for (let t = 0; t < 20_000; t += 100) {
      const p = loadGuess(t);
      expect(p).toBeGreaterThanOrEqual(last);
      last = p;
    }
  });
});
