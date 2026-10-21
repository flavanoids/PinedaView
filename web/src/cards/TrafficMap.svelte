<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The traffic card's freeway map: the radar card's dark basemap + roads mosaic,
  zoomed in on home, with TranStar's live speeds drawn over it as one static
  SVG (see providers/traffic_map.py). Chips and attribution are the Traffic
  card's own, so they match the camera slides.
-->
<script lang="ts">
  import type { TrafficMap } from "./types";

  let { map }: { map: TrafficMap } = $props();
</script>

<div
  class="map"
  style:--map-cols={map.cols}
  style:--map-tx={`${map.focus.dx}%`}
  style:--map-ty={`${map.focus.dy}%`}
>
  <div class="mosaic">
    {#each map.basemap as tile (tile)}<img src={tile} alt="" />{/each}
  </div>
  <div class="mosaic roads">
    {#each map.roads as tile (tile)}<img src={tile} alt="" />{/each}
  </div>
  <svg class="mosaic speeds" viewBox="0 0 100 100" aria-hidden="true">
    <!-- Every casing first, then every colour, so neighbouring directions
         keep their dark edge without one painting over the other. -->
    {#each map.segments as s, i (i)}
      <polyline class="casing" class:crawl={s.level === "crawl"} points={s.d} />
    {/each}
    {#each map.segments as s, i (i)}
      <polyline class={s.level} points={s.d} />
    {/each}
    {#each map.incidents as m, i (i)}
      <circle
        class="incident"
        class:crash={m.crash}
        class:closure={m.kind === "closure"}
        class:flood={m.kind === "flood"}
        cx={m.x}
        cy={m.y}
        r={m.crash ? 0.95 : 0.72}
      >
        {#if m.desc}<title>{m.desc}</title>{/if}
      </circle>
    {/each}
    {#each map.cameras ?? [] as c (c.id)}
      <g class="cam-marker" transform="translate({c.x}, {c.y})">
        <circle class="cam-ring" r="1.3" />
        <circle class="cam-dot" r="0.6" />
        <title>{c.label}</title>
      </g>
    {/each}
  </svg>
  <span class="home" aria-hidden="true"></span>
  <div class="legend" aria-hidden="true">
    <span class="bar fast" title="≥50 mph"></span>
    <span class="bar ok" title="40–49 mph"></span>
    <span class="bar slow" title="30–39 mph"></span>
    <span class="bar crawl" title="<30 mph"></span>
  </div>
</div>

<style>
  .map {
    position: absolute;
    inset: 0;
    overflow: hidden;
    container-type: size;
  }
  .mosaic {
    position: absolute;
    left: 50%;
    top: 50%;
    /* ~10 miles across the card's longer side at zoom 12 (the 3×3 mosaic is
       ~16), so a tall cell is covered too. Room to spare for the focus shift
       (clamped to ±17% server-side). */
    width: max(160cqw, 160cqh);
    aspect-ratio: 1;
    display: grid;
    grid-template-columns: repeat(var(--map-cols, 1), 1fr);
    grid-auto-rows: 1fr;
    transform: translate(-50%, -50%)
      translate(var(--map-tx, 0), var(--map-ty, 0));
  }
  .mosaic img {
    display: block;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
  }
  /* Streets for orientation only — grey and quiet under the speeds. */
  .roads {
    filter: grayscale(1) brightness(1.4);
    opacity: 0.45;
  }
  .speeds {
    display: block;
    overflow: visible;
  }
  polyline {
    fill: none;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-width: 0.42;
  }
  polyline.casing {
    stroke: rgba(10, 8, 14, 0.8);
    stroke-width: 0.72;
  }
  polyline.casing.crawl {
    stroke-width: 0.95;
  }
  .fast {
    stroke: #3fbf5f;
  }
  .ok {
    stroke: #f2d43d;
  }
  .slow {
    stroke: #ff9a3d;
  }
  .crawl {
    stroke: #ff4d4d;
    stroke-width: 0.54;
    filter: drop-shadow(0 0 0.8px rgba(255, 77, 77, 0.75));
  }
  .none {
    stroke: #8a8792;
    opacity: 0.6;
  }
  circle.incident {
    fill: #ffc23d;
    stroke: rgba(10, 8, 14, 0.85);
    stroke-width: 0.22;
  }
  circle.incident.crash {
    fill: #ff4d5e;
    stroke: rgba(10, 8, 14, 0.95);
    stroke-width: 0.28;
    filter: drop-shadow(0 0 0.9px rgba(255, 77, 94, 0.85));
  }
  circle.incident.closure {
    fill: #ef4444;
    stroke: #ffffff;
    stroke-width: 0.3;
  }
  circle.incident.flood {
    fill: #38bdf8;
    stroke: rgba(10, 8, 14, 0.9);
    stroke-width: 0.28;
    filter: drop-shadow(0 0 0.9px rgba(56, 189, 248, 0.85));
  }
  .cam-marker .cam-ring {
    fill: rgba(15, 13, 19, 0.9);
    stroke: var(--accent, #6366f1);
    stroke-width: 0.28;
  }
  .cam-marker .cam-dot {
    fill: #ffffff;
  }
  /* "You are here", as on the radar card. */
  .home {
    position: absolute;
    left: 50%;
    top: 50%;
    width: calc(0.7rem * var(--ui-scale));
    height: calc(0.7rem * var(--ui-scale));
    transform: translate(-50%, -50%);
    border-radius: 50%;
    background: var(--accent);
    box-shadow:
      0 0 0 calc(0.18rem * var(--ui-scale))
        color-mix(in srgb, var(--stage) 70%, transparent),
      0 0 calc(0.6rem * var(--ui-scale)) calc(0.12rem * var(--ui-scale))
        color-mix(in srgb, var(--accent) 60%, transparent);
  }
  .legend {
    position: absolute;
    right: var(--space-2);
    top: var(--space-2);
    display: flex;
    gap: 2px;
    padding: calc(0.18rem * var(--ui-scale)) calc(0.35rem * var(--ui-scale));
    border-radius: var(--radius-pill);
    background: rgba(15, 13, 19, 0.75);
    backdrop-filter: blur(4px);
    pointer-events: none;
  }
  .bar {
    width: calc(0.35rem * var(--ui-scale));
    height: calc(0.18rem * var(--ui-scale));
    border-radius: 1px;
  }
  .bar.fast {
    background: #3fbf5f;
  }
  .bar.ok {
    background: #f2d43d;
  }
  .bar.slow {
    background: #ff9a3d;
  }
  .bar.crawl {
    background: #ff4d4d;
  }
  :global(.card.hero) .legend {
    right: var(--space-4);
    top: var(--space-4);
    gap: 4px;
  }
  :global(.card.hero) .bar {
    width: 10px;
    height: 4px;
  }
</style>
