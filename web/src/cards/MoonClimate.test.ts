// SPDX-License-Identifier: Apache-2.0
import { render } from "@testing-library/svelte";
import type { ViewModel } from "@pinedaview/protocol";
import { describe, expect, it } from "vitest";

import MoonClimate from "./MoonClimate.svelte";
import type { TimerEntry } from "./types";

function inMinutes(label: string, minutes: number): TimerEntry {
  return {
    id: label,
    label,
    fires_at: new Date(Date.now() + minutes * 60_000).toISOString(),
    source: "antigua",
  };
}

function viewWith(timer: TimerEntry[] | undefined): ViewModel {
  return {
    version: "v0",
    device_id: "d",
    units: "imperial",
    cards: [],
    stale_stores: [],
    data: {
      moon: { phase: 0.5, illumination: 98, name: "Full Moon" },
      indoorClimate: { tempC: 22, humidity: 40 },
      ...(timer ? { timer } : {}),
    },
  } as unknown as ViewModel;
}

describe("MoonClimate mini card", () => {
  it("stays two halves with no timer running", () => {
    const { container } = render(MoonClimate, {
      props: { view: viewWith(undefined), stale: false, hero: false },
    });
    expect(container.querySelector(".cluster.quad")).toBeNull();
    expect(container.querySelector(".timer")).toBeNull();
  });

  it("turns 2×2 and shows the soonest timer with a count of the rest", () => {
    const { container } = render(MoonClimate, {
      props: {
        view: viewWith([inMinutes("eggs", 20), inMinutes("pasta", 5)]),
        stale: false,
        hero: false,
      },
    });
    expect(container.querySelector(".cluster.quad")).not.toBeNull();
    const timer = container.querySelector(".timer");
    expect(timer?.querySelector(".mini-label")?.textContent).toBe("pasta +1");
    expect(timer?.querySelector(".mini-value")?.textContent).toMatch(
      /^[45]:\d\d$/,
    );
    expect(container.querySelectorAll(".mini")).toHaveLength(4);
  });

  it("ignores finished timers", () => {
    const { container } = render(MoonClimate, {
      props: {
        view: viewWith([inMinutes("done", -1)]),
        stale: false,
        hero: false,
      },
    });
    expect(container.querySelector(".cluster.quad")).toBeNull();
  });
});
