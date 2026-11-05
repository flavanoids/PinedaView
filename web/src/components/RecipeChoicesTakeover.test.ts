// SPDX-License-Identifier: Apache-2.0
import type { components } from "@pinedaview/protocol";
import { fireEvent, render } from "@testing-library/svelte";
import { tick } from "svelte";
import { beforeAll, describe, expect, it } from "vitest";

import RecipeChoicesTakeover from "./RecipeChoicesTakeover.svelte";

type Takeover = components["schemas"]["Takeover"];

function choices(highlight: string | null = null): Takeover {
  const ids = ["A1", "A2", "A3", "B1", "C1", "C2"];
  return {
    card: {
      kind: "recipe_choices",
      dish: "chia seed pudding",
      images: ids.map((id) => ({
        id,
        url: `https://pics.example/${id}.jpg`,
        title: "",
        source: "",
        snippet: "",
        aspect_ratio: 1,
      })),
      choices: [
        {
          id: "A",
          title: "Easy Chia Pudding",
          source: "Minimalist Baker",
          rating: 4.9,
          rating_count: 1240,
          total_min: 10,
          servings: "serves 2",
          images: ["A1", "A2", "A3"],
        },
        {
          id: "B",
          title: "Overnight Chia Pudding",
          source: "Allrecipes",
          rating: 0,
          rating_count: 0,
          total_min: 75,
          servings: "makes 1 loaf",
          images: ["B1"],
        },
        {
          id: "C",
          title: "Chocolate Chia Pudding",
          source: "",
          rating: 4.5,
          rating_count: 0,
          total_min: 0,
          servings: "makes 12 slices",
          images: ["C1", "C2"],
        },
      ],
      highlight,
    },
    shown_at: "2026-10-25T18:00:00Z",
    expires_at: new Date(Date.now() + 120_000).toISOString(),
  };
}

describe("RecipeChoicesTakeover", () => {
  beforeAll(() => {
    window.matchMedia ??= ((query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })) as unknown as typeof window.matchMedia;
  });

  it("puts each recipe up with its letter, photos and what it is", () => {
    const { container } = render(RecipeChoicesTakeover, {
      takeover: choices(),
    });
    expect(container.querySelector("h1")?.textContent).toBe(
      "Chia seed pudding",
    );
    expect(container.querySelector(".hint")?.textContent).toContain(
      "“A”, “B” or “C”",
    );
    const cols = [...container.querySelectorAll(".choice")];
    expect(cols.map((c) => c.querySelector(".badge")?.textContent)).toEqual([
      "A",
      "B",
      "C",
    ]);
    expect(cols[0]!.querySelectorAll(".thumb")).toHaveLength(2);
    expect(cols[1]!.querySelector(".photos")?.classList).toContain("alone");
    const stats = (i: number) =>
      [...cols[i]!.querySelectorAll(".stats > div")].map((d) =>
        [d.querySelector("dd"), d.querySelector("dt")].map((e) =>
          e?.textContent?.replace(/\s+/g, " ").trim(),
        ),
      );
    expect(stats(0)).toEqual([
      ["★ 4.9", "1.2k ratings"],
      ["10 min", "total time"],
      ["2", "servings"],
    ]);
    expect(stats(1)).toEqual([
      ["—", "rating"],
      ["1h 15m", "total time"],
      ["1 loaf", "makes"],
    ]);
    expect(stats(2)[2]).toEqual(["12", "slices"]);
    const src = cols[0]!.querySelector<HTMLImageElement>(".hero .photo")?.src;
    expect(src).toContain("/api/takeover/images/A1?size=full");
    expect(
      cols[0]!.querySelector<HTMLImageElement>(".thumb .photo")?.src,
    ).toContain("/api/takeover/images/A2?size=thumb");
  });

  it("lights the highlighted choice", () => {
    const { container } = render(RecipeChoicesTakeover, {
      takeover: choices("b"),
    });
    const lit = container.querySelectorAll(".choice.lit");
    expect(lit).toHaveLength(1);
    expect(lit[0]!.querySelector(".badge")?.textContent).toBe("B");
  });

  it("keeps a recipe whose pictures all fail, letter and title", async () => {
    const { container } = render(RecipeChoicesTakeover, {
      takeover: choices(),
    });
    const b = () => container.querySelectorAll(".choice")[1]!;
    const img = b().querySelector<HTMLImageElement>(".hero .photo")!;
    await fireEvent.error(img);
    await new Promise((r) => setTimeout(r, 1600));
    await tick();
    await fireEvent.error(b().querySelector<HTMLImageElement>(".hero .photo")!);
    await tick();
    expect(b().querySelector(".hero .photo")).toBeNull();
    expect(b().querySelector(".hero .nophoto")).not.toBeNull();
    expect(b().querySelector(".badge")?.textContent).toBe("B");
    expect(b().querySelector("h2")?.textContent).toBe("Overnight Chia Pudding");
  });
});
