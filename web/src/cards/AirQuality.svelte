<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import Metric from "../components/Metric.svelte";
  import type { CardProps } from "./types";
  import Placeholder from "../components/Placeholder.svelte";
  import { pick } from "./types";

  interface AirQualityData {
    usAqi?: number | null;
    pm25?: number | null;
    pm10?: number | null;
    ozone?: number | null;
  }

  const BANDS: [number, string][] = [
    [50, "Good"],
    [100, "Moderate"],
    [150, "Unhealthy for sensitive groups"],
    [200, "Unhealthy"],
    [300, "Very unhealthy"],
    [Infinity, "Hazardous"],
  ];

  let { view, stale, hero }: CardProps = $props();
  const aq = $derived(pick<AirQualityData>(view, "airQuality"));
  const aqi = $derived(aq?.usAqi ?? null);
  const band = $derived(
    aqi == null ? "" : (BANDS.find(([max]) => aqi <= max)?.[1] ?? ""),
  );
</script>

<Card accent="generic" {stale} {hero}>
  {#if aqi != null}
    <span class="eyebrow">Air quality</span>
    <span class="aqi">{Math.round(aqi)}</span>
    <span class="band">{band}</span>
    <div class="metrics">
      {#if aq?.pm25 != null}
        <Metric label="PM2.5" value={`${aq.pm25}`} sub="µg/m³" />
      {/if}
      {#if aq?.ozone != null}
        <Metric label="Ozone" value={`${Math.round(aq.ozone)}`} sub="µg/m³" />
      {/if}
    </div>
  {:else}
    <Placeholder label="Waiting for air quality…" />
  {/if}
</Card>

<style>
  .eyebrow {
    font-size: var(--type-caption);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .aqi {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: var(--type-xl);
    line-height: 1;
  }
  .band {
    font-size: var(--type-sm);
    color: var(--on-card-soft);
  }
  .metrics {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
    margin-top: var(--space-2);
  }
</style>
