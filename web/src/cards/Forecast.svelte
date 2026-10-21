<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { glyphFor } from "../components/WeatherGlyph.svelte";
  import { formatDayName, formatTemp, type Units } from "../lib/format";
  import type { CardProps } from "./types";
  import Placeholder from "../components/Placeholder.svelte";
  import { pick } from "./types";

  interface Day {
    index: number;
    date: string;
    highC?: number | null;
    lowC?: number | null;
    code?: string;
    desc?: string;
    precip?: number;
  }
  interface WeatherWithForecast {
    forecast?: Day[];
  }

  let { view, stale, hero }: CardProps = $props();
  const units = $derived(view.units as Units);
  const allForecast = $derived(
    pick<WeatherWithForecast>(view, "weather")?.forecast ?? [],
  );
  const days = $derived(
    hero ? allForecast.slice(0, 7) : allForecast.slice(0, 3),
  );
</script>

<Card accent="forecast" {stale} {hero} fill={hero}>
  {#if days.length}
    {#if hero}
      <div class="hero-forecast">
        <div class="hero-top">
          <span class="eyebrow">7-Day Extended Forecast</span>
        </div>
        <div class="hero-days-grid">
          {#each days as day (day.date)}
            <div class="hero-day-col">
              <span class="hero-day-name"
                >{formatDayName(day.date, day.index)}</span
              >
              <span class="hero-glyph" aria-hidden="true"
                >{glyphFor(day.code)}</span
              >
              <span class="hero-high">{formatTemp(day.highC, units)}</span>
              <span class="hero-low">{formatTemp(day.lowC, units)}</span>
              {#if day.precip && day.precip > 0}
                <span class="hero-precip">{day.precip}%</span>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <span class="eyebrow">Next 3 days</span>
      <ul class="days">
        {#each days as day (day.date)}
          <li>
            <span class="day">{formatDayName(day.date, day.index)}</span>
            <span class="glyph" aria-hidden="true">{glyphFor(day.code)}</span>
            <span class="temps">
              <b>{formatTemp(day.highC, units)}</b>
              <span class="lo">{formatTemp(day.lowC, units)}</span>
            </span>
          </li>
        {/each}
      </ul>
    {/if}
  {:else}
    <Placeholder label="Waiting for the forecast…" shape="list" />
  {/if}
</Card>

<style>
  .eyebrow {
    font-size: var(--type-caption);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .days {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .days li {
    display: grid;
    grid-template-columns: 1fr auto auto;
    align-items: center;
    gap: var(--space-3);
  }
  .day {
    font-size: var(--type-sm);
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
  }
  .glyph {
    font-size: var(--type-md);
    line-height: 1;
  }
  .temps {
    font-size: var(--type-sm);
    display: flex;
    gap: var(--space-2);
    font-variant-numeric: tabular-nums;
  }
  .temps b {
    font-weight: var(--weight-display);
  }
  .lo {
    color: var(--on-card-faint);
  }

  /* Hero variant */
  .hero-forecast {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 100%;
    padding: var(--space-1) 0;
  }
  .hero-top {
    margin-bottom: var(--space-3);
  }
  .hero-days-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: var(--space-2);
    align-items: stretch;
    flex: 1;
  }
  .hero-day-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-1);
    background: color-mix(in srgb, var(--on-card) 6%, transparent);
    border-radius: var(--radius-sm, 10px);
  }
  .hero-day-name {
    font-size: var(--type-caption);
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .hero-glyph {
    font-size: clamp(1.5rem, 4cqi, 2.5rem);
    line-height: 1;
    margin: var(--space-1) 0;
  }
  .hero-high {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: var(--type-md);
    color: var(--on-card);
  }
  .hero-low {
    font-size: var(--type-sm);
    color: var(--on-card-faint);
  }
  .hero-precip {
    font-size: var(--type-caption);
    color: var(--accent);
    font-weight: 500;
  }
</style>
