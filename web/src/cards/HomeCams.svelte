<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  Our own cameras, the doorbell and the garage: the latest photo Antigua
  took of each (battery cameras, so every 30 / 10 minutes, never live here;
  "show me the front door" is the live view). One at a time, edge to edge,
  10s each — both images stay in the page, so the swap is just an opacity
  fade, cheap on the Pi. A battery under Antigua's warning level puts a red
  "charge it" note on that camera's photo. The doorbell's level ([cameras]
  always_battery) is a small battery icon in the top corner of its own
  photo only, red when it's low. No camera names: it's our house.

  It took the moon-climate mini card's cell, and with it the job of showing
  a running timer (set here or by Antigua): the one ending soonest, "+N"
  for the others, as a pill in the top corner.
-->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { alarmTime, formatCountdown, timeOfDay } from "../lib/format";
  import { remaining } from "../lib/time.svelte";
  import type { CardProps, HomeCamsData, TimerEntry } from "./types";
  import { pick } from "./types";
  import { paced } from "../lib/prefs.svelte";

  let { view, stale, hero }: CardProps = $props();

  const CAM_MS = 10_000;

  const cams = $derived(pick<HomeCamsData>(view, "homeCams")?.cams ?? []);
  // A primitive, so the dwell timer restarts only when the set of cameras
  // changes, not on every view rebuild.
  const camIds = $derived(cams.map((c) => c.id).join(","));

  let shown = $state(0);
  $effect(() => {
    const n = camIds ? camIds.split(",").length : 0;
    shown = 0;
    if (n < 2) return;
    const id = setInterval(() => {
      if (!document.hidden) shown = (shown + 1) % n;
    }, paced(CAM_MS));
    return () => clearInterval(id);
  });

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

  // "1:51 PM", as on the traffic and radar cards.
  function clock(iso: string): string {
    return timeOfDay(new Date(iso));
  }
</script>

<Card accent="moon" {stale} {hero} bleed>
  <div class="stack" class:timing={soonest}>
    {#each cams as cam, i (cam.id)}
      <div
        class="layer"
        class:show={i === shown % cams.length}
        aria-hidden={i === shown % cams.length ? undefined : "true"}
      >
        <img src={cam.src} alt="Home camera: {cam.label}" decoding="async" />
        {#if cam.lowBattery && !cam.alwaysBattery}
          <span class="battery" role="status"
            >Battery {cam.battery}% · charge it soon</span
          >
        {:else if cam.alwaysBattery && cam.battery !== null}
          <span
            class="level"
            class:low={cam.lowBattery}
            style:--pct={Math.min(Math.max(cam.battery, 0), 100)}
            role="status"
            aria-label="{cam.label} battery {cam.battery}%"
            ><span class="fill"></span><b>{cam.battery}%</b></span
          >
        {/if}
        <span class="chips">
          <span class="chip when" class:late={cam.stale}
            >{clock(cam.capturedAt)}</span
          >
        </span>
      </div>
    {:else}
      <span class="waiting">No camera snapshots yet</span>
    {/each}
    {#if soonest}
      <span class="chip timer" role="timer"
        >{soonest.label}{running.length > 1 ? ` +${running.length - 1}` : ""}
        <b>{soonest.alarm ?? formatCountdown(soonest.left.totalSeconds)}</b
        ></span
      >
    {/if}
  </div>
</Card>

<style>
  .stack {
    flex: 1;
    position: relative;
    display: grid;
    grid-template-rows: minmax(0, 1fr);
    /* A floor for content-sized rows (tablets, phones), capped so a wide
       cell doesn't grow taller than its row and hide the chips. */
    min-height: min(50cqi, 16rem);
    border-radius: inherit;
    overflow: hidden;
    background: #000;
  }
  .layer {
    grid-area: 1 / 1;
    position: relative;
    min-width: 0;
    min-height: 0;
    opacity: 0;
    /* Own compositor layer: the swap is a GPU opacity blend. */
    transform: translateZ(0);
    will-change: opacity;
    transition: opacity 600ms ease;
  }
  .layer.show {
    opacity: 1;
  }
  @media (prefers-reduced-motion: reduce) {
    .layer {
      transition: none;
    }
  }
  img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    /* Cropped to the cell, never stretched. */
    object-fit: cover;
    object-position: center;
  }
  /* A soft inset border in the stage colour, as on the traffic card. */
  .stack::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    box-shadow: inset 0 0 0 2px
      color-mix(in srgb, var(--stage) 45%, transparent);
    pointer-events: none;
  }
  .chips {
    position: absolute;
    left: var(--space-2);
    right: var(--space-2);
    bottom: var(--space-2);
    display: flex;
    justify-content: flex-end;
  }
  .chip {
    padding: calc(0.2rem * var(--ui-scale)) calc(0.55rem * var(--ui-scale));
    border-radius: var(--radius-pill);
    background: rgba(15, 13, 19, 0.62);
    color: #e8e4ec;
    font-size: var(--type-caption);
    font-weight: var(--weight-label);
    white-space: nowrap;
  }
  .when {
    flex: none;
    font-variant-numeric: tabular-nums;
  }
  .when.late {
    color: var(--accent);
  }
  .timer {
    position: absolute;
    top: var(--space-2);
    right: var(--space-2);
    max-width: calc(100% - 2 * var(--space-2));
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .timer b {
    margin-left: 0.3em;
    font-weight: var(--weight-display);
    font-variant-numeric: tabular-nums;
  }
  /* Needs charging: readable across the room, on the photo's top edge. */
  .battery {
    position: absolute;
    left: var(--space-2);
    top: var(--space-2);
    max-width: calc(100% - 2 * var(--space-2));
    padding: 0.25em 0.7em;
    border-radius: 999px;
    background: rgb(180 35 24 / 0.88);
    color: #fff;
    font-size: var(--type-caption);
    font-weight: var(--weight-label);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .timing .battery {
    top: calc(var(--space-2) * 2 + 1.6em);
  }
  /* The doorbell's level, on its own photo only: a small battery (outline,
     a fill to the level, the percent inside), top left, opposite the
     timer pill. */
  .level {
    position: absolute;
    top: var(--space-2);
    left: var(--space-2);
    display: inline-grid;
    place-items: center;
    min-width: 3em;
    height: 1.5em;
    margin-right: 0.3em;
    padding: 0 0.3em;
    border: 1.5px solid rgb(255 255 255 / 0.85);
    border-radius: 0.35em;
    background: rgba(15, 13, 19, 0.55);
    color: #fff;
    font-size: calc(var(--type-caption) * 0.85);
  }
  .level::after {
    content: "";
    position: absolute;
    top: 50%;
    right: -0.3em;
    width: 0.18em;
    height: 0.6em;
    translate: 0 -50%;
    border-radius: 0 0.1em 0.1em 0;
    background: rgb(255 255 255 / 0.85);
  }
  .fill {
    position: absolute;
    top: 2px;
    bottom: 2px;
    left: 2px;
    width: calc((100% - 4px) * var(--pct) / 100);
    border-radius: 0.2em;
    background: rgb(255 255 255 / 0.32);
  }
  .level b {
    position: relative;
    line-height: 1;
    font-weight: var(--weight-display);
    font-variant-numeric: tabular-nums;
    text-shadow: 0 1px 2px rgb(0 0 0 / 0.6);
  }
  .level.low {
    border-color: #ff7a6b;
  }
  .level.low::after {
    background: #ff7a6b;
  }
  .level.low .fill {
    background: rgb(214 48 34 / 0.9);
  }
  .waiting {
    grid-area: 1 / 1;
    margin: auto;
    color: rgb(255 255 255 / 0.6);
  }
</style>
