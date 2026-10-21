<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import Metric from "../components/Metric.svelte";
  import { formatTemp, type Units } from "../lib/format";
  import type { CardProps, IndoorClimateData } from "./types";
  import Placeholder from "../components/Placeholder.svelte";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();
  const units = $derived(view.units as Units);
  const climate = $derived(pick<IndoorClimateData>(view, "indoorClimate"));

  const metrics = $derived(
    climate
      ? [
          { label: "Humidity", value: `${climate.humidity ?? "—"}%` },
          { label: "Setpoint", value: formatTemp(climate.setpointC, units) },
          { label: "Outside", value: formatTemp(climate.outdoorC, units) },
          ...(climate.runtimePct != null
            ? [{ label: "AC running", value: `${climate.runtimePct}%` }]
            : []),
        ]
      : [],
  );
</script>

<Card accent="generic" {stale} {hero} fill={hero}>
  {#if climate}
    {#if hero}
      <div class="hero-climate">
        <div class="hero-header">
          <span class="hero-badge">
            <svg class="badge-icon" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M8 1a3.5 3.5 0 0 0-3.5 3.5v5.08a4.5 4.5 0 1 0 7 0V4.5A3.5 3.5 0 0 0 8 1zm0 2a1.5 1.5 0 0 1 1.5 1.5v5.5a.5.5 0 0 0 .2.4 2.5 2.5 0 1 1-3.4 0 .5.5 0 0 0 .2-.4V4.5A1.5 1.5 0 0 1 8 3z"
                fill="currentColor"
              />
            </svg>
            Indoor Climate
          </span>
          {#if climate.runtimePct != null && climate.runtimePct > 0}
            <span class="status-chip active">Active {climate.runtimePct}%</span>
          {:else}
            <span class="status-chip idle">Idle</span>
          {/if}
        </div>

        <div class="hero-temp-row">
          <span class="hero-temp">{formatTemp(climate.tempC, units)}</span>
          {#if climate.setpointC != null}
            <div class="setpoint-tag">
              <span class="tag-label">Target</span>
              <span class="tag-val">{formatTemp(climate.setpointC, units)}</span
              >
            </div>
          {/if}
        </div>

        <div class="hero-grid">
          <div class="hero-metric">
            <span class="m-val">{climate.humidity ?? "—"}%</span>
            <span class="m-lbl">Humidity</span>
          </div>
          {#if climate.outdoorC != null}
            <div class="hero-metric">
              <span class="m-val">{formatTemp(climate.outdoorC, units)}</span>
              <span class="m-lbl">Outside</span>
            </div>
          {/if}
          {#if climate.runtimePct != null}
            <div class="hero-metric">
              <span class="m-val">{climate.runtimePct}%</span>
              <span class="m-lbl">HVAC Run</span>
            </div>
          {/if}
        </div>
      </div>
    {:else}
      <span class="head">
        <span class="temp">{formatTemp(climate.tempC, units)}</span>
      </span>
      <span class="label">Indoor</span>
      {#if metrics.length}
        <hr class="divider" />
        <div class="metrics">
          {#each metrics as m (m.label)}
            <Metric label={m.label} value={m.value} />
          {/each}
        </div>
      {/if}
    {/if}
  {:else}
    <Placeholder label="Waiting for indoor readings…" />
  {/if}
</Card>

<style>
  .head {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  .temp {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    letter-spacing: -0.03em;
    font-size: var(--type-xl);
    line-height: 1.15;
  }
  .label {
    font-size: var(--type-md);
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
  }
  .divider {
    align-self: stretch;
    margin: var(--space-2) 0;
    border: none;
    border-top: 1px solid color-mix(in srgb, var(--on-card) 25%, transparent);
  }
  .metrics {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  /* Hero variant styles */
  .hero-climate {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 100%;
    padding: var(--space-1) 0;
  }
  .hero-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-2);
  }
  .hero-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--type-sm);
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .badge-icon {
    width: 1.1em;
    height: 1.1em;
  }
  .status-chip {
    font-size: var(--type-caption);
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    font-weight: 500;
  }
  .status-chip.active {
    background: color-mix(in srgb, var(--accent) 25%, transparent);
    color: var(--accent);
  }
  .status-chip.idle {
    background: color-mix(in srgb, var(--on-card) 12%, transparent);
    color: var(--on-card-soft);
  }
  .hero-temp-row {
    display: flex;
    align-items: baseline;
    gap: var(--space-4);
    margin: var(--space-2) 0 var(--space-4);
  }
  .hero-temp {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    letter-spacing: -0.04em;
    font-size: clamp(3rem, 28cqi, var(--type-hero));
    line-height: 1;
    color: var(--on-card);
  }
  .setpoint-tag {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .tag-label {
    font-size: var(--type-caption);
    color: var(--on-card-soft);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .tag-val {
    font-size: var(--type-lg);
    font-weight: var(--weight-display);
    color: var(--on-card);
  }
  .hero-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
    gap: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid color-mix(in srgb, var(--on-card) 15%, transparent);
  }
  .hero-metric {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .m-val {
    font-family: var(--font-display);
    font-size: var(--type-xl);
    font-weight: var(--weight-display);
    color: var(--on-card);
  }
  .m-lbl {
    font-size: var(--type-caption);
    color: var(--on-card-soft);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
</style>
