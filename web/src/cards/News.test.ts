// SPDX-License-Identifier: Apache-2.0
import { render } from "@testing-library/svelte";
import type { ViewModel } from "@pinedaview/protocol";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import News from "./News.svelte";
import type { NewsStory } from "./types";

function viewWith(stories: NewsStory[]): ViewModel {
  return {
    version: "v0",
    device_id: "d",
    cards: [],
    stale_stores: [],
    data: { news: { stories } },
  } as unknown as ViewModel;
}

const HOURS_AGO = (h: number): string =>
  new Date(Date.now() - h * 3_600_000).toISOString();

const MIDTERMS: NewsStory = {
  id: "0123456789ab",
  title:
    "On the ground in Ohio's 9th District, the battleground of the midterms",
  url: "https://www.npr.org/2026/10/10/nx-s1-5965798/ohio-9th-district",
  outlet: "NPR",
  beat: "US",
  published: HOURS_AGO(3),
  image: "/api/news/0123456789ab.jpg",
  tint: "#355980",
};
const RHEAS: NewsStory = {
  id: "ba9876543210",
  title: "These women are bringing Darwin's rheas back to Chilean Patagonia",
  url: "https://news.mongabay.com/video/2026/10/rheas",
  outlet: "Mongabay",
  beat: "Good news",
  published: HOURS_AGO(30),
  image: null,
  tint: null,
};

describe("News card", () => {
  beforeEach(() => {
    // jsdom has no ResizeObserver; the card's fitText only needs it to exist.
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the headline with its beat, outlet and age", () => {
    const { getAllByText } = render(News, {
      view: viewWith([MIDTERMS, RHEAS]),
      stale: false,
      hero: false,
    });
    // Cycler renders two crossfade layers, so each string can appear twice.
    expect(getAllByText(MIDTERMS.title).length).toBeGreaterThan(0);
    expect(getAllByText("US").length).toBeGreaterThan(0);
    expect(getAllByText("NPR · 3h").length).toBeGreaterThan(0);
  });

  it("puts the story's own blurred picture behind it, tinted to match", () => {
    const { container } = render(News, {
      view: viewWith([MIDTERMS]),
      stale: false,
      hero: false,
    });
    const story = container.querySelector<HTMLElement>(".story.art");
    expect(story?.style.getPropertyValue("--tint")).toBe("#355980");
    expect(story?.querySelector("img.backdrop")?.getAttribute("src")).toBe(
      "/api/news/0123456789ab.jpg",
    );
  });

  it("falls back to the card's own colours for a story without a picture", () => {
    const { container } = render(News, {
      view: viewWith([RHEAS]),
      stale: false,
      hero: false,
    });
    expect(container.querySelector(".story.art")).toBeNull();
    expect(container.querySelector("img.backdrop")).toBeNull();
    expect(container.textContent).toContain("Mongabay · 30h");
  });

  it("shows a QR that opens the article at the outlet", async () => {
    const { container } = render(News, {
      view: viewWith([MIDTERMS]),
      stale: false,
      hero: false,
    });
    await vi.waitFor(() => {
      expect(container.querySelectorAll("a.qr svg").length).toBeGreaterThan(0);
    });
    const qr = container.querySelector<HTMLAnchorElement>("a.qr");
    expect(qr?.getAttribute("href")).toBe(MIDTERMS.url);
    expect(qr?.getAttribute("aria-label")).toBe("Read the story at NPR");
  });

  it("waits while the store is empty", () => {
    const { container } = render(News, {
      view: viewWith([]),
      stale: false,
      hero: false,
    });
    expect(container.textContent).toContain("…");
    expect(container.querySelector("a.qr")).toBeNull();
  });
});
