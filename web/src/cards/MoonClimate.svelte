<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  A mini-card cluster: two compact readouts sharing one grid cell instead of
  each claiming a full one. Moon and indoor climate were both a couple of
  short lines in a mostly-empty cell — fixed pairing, not yet drag-to-group
  (see the "mini cards" note in the project's edit history for the fuller
  drag-and-drop version, not built yet).

  While a timer runs (set here or mirrored from the Antigua voice assistant)
  the pair becomes a 2×2 grid and the timer takes the bottom-left quadrant:
  the one ending soonest, "+N" for the others. Bottom-right is kept free for
  a future readout. No timer, and it goes back to two halves.
-->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import MoonGlyph from "../components/MoonGlyph.svelte";
  import { alarmTime, formatTemp, type Units } from "../lib/format";
  import { remaining } from "../lib/time.svelte";
  import type {
    CardProps,
    IndoorClimateData,
    MoonData,
    TimerEntry,
  } from "./types";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();
  const moon = $derived(pick<MoonData>(view, "moon"));
  const climate = $derived(pick<IndoorClimateData>(view, "indoorClimate"));
  const units = $derived(view.units as Units);
  // Re-derived every clock tick (remaining() reads the shared clock), so a
  // timer drops out, and the grid folds back, the second it finishes.
  const running = $derived(
    (pick<TimerEntry[]>(view, "timer") ?? [])
      .map((t) => ({
        label: t.label,
        left: remaining(t.fires_at),
        alarm:
          t.kind === "alarm" || t.kind === "reminder"
            ? alarmTime(t.fires_at)
            : null,
      }))
      .filter((t) => !t.left.done)
      .sort((a, b) => a.left.totalSeconds - b.left.totalSeconds),
  );
  const soonest = $derived(running[0]);

  function countdown(total: number): string {
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = String(total % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
  }
</script>

<Card accent="moon" {stale} {hero}>
  <div class="cluster" class:quad={soonest}>
    <div class="mini">
      {#if moon}
        <span class="mini-glyph">
          <MoonGlyph
            phase={moon.phase ?? 0}
            illumination={moon.illumination ?? 0}
          />
        </span>
        <span class="mini-value">{Math.round(moon.illumination ?? 0)}%</span>
        <span class="mini-label">{moon.name ?? "Moon"}</span>
      {:else}
        <span class="mini-waiting">…</span>
      {/if}
    </div>
    <span class="divider" aria-hidden="true"></span>
    <div class="mini">
      {#if climate}
        <span class="mini-value">{formatTemp(climate.tempC, units)}</span>
        <span class="mini-label"
          >Indoor{climate.humidity != null
            ? ` · ${climate.humidity}%`
            : ""}</span
        >
      {:else}
        <span class="mini-waiting">…</span>
      {/if}
    </div>
    {#if soonest}
      <div class="mini timer" role="timer">
        <span class="mini-value"
          >{soonest.alarm ?? countdown(soonest.left.totalSeconds)}</span
        >
        <span class="mini-label"
          >{soonest.label}{running.length > 1
            ? ` +${running.length - 1}`
            : ""}</span
        >
      </div>
      <div class="mini spare" aria-hidden="true"></div>
    {/if}
  </div>
</Card>

<style>
  .cluster {
    display: flex;
    align-items: center;
    width: 100%;
  }
  /* Two halves become four quadrants; the divider line gives way to gaps. */
  .cluster.quad {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
    row-gap: var(--space-2);
  }
  .cluster.quad .divider {
    display: none;
  }
  .timer .mini-value {
    font-variant-numeric: tabular-nums;
  }
  .timer .mini-label {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mini {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 2px;
  }
  .divider {
    align-self: stretch;
    width: 1px;
    margin: 0 var(--space-3);
    background: color-mix(in srgb, var(--on-card) 18%, transparent);
  }
  .mini-glyph {
    display: block;
    width: 2.2rem;
    height: 2.2rem;
    margin-bottom: 2px;
  }
  .mini-value {
    font-size: var(--type-md);
    font-weight: var(--weight-display);
    line-height: 1.1;
  }
  .mini-label {
    font-size: var(--type-caption);
    color: var(--on-card-soft);
  }
  .mini-waiting {
    color: var(--on-card-faint);
    font-size: var(--type-sm);
  }
</style>
