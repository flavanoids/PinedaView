// SPDX-License-Identifier: Apache-2.0
import type { ViewModel } from "@pinedaview/protocol";
import { describe, expect, it } from "vitest";

import { isCardStale, pick } from "./types";

const view = {
  version: "v0",
  device_id: "d",
  profile_id: "p",
  state: "idle",
  theme: "warm",
  layout: "wide",
  units: "metric",
  hero: { kind: "card", card: "weather" },
  cards: [{ id: "clock", stale: false }],
  tickers: [{ kind: "clock" }],
  stale_stores: ["weather"],
  data: { weather: { current: { tempC: 20 } } },
} as unknown as ViewModel;

describe("pick", () => {
  it("reads a store payload out of view.data", () => {
    expect(
      pick<{ current: { tempC: number } }>(view, "weather")?.current.tempC,
    ).toBe(20);
    expect(pick(view, "missing")).toBeUndefined();
  });
});

describe("isCardStale", () => {
  it("trusts the per-card flag when present", () => {
    expect(isCardStale(view, "clock")).toBe(false);
  });
  it("falls back to stale_stores for the hero card", () => {
    expect(isCardStale(view, "weather")).toBe(true);
    expect(isCardStale(view, "moon")).toBe(false);
  });
  it("knows the commute and alerts cards' backing stores", () => {
    const withAlerts = {
      ...view,
      cards: [],
      stale_stores: ["alerts"],
    } as unknown as ViewModel;
    expect(isCardStale(withAlerts, "alerts")).toBe(true);
    expect(isCardStale(withAlerts, "commute")).toBe(false);
  });
});
