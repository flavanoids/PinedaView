// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";
import {
  loadingDetail,
  loadingEyebrow,
  loadingHeadline,
  loadingPercent,
  type Loading,
} from "./loadingProgress";

const at = (s: number) => new Date(Date.UTC(2026, 9, 10, 12, 0, s));
const iso = (s: number) => at(s).toISOString();

describe("loading progress", () => {
  it("eases within a stage without reaching its cap", () => {
    const l: Loading = { stage: "finding", since: iso(0), stageAt: iso(0) };
    expect(loadingPercent(l, at(0))).toBe(4);
    expect(loadingHeadline({ ...l, title: "finally" })).toBe("“finally”");
    const later = loadingPercent(l, at(30));
    expect(later).toBeGreaterThan(40);
    expect(later).toBeLessThanOrEqual(45);
  });

  it("picks up from the next stage's floor and keeps climbing", () => {
    const l: Loading = {
      stage: "starting",
      since: iso(0),
      stageAt: iso(5),
      title: "Halo",
    };
    expect(loadingPercent(l, at(5))).toBe(45);
    expect(loadingPercent(l, at(12))).toBeGreaterThan(70);
    expect(loadingPercent(l, at(59))).toBeLessThan(100);
    expect(loadingHeadline(l)).toBe("Halo");
    expect(loadingEyebrow(l)).toBe("Getting it ready");
  });

  it("gets more reassuring the longer a start takes", () => {
    const l: Loading = { stage: "starting", since: iso(0), stageAt: iso(0) };
    expect(loadingDetail(l, at(1))).toMatch(/Found it/);
    expect(loadingDetail(l, at(20))).toMatch(/slow/);
    expect(loadingDetail(l, at(50))).toMatch(/ask me again/);
  });

  it("shows Antigua's own words when it fails", () => {
    const l: Loading = {
      stage: "failed",
      since: "",
      stageAt: "",
      text: "I couldn't find pop.",
    };
    expect(loadingHeadline(l)).toBe("That didn't start");
    expect(loadingDetail(l, at(0))).toBe("I couldn't find pop.");
  });
});
