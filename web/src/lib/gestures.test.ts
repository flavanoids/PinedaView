// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { classifyGesture, LONG_PRESS_MS } from "./gestures";

const origin = { x: 100, y: 100 };

describe("classifyGesture", () => {
  it("is a tap when it stays put and is quick", () => {
    expect(classifyGesture(origin, { x: 103, y: 98 }, 120)).toBe("tap");
  });

  it("is a long-press when it stays put past the threshold", () => {
    expect(
      classifyGesture(origin, { x: 101, y: 101 }, LONG_PRESS_MS + 10),
    ).toBe("longpress");
  });

  it("reads horizontal swipes", () => {
    expect(classifyGesture(origin, { x: 200, y: 108 }, 200)).toBe(
      "swipe-right",
    );
    expect(classifyGesture(origin, { x: 20, y: 96 }, 200)).toBe("swipe-left");
  });

  it("reads vertical swipes", () => {
    expect(classifyGesture(origin, { x: 104, y: 220 }, 200)).toBe("swipe-down");
    expect(classifyGesture(origin, { x: 96, y: 10 }, 200)).toBe("swipe-up");
  });

  it("ignores a nudge that is neither a tap nor a full swipe", () => {
    expect(classifyGesture(origin, { x: 125, y: 100 }, 150)).toBe("none");
  });
});
