// SPDX-License-Identifier: Apache-2.0
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  allows,
  detectMotionTier,
  effectiveTier,
  motion,
  tierForFrameTime,
} from "./tier.svelte";

function stubEnvironment(opts: {
  cores?: number;
  memory?: number;
  reduce?: boolean;
}): void {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: opts.reduce === true && query.includes("reduced-motion"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.stubGlobal("navigator", {
    hardwareConcurrency: opts.cores ?? 4,
    deviceMemory: opts.memory ?? 4,
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("detectMotionTier", () => {
  it("forces lite when the user prefers reduced motion", () => {
    stubEnvironment({ cores: 16, memory: 16, reduce: true });
    expect(detectMotionTier()).toBe("lite");
  });
  it("returns lite on a weak device", () => {
    stubEnvironment({ cores: 4, memory: 2 });
    expect(detectMotionTier()).toBe("lite");
  });
  it("returns rich on a strong device", () => {
    stubEnvironment({ cores: 8, memory: 8 });
    expect(detectMotionTier()).toBe("rich");
  });
  it("returns standard in between", () => {
    stubEnvironment({ cores: 6, memory: 4 });
    expect(detectMotionTier()).toBe("standard");
  });
});

describe("allows", () => {
  it("gates a feature by the current tier", () => {
    motion.tier = "standard";
    motion.batterySaver = false;
    expect(allows("lite")).toBe(true);
    expect(allows("standard")).toBe(true);
    expect(allows("rich")).toBe(false);
  });
});

describe("battery saver", () => {
  it("forces the effective tier to lite without losing the preference", () => {
    motion.tier = "rich";
    motion.batterySaver = true;
    expect(effectiveTier()).toBe("lite");
    expect(allows("standard")).toBe(false);
    motion.batterySaver = false;
    expect(effectiveTier()).toBe("rich");
  });
});

describe("tierForFrameTime", () => {
  it("maps a measured median frame time to a tier", () => {
    expect(tierForFrameTime(12)).toBe("rich");
    expect(tierForFrameTime(25)).toBe("standard");
    expect(tierForFrameTime(50)).toBe("lite");
  });
});
