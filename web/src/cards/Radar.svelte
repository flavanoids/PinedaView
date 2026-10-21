<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { timeOfDay } from "../lib/format";
  import type { CardProps, RadarData } from "./types";
  import Placeholder from "../components/Placeholder.svelte";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();
  const data = $derived(pick<RadarData>(view, "radar"));
  // A still image of the newest frame, refreshed with each 10-minute poll. The
  // old ~2-hour timelapse never let the page go idle and was ~70% of the Pi
  // kiosk's CPU (DECISIONS 0024); the storm-track arrows carry the "where is it
  // heading" the loop used to show, for the cost of one static SVG.
  const frame = $derived(data?.frames?.at(-1));
  const storms = $derived(data?.storms ?? []);
  const basemap = $derived(data?.basemap ?? []);
  const roads = $derived(data?.roads ?? []);
  const cols = $derived(data?.cols ?? 1);
  const dx = $derived(data?.focus?.dx ?? 0);
  const dy = $derived(data?.focus?.dy ?? 0);

  const stamp = $derived.by(() => {
    const iso = frame?.time ?? data?.generated_at;
    if (!iso) return null;
    return timeOfDay(new Date(iso));
  });

  // Arrowhead for a track, in the mosaic's 0–100 viewBox (the mosaic is 4×
  // the card, so 1 unit ≈ a quarter of a percent of the card's width).
  const HEAD = 1;
  function head(s: { x: number; y: number; x2: number; y2: number }): string {
    const a = Math.atan2(s.y2 - s.y, s.x2 - s.x);
    const p = (d: number): string =>
      `${s.x2 - HEAD * Math.cos(a + d)},${s.y2 - HEAD * Math.sin(a + d)}`;
    return `${s.x2},${s.y2} ${p(0.45)} ${p(-0.45)}`;
  }
  const moving = (s: {
    x: number;
    y: number;
    x2: number;
    y2: number;
  }): boolean => Math.hypot(s.x2 - s.x, s.y2 - s.y) > HEAD;
</script>

<Card accent="radar" {hero} bleed={!!frame}>
  <div
    class="frame"
    style:--radar-cols={cols}
    style:--radar-tx={`${dx}%`}
    style:--radar-ty={`${dy}%`}
  >
    {#if frame}
      {#if basemap.length}
        <div class="mosaic base">
          {#each basemap as tile (tile)}<img src={tile} alt="" />{/each}
        </div>
      {/if}
      {#if roads.length}
        <div class="mosaic roads">
          {#each roads as tile (tile)}<img src={tile} alt="" />{/each}
        </div>
      {/if}
      <div class="mosaic">
        {#each frame.tiles as tile (tile)}<img src={tile} alt="" />{/each}
      </div>
      {#if storms.length}
        <svg class="mosaic tracks" viewBox="0 0 100 100" aria-hidden="true">
          {#each storms as s, i (i)}
            <g class:hail={s.hail} class:rotation={s.rotation}>
              {#if moving(s)}
                <line class="halo" x1={s.x} y1={s.y} x2={s.x2} y2={s.y2} />
                <line x1={s.x} y1={s.y} x2={s.x2} y2={s.y2} />
                <polygon points={head(s)} />
              {/if}
              <circle cx={s.x} cy={s.y} r="0.41" />
            </g>
          {/each}
        </svg>
      {/if}
      <span class="home" aria-hidden="true"></span>
      <span class="chip label"
        >Radar{storms.length ? " · 30-min tracks" : ""}</span
      >
      {#if stamp}
        <span class="chip stamp" class:stale>{stamp}</span>
      {/if}
      <span class="attribution">Esri · RainViewer</span>
    {:else}
      <Placeholder label="Waiting for radar…" shape="map" />
    {/if}
  </div>
</Card>

<style>
  .frame {
    position: relative;
    align-self: stretch;
    flex: 1;
    /* Height comes from the flex chain (bleed card → body → frame); this floor
       only matters in the scrolling layout, where the cell collapses toward
       --cell-min. */
    min-height: var(--cell-min);
    border-radius: inherit;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .mosaic {
    position: absolute;
    left: 50%;
    top: 50%;
    /* Oversized so it covers the card at any card aspect ratio and still has
       margin for the focus shift (clamped to ±14% server-side). Bigger than
       "just cover" also crops the wide 3×3 mosaic down to a tighter view. */
    width: 400%;
    aspect-ratio: 1;
    display: grid;
    grid-template-columns: repeat(var(--radar-cols, 1), 1fr);
    grid-auto-rows: 1fr;
    transform: translate(-50%, -50%)
      translate(var(--radar-tx, 0), var(--radar-ty, 0));
  }
  /* Storm tracks: dot where the cell is now, arrow to where it'll be in 30
     minutes. Dark outline under a light fill so they read over any echo
     colour; amber for likely hail, red for detected rotation. */
  .tracks {
    display: block;
    overflow: visible;
    pointer-events: none;
    --track: #f4f1f6;
  }
  .tracks g {
    stroke: rgba(10, 8, 14, 0.75);
    stroke-width: 0.17;
    paint-order: stroke;
    fill: var(--track);
  }
  .tracks line {
    stroke: var(--track);
    stroke-width: 0.24;
    stroke-linecap: round;
  }
  .tracks line.halo {
    stroke: rgba(10, 8, 14, 0.75);
    stroke-width: 0.57;
  }
  .tracks g.hail {
    --track: #ffc23d;
  }
  .tracks g.rotation {
    --track: #ff4d5e;
  }
  /* Esri draws roads tan — the colour of light rain here — so grey them and
     keep them faint: there to place a storm by, never louder than it. */
  .roads {
    filter: grayscale(1) brightness(1.5);
    opacity: 0.5;
  }
  .mosaic img {
    display: block;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
  }
  /* "You are here" — the focus shift already put the location at frame centre. */
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
  /* A soft inset border in the stage colour so the full-bleed map doesn't
     read as a hard-edged foreign object dropped into the layout — ported
     from the Pi radar card's _draw_perimeter_border. */
  .frame::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    box-shadow: inset 0 0 0 2px
      color-mix(in srgb, var(--stage) 45%, transparent);
    pointer-events: none;
  }
  .chip {
    position: absolute;
    bottom: var(--space-2);
    padding: calc(0.2rem * var(--ui-scale)) calc(0.55rem * var(--ui-scale));
    border-radius: var(--radius-pill);
    background: rgba(15, 13, 19, 0.62);
    color: #e8e4ec;
    font-size: var(--type-caption);
    font-weight: var(--weight-label);
  }
  .chip.label {
    left: var(--space-2);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .chip.stamp {
    right: var(--space-2);
    font-variant-numeric: tabular-nums;
  }
  .chip.stamp.stale {
    color: var(--accent);
  }
  /* Top-left, clear of both bottom chips. */
  .attribution {
    position: absolute;
    left: var(--space-2);
    top: var(--space-2);
    font-size: max(9px, calc(var(--type-caption) * 0.66));
    color: rgba(255, 255, 255, 0.5);
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
    pointer-events: none;
    white-space: nowrap;
  }
</style>
