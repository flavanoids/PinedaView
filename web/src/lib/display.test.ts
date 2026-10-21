// SPDX-License-Identifier: Apache-2.0
import { afterEach, describe, expect, it } from "vitest";

import { detectScale } from "./display.svelte";

function panel(w: number, h: number, dpr: number): void {
  Object.defineProperty(window, "innerWidth", { value: w, configurable: true });
  Object.defineProperty(window, "innerHeight", {
    value: h,
    configurable: true,
  });
  Object.defineProperty(window, "devicePixelRatio", {
    value: dpr,
    configurable: true,
  });
}

afterEach(() => panel(1024, 768, 1));

describe("detectScale", () => {
  it("nudges a dense little handset down", () => {
    panel(390, 844, 3);
    expect(detectScale()).toBe(0.85);
  });

  it("keeps a hi-dpi portrait tablet at parity", () => {
    panel(820, 1180, 2);
    expect(detectScale()).toBe(1);
  });

  it("nudges a coarse 1x tablet up so it reads from a distance", () => {
    panel(1024, 768, 1);
    expect(detectScale()).toBe(1.3);
  });

  it("scales a large low-density display up the most", () => {
    panel(1280, 1024, 1);
    expect(detectScale()).toBe(1.42);
  });

  it("stays within bounds", () => {
    panel(3840, 2160, 1);
    const s = detectScale();
    expect(s).toBeGreaterThanOrEqual(0.8);
    expect(s).toBeLessThanOrEqual(1.7);
  });
});
