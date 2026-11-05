// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { chimeForFinishedTimers } from "./timerSound.svelte";

const timer = (id: string, firesAt: number, kind = "timer") => ({
  id,
  label: "Pasta",
  fires_at: new Date(firesAt).toISOString(),
  kind,
});

describe("chimeForFinishedTimers", () => {
  it("chimes when a timer leaves at its due time, not when cancelled", () => {
    const due = 1_000_000;
    chimeForFinishedTimers([timer("a", due), timer("b", due + 600_000)], 0);
    // "b" cancelled early: no chime.
    expect(chimeForFinishedTimers([timer("a", due)], due - 300_000)).toBe(
      false,
    );
    // "a" ran out.
    expect(chimeForFinishedTimers([], due)).toBe(true);
    // Nothing left to finish.
    expect(chimeForFinishedTimers([], due + 1)).toBe(false);
  });

  it("leaves alarms to their takeover", () => {
    chimeForFinishedTimers([timer("x", 5_000, "alarm")], 0);
    expect(chimeForFinishedTimers([], 5_000)).toBe(false);
  });

  it("leaves Antigua's timers to Antigua, which rings them itself", () => {
    chimeForFinishedTimers([{ ...timer("y", 5_000), source: "antigua" }], 0);
    expect(chimeForFinishedTimers([], 5_000)).toBe(false);
  });
});
