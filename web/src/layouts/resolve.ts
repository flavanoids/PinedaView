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

/** Smallest tier whose maxWidth still fits `width`; the last one has no cap. */
export function resolveTier(layout: LayoutConfig, width: number): Tier {
  const ordered = [...layout.tiers].sort(
    (a, b) =>
      (a.maxWidth ?? Number.POSITIVE_INFINITY) -
      (b.maxWidth ?? Number.POSITIVE_INFINITY),
  );
  const fallback = ordered.at(-1) ?? DEFAULT_TIER;
  return (
    ordered.find(
      (tier) => width <= (tier.maxWidth ?? Number.POSITIVE_INFINITY),
    ) ?? fallback
  );
}
