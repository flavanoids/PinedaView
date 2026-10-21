// SPDX-License-Identifier: Apache-2.0
import { beforeEach, describe, expect, it, vi } from "vitest";

import { prefs } from "./prefs.svelte";
import { shuffle } from "./shuffle.svelte";

describe("DynamicShuffleController", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    prefs.dynamic_shuffle = true;
    prefs.shuffle_hold_s = 15;
    shuffle.stop();
  });

  it("filters out photo and video cards from rotation", () => {
    shuffle.start(["weather", "photo", "calendar", "video"]);
    expect(shuffle.active).toBe(true);

    // Initial rest interval before first expansion
    vi.advanceTimersByTime(1000);
    expect(shuffle.expandedCard).toBe("weather");
    expect(shuffle.phase).toBe("expanding");

    // After expansion finishes, it dwells
    vi.advanceTimersByTime(450);
    expect(shuffle.phase).toBe("dwelling");

    // After dwell finishes, it contracts
    vi.advanceTimersByTime(15000);
    expect(shuffle.phase).toBe("contracting");

    // After contraction, it returns to idle and advances queue
    vi.advanceTimersByTime(400);
    expect(shuffle.phase).toBe("idle");
    expect(shuffle.expandedCard).toBe(null);

    // After rest, next card is calendar (photo was skipped!)
    vi.advanceTimersByTime(1000);
    expect(shuffle.expandedCard).toBe("calendar");
  });

  it("pauses and resumes cleanly", () => {
    shuffle.start(["weather", "calendar"]);
    vi.advanceTimersByTime(1000 + 450);
    expect(shuffle.phase).toBe("dwelling");

    shuffle.pause();
    vi.advanceTimersByTime(20000);
    // Should still be dwelling because it was paused
    expect(shuffle.phase).toBe("dwelling");

    shuffle.resume();
    vi.advanceTimersByTime(15000);
    expect(shuffle.phase).toBe("contracting");
  });

  it("stops when dynamic_shuffle is turned off", () => {
    shuffle.start(["weather", "calendar"]);
    expect(shuffle.active).toBe(true);

    prefs.dynamic_shuffle = false;
    shuffle.start(["weather", "calendar"]);
    expect(shuffle.active).toBe(false);
    expect(shuffle.expandedCard).toBe(null);
  });
});
