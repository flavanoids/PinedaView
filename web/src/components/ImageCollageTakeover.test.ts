// SPDX-License-Identifier: Apache-2.0
import type { components } from "@pinedaview/protocol";
import { fireEvent, render } from "@testing-library/svelte";
import { tick } from "svelte";
import { beforeAll, describe, expect, it, vi } from "vitest";

import ImageCollageTakeover from "./ImageCollageTakeover.svelte";

type Takeover = components["schemas"]["Takeover"];

function collage(highlight: string | null = null): Takeover {
  const images = ["A", "B", "C", "D"].map((id, i) => ({
    id,
    url: `https://pics.example/${id}.jpg`,
    title: `Picture ${id}`,
    source: "pics.example",
    snippet: id === "B" ? "An elevated park." : "",
    aspect_ratio: i === 1 ? 0.66 : 1.5,
  }));
  return {
    card: { kind: "image_search", query: "the high line", images, highlight },
    shown_at: "2026-10-24T18:00:00Z",
    expires_at: new Date(Date.now() + 120_000).toISOString(),
  };
}

describe("ImageCollageTakeover", () => {
  beforeAll(() => {
    // jsdom has no layout; bind:clientWidth wants a ResizeObserver.
    globalThis.ResizeObserver ??= class {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    };
    // Transitions ask about reduced motion and run on WAAPI.
    window.matchMedia ??= ((query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })) as unknown as typeof window.matchMedia;
    Element.prototype.animate ??= (() => ({
      cancel: () => {},
      finish: () => {},
      onfinish: null,
      addEventListener: () => {},
      removeEventListener: () => {},
    })) as unknown as typeof Element.prototype.animate;
  });

  it("loads every picture through the server, and says which letters to ask", () => {
    const { container } = render(ImageCollageTakeover, {
      takeover: collage(),
    });
    expect(container.querySelector("h1")?.textContent).toBe("The high line");
    expect(container.querySelector(".hint")?.textContent).toContain("A–D");
    expect(container.querySelector(".hint")?.textContent).toContain(
      "show me A",
    );
    const photos = [...container.querySelectorAll<HTMLImageElement>(".photo")];
    expect(photos).toHaveLength(4);
    expect(photos[0]?.getAttribute("src")).toBe(
      "/api/takeover/images/A?size=full&v=2026-10-24T18%3A00%3A00Z",
    );
    const backdrop = container.querySelector(".backdrop");
    expect(backdrop?.getAttribute("src")).toContain("size=thumb");
    const tiles = [...container.querySelectorAll<HTMLElement>(".tile")];
    expect(tiles[0]?.classList.contains("hero")).toBe(true);
    expect(new Set(tiles.map((t) => t.style.gridArea)).size).toBe(4);
  });

  it("drops a picture that can't be had and closes up", async () => {
    const { container } = render(ImageCollageTakeover, {
      takeover: collage(),
    });
    const c = container.querySelectorAll(".photo")[2];
    if (!c) throw new Error("no third picture");
    vi.useFakeTimers();
    await fireEvent.error(c);
    await tick();
    expect(container.querySelectorAll(".tile")).toHaveLength(4); // tried again first
    vi.advanceTimersByTime(1500);
    await tick();
    const again = container.querySelectorAll(".photo")[2];
    expect(again?.getAttribute("src")).toContain("&again=1");
    if (!again) throw new Error("no third picture");
    await fireEvent.error(again);
    await tick();
    vi.useRealTimers();
    expect(container.querySelectorAll(".tile")).toHaveLength(3);
    expect(container.querySelector(".hint")?.textContent).toContain(
      "A, B and D",
    );
  });

  it("opens the highlighted picture full screen, whole", () => {
    const { container } = render(ImageCollageTakeover, {
      takeover: collage("b"),
    });
    const zoom = container.querySelector(".zoom");
    expect(zoom?.querySelector(".badge")?.textContent).toBe("B");
    expect(zoom?.querySelector("h2")?.textContent).toBe("Picture B");
    expect(zoom?.querySelector(".snippet")?.textContent).toBe(
      "An elevated park.",
    );
    expect(zoom?.querySelector(".zoom-photo")?.getAttribute("src")).toContain(
      "/api/takeover/images/B?size=full",
    );
    expect(zoom?.textContent).toContain("go back");
    // Its tile is where it lifted out of.
    expect(container.querySelector(".tile.lit .badge")?.textContent).toBe("B");
  });

  it("taps do what the voice does", async () => {
    const sent: unknown[] = [];
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (_url, init) => {
        sent.push(JSON.parse(String(init?.body)));
        return new Response("null", {
          headers: { "content-type": "application/json" },
        });
      });
    const { container } = render(ImageCollageTakeover, {
      takeover: collage("b"),
    });
    const tile = container.querySelectorAll<HTMLElement>(".tile")[2];
    const zoom = container.querySelector<HTMLElement>(".zoom");
    if (!tile || !zoom) throw new Error("no tile or zoom");
    await fireEvent.click(tile);
    await fireEvent.click(zoom);
    expect(sent).toEqual([{ highlight: "C" }, { highlight: null }]);
    fetchSpy.mockRestore();
  });

  it("lays a comparison out as two labelled sides", () => {
    const takeover = collage();
    const card = takeover.card as components["schemas"]["ImageSearchTakeover"];
    card.groups = [
      { label: "Fuji apples", ids: ["A", "B"] },
      { label: "Honeycrisp apples", ids: ["C", "D"] },
    ];
    const { container } = render(ImageCollageTakeover, { takeover });
    const sides = [...container.querySelectorAll(".side")];
    expect(
      sides.map((s) => s.querySelector(".side-label")?.textContent),
    ).toEqual(["Fuji apples", "Honeycrisp apples"]);
    expect(
      sides.map((s) =>
        [...s.querySelectorAll(".badge")].map((b) => b.textContent),
      ),
    ).toEqual([
      ["A", "B"],
      ["C", "D"],
    ]);
    expect(sides[1]?.querySelector(".tile.hero .badge")?.textContent).toBe("C");
  });
});
