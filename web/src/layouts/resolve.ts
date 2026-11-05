// SPDX-License-Identifier: Apache-2.0
import material from "./material.json";
import square from "./square.json";
import wide from "./wide.json";

export interface Tier {
  id: string;
  maxWidth?: number;
  columns: string;
  heroColSpan: number;
  heroRowSpan: number;
  cellMinHeight: string;
}

export interface LayoutConfig {
  id: string;
  name: string;
  gap: string;
  tiers: Tier[];
}

const WIDE = wide as LayoutConfig;

const DEFAULT_TIER: Tier = {
  id: "wide",
  columns: "repeat(4, minmax(0, 1fr))",
  heroColSpan: 2,
  heroRowSpan: 2,
  cellMinHeight: "180px",
};

const LAYOUTS: Record<string, LayoutConfig> = {
  wide: WIDE,
  wide_grid: WIDE,
  square: square as LayoutConfig,
  square_grid: square as LayoutConfig,
  material: material as LayoutConfig,
};

export function getLayout(id: string): LayoutConfig {
  return LAYOUTS[id] ?? WIDE;
}

/** Smallest tier whose maxWidth still fits `width`; the last one has no cap.
    A screen standing taller than wide that would get that last tier (a wall
    panel turned on its side) gets two columns instead, the hero across both:
    four columns of a portrait panel are too narrow for their cards. Phones
    and tablets in portrait never reach the last tier, so they're as before. */
export function resolveTier(
  layout: LayoutConfig,
  width: number,
  height = 0,
): Tier {
  const ordered = [...layout.tiers].sort(
    (a, b) =>
      (a.maxWidth ?? Number.POSITIVE_INFINITY) -
      (b.maxWidth ?? Number.POSITIVE_INFINITY),
  );
  const fallback = ordered.at(-1) ?? DEFAULT_TIER;
  const tier =
    ordered.find((t) => width <= (t.maxWidth ?? Number.POSITIVE_INFINITY)) ??
    fallback;
  if (height > width && tier === fallback) {
    return {
      ...tier,
      id: "tall",
      columns: "repeat(2, minmax(0, 1fr))",
      heroColSpan: 2,
      heroRowSpan: 2,
    };
  }
  return tier;
}

/** The tiers that fit a fixed panel's whole height (no scrolling). */
export function fillsPanel(tier: Tier): boolean {
  return tier.id === "wide" || tier.id === "tall";
}
