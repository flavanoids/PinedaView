// SPDX-License-Identifier: Apache-2.0
import { render } from "@testing-library/svelte";
import type { ViewModel } from "@pinedaview/protocol";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Traffic, { forgetTrafficResume } from "./Traffic.svelte";
import type { TrafficCam, TrafficMap } from "./types";

function cam(id: string, extra: Partial<TrafficCam> = {}): TrafficCam {
  return {
    id,
    label: `Road @ ${id}`,
    src: `/api/cams/${id}.jpg?v=1`,
    frames: [],
    frameMs: 300,
    capturedAt: "2026-09-29T12:54:00-05:00",
    stale: false,
    ...extra,
  };
}

const MAP: TrafficMap = {
  cols: 3,
  focus: { dx: 0, dy: 0 },
  basemap: [],
  roads: [],
  segments: [{ d: "10,10 20,20", level: "crawl" }],
  incidents: [{ x: 50, y: 50, crash: true }],
  slowest: { label: "I-10 EB · Kirkwood → BW-8 West", mph: 24 },
  updatedAt: "2026-10-08T13:26:35-05:00",
  stale: false,
};

function viewWith(
  active: boolean,
  cams: TrafficCam[],
  map: TrafficMap | null = null,
): ViewModel {
  return {
    version: "v0",
    device_id: "d",
    cards: [],
    stale_stores: [],
    data: {
      dailyContent: { affirmations: [{ text: "A quote.", author: "A" }] },
      traffic: { active, cams, map },
    },
  } as unknown as ViewModel;
}

/** What the visible layer shows: a camera id, or its placeholder text. */
function showing(container: HTMLElement): string | undefined {
  const layer = container.querySelector(".layer.show");
  if (layer?.querySelector(".speeds")) return "map";
  const img = layer?.querySelector("img");
  if (img) return img.getAttribute("src")?.match(/cams\/(\d+)/)?.[1];
  return layer?.querySelector(".waiting")?.textContent ?? undefined;
}

describe("Traffic card", () => {
  beforeEach(() => {
    forgetTrafficResume();
    vi.useFakeTimers();
    // jsdom has no ResizeObserver; the quote's fitText only needs it to exist.
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("loops Cam 1 → 2 → 3 → 4 at 8s each, never a quote", async () => {
    const cams = ["407", "408", "614", "324"].map((id) => cam(id));
    const { container } = render(Traffic, {
      view: viewWith(true, cams),
      stale: false,
      hero: false,
    });

    const seen = [showing(container)];
    for (let i = 0; i < 8; i++) {
      await vi.advanceTimersByTimeAsync(8_000);
      seen.push(showing(container));
    }
    expect(seen).toEqual([
      "407",
      "408",
      "614",
      "324",
      "407",
      "408",
      "614",
      "324",
      "407",
    ]);
    expect(container.querySelector(".quote")).toBeNull();
  });

  it("shows no quotes outside a window, just a quiet note", async () => {
    const { container } = render(Traffic, {
      view: viewWith(false, []),
      stale: false,
      hero: false,
    });
    expect(showing(container)).toBe("Traffic cams are off for now");
    await vi.advanceTimersByTimeAsync(30_000);
    expect(showing(container)).toBe("Traffic cams are off for now");
    expect(container.querySelector("img")).toBeNull();
  });

  it("captions the camera and credits TranStar; a late capture is amber", () => {
    const { container } = render(Traffic, {
      view: viewWith(true, [cam("407", { stale: true })]),
      stale: false,
      hero: false,
    });
    const layer = container.querySelector(".layer.show");
    expect(layer?.querySelector(".where")?.textContent).toBe("Road @ 407");
    expect(layer?.querySelector(".attribution")?.textContent).toBe(
      "Houston TranStar",
    );
    // 12:54 -05:00 → the radar's "h:mm AM/PM" style, in the viewer's zone.
    expect(layer?.querySelector(".when")?.textContent).toMatch(
      /^\d{1,2}:\d{2} (AM|PM)$/,
    );
    expect(layer?.querySelector(".when.late")).not.toBeNull();
    const img = container.querySelector(".layer.show img");
    expect(img?.getAttribute("alt")).toBe("Traffic camera: Road @ 407");
  });

  it("plays a flipbook camera's frames while it's showing", async () => {
    const frames = [1, 2, 3].map((n) => `/api/cams/324-${n}.jpg?v=1`);
    const { container } = render(Traffic, {
      view: viewWith(true, [cam("324", { frames })]),
      stale: false,
      hero: false,
    });
    const src = () =>
      container.querySelector(".layer.show img")?.getAttribute("src");
    expect(src()).toBe(frames[0]);
    await vi.advanceTimersByTimeAsync(300);
    expect(src()).toBe(frames[1]);
    await vi.advanceTimersByTimeAsync(300);
    expect(src()).toBe(frames[2]);
  });

  it("leads with the freeway map held 40s, then 8s per cam", async () => {
    const { container } = render(Traffic, {
      view: viewWith(true, [cam("407"), cam("408")], MAP),
      stale: false,
      hero: false,
    });
    // The map holds 40s, each cam 8s.
    const seen = [showing(container)];
    for (const ms of [39_000, 1_000, 7_000, 1_000, 8_000, 39_000, 1_000]) {
      await vi.advanceTimersByTimeAsync(ms);
      seen.push(showing(container));
    }
    expect(seen).toEqual([
      "map",
      "map",
      "407",
      "407",
      "408",
      "map",
      "map",
      "407",
    ]);
  });

  it("picks up where it left off when remounted (Alternate's cards phase)", async () => {
    const props = {
      view: viewWith(true, [cam("407"), cam("408")], MAP),
      stale: false,
      hero: false,
    };
    // 30s of cards: the map, 10s of its hold left.
    const first = render(Traffic, props);
    await vi.advanceTimersByTimeAsync(30_000);
    first.unmount();
    // The next phase finishes the map's hold, then moves on to the cams.
    const { container } = render(Traffic, props);
    expect(showing(container)).toBe("map");
    await vi.advanceTimersByTimeAsync(10_000);
    expect(showing(container)).toBe("407");
    await vi.advanceTimersByTimeAsync(8_000);
    expect(showing(container)).toBe("408");
  });

  it("captions the map with the slowest stretch and draws incidents", () => {
    const { container } = render(Traffic, {
      view: viewWith(true, [], MAP),
      stale: false,
      hero: false,
    });
    const layer = container.querySelector(".layer.show");
    expect(layer?.querySelector(".where")?.textContent).toBe(
      "24 mph · I-10 EB · Kirkwood → BW-8 West",
    );
    expect(layer?.querySelector("polyline.crawl")).not.toBeNull();
    expect(layer?.querySelector("circle.crash")).not.toBeNull();
  });

  it("captions the map with delay and renders camera markers and incident kinds", () => {
    const enrichedMap: TrafficMap = {
      ...MAP,
      slowest: { label: "I-10 EB · Kirkwood → BW-8 West", mph: 24, delay: 15 },
      cameras: [{ id: "407", label: "US-290 @ Pinemont", x: 45, y: 55 }],
      incidents: [
        { x: 50, y: 50, crash: true, kind: "crash", desc: "Major Crash" },
        { x: 30, y: 40, crash: false, kind: "flood", desc: "High Water" },
      ],
    };
    const { container } = render(Traffic, {
      view: viewWith(true, [], enrichedMap),
      stale: false,
      hero: false,
    });
    const layer = container.querySelector(".layer.show");
    expect(layer?.querySelector(".where")?.textContent).toBe(
      "24 mph (+15m) · I-10 EB · Kirkwood → BW-8 West",
    );
    expect(layer?.querySelector(".cam-marker")).not.toBeNull();
    expect(layer?.querySelector("circle.flood")).not.toBeNull();
    expect(layer?.querySelector(".legend")).not.toBeNull();
  });

  it("rotates through multiple traffic alerts during the map hold", async () => {
    const multiAlertMap: TrafficMap = {
      ...MAP,
      alerts: [
        { type: "slow", text: "24 mph · I-10 EB" },
        { type: "crash", text: "Crash · 610 West Loop" },
      ],
    };
    const { container } = render(Traffic, {
      view: viewWith(true, [], multiAlertMap),
      stale: false,
      hero: false,
    });
    const where = () =>
      container.querySelector(".layer.show .where")?.textContent;
    expect(where()).toBe("24 mph · I-10 EB");
    await vi.advanceTimersByTimeAsync(9_000);
    expect(where()).toBe("Crash · 610 West Loop");
    await vi.advanceTimersByTimeAsync(9_000);
    expect(where()).toBe("24 mph · I-10 EB");
  });
});
