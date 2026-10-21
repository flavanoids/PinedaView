<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { tick, untrack } from "svelte";
  import type { ViewModel } from "@pinedaview/protocol";

  import { pick, type WeatherData } from "../cards/types";
  import { resolvePhotoClock } from "../lib/clockface.svelte";
  import { handoff } from "../lib/handoff";
  import { motion } from "../lib/tier.svelte";
  import NightClock from "./NightClock.svelte";
  import Stage from "./Stage.svelte";

  // Alternate (the phone hub's button): the Photo Clock for a minute, then
  // the cards for 30 s, round and round, with lib/handoff's 2 s move between
  // them. Only the view on screen is mounted; the next one mounts a few
  // seconds early, out of sight, so its photo has decoded and its cards have
  // settled before anything moves. While both are mounted the Photo Clock
  // holds its photo, so the one handed to the Photo card is the one that
  // was showing (its 30 s hold would otherwise land a swipe right on the
  // 60 s handover). The small-hours night clock and Clock
  // only still win (App decides before this mounts).

  let { view, deviceId }: { view: ViewModel; deviceId: string } = $props();

  const CLOCK_MS = 60_000;
  const CARDS_MS = 30_000;
  const WARM_MS = 3_000;

  let shown = $state<"clock" | "cards">("clock");
  let clockOn = $state(true);
  let cardsOn = $state(false);
  /** Mid-handoff: both views on screen. */
  let live = $state(false);
  let moving = false;

  let clockEl = $state<HTMLElement>();
  let cardsEl = $state<HTMLElement>();
  let flightEl = $state<HTMLElement>();

  async function turn(): Promise<void> {
    if (moving) return;
    moving = true;
    const to = shown === "clock" ? "cards" : "clock";
    clockOn = cardsOn = true;
    await tick();
    // One frame for the incoming view's layout before it's measured.
    await new Promise(requestAnimationFrame);
    if (!clockEl || !cardsEl || !flightEl) {
      moving = false;
      return;
    }
    const run = handoff(
      to,
      { clock: clockEl, cards: cardsEl, flight: flightEl },
      { reduced: motion.reduced },
    );
    live = true;
    await run.done;
    shown = to;
    live = false;
    clockOn = to === "clock";
    cardsOn = to === "cards";
    await tick();
    run.settle();
    moving = false;
    hold();
  }

  // The hold on whatever's showing: warm the next view, then hand over.
  let warmTimer: ReturnType<typeof setTimeout> | undefined;
  let turnTimer: ReturnType<typeof setTimeout> | undefined;
  function hold(): void {
    clearTimeout(warmTimer);
    clearTimeout(turnTimer);
    const ms = shown === "clock" ? CLOCK_MS : CARDS_MS;
    warmTimer = setTimeout(() => {
      if (shown === "clock") cardsOn = true;
      else clockOn = true;
    }, ms - WARM_MS);
    turnTimer = setTimeout(() => void turn(), ms);
  }
  $effect(() => {
    untrack(hold);
    return () => {
      clearTimeout(warmTimer);
      clearTimeout(turnTimer);
    };
  });

  // A tap on the clock brings the cards now (after a moment to warm them).
  function wake(): void {
    if (moving || shown !== "clock") return;
    clearTimeout(warmTimer);
    clearTimeout(turnTimer);
    cardsOn = true;
    turnTimer = setTimeout(() => void turn(), 400);
  }
</script>

{#if cardsOn}
  <div
    class="cards"
    bind:this={cardsEl}
    style:visibility={shown === "cards" || live ? "visible" : "hidden"}
  >
    <Stage {view} {deviceId} />
  </div>
{/if}
{#if clockOn}
  <div
    class="clock"
    bind:this={clockEl}
    style:visibility={shown === "clock" || live ? "visible" : "hidden"}
  >
    <NightClock
      photo
      font={view.night_clock_font}
      tint={view.night_clock_tint}
      photoClock={resolvePhotoClock(view.photo_clock)}
      weather={pick<WeatherData>(view, "weather")}
      units={view.units}
      paused={cardsOn}
      onWake={wake}
    />
  </div>
{/if}
<div class="flight" bind:this={flightEl} aria-hidden="true"></div>

<style>
  /* No box of its own: the Stage lays out exactly as it does alone. */
  .cards {
    display: contents;
  }
  /* NightClock is fixed full screen; this is what slides it. */
  .clock {
    position: fixed;
    inset: 0;
    z-index: 11;
  }
  .flight {
    position: fixed;
    inset: 0;
    z-index: 13;
    pointer-events: none;
  }
  .flight :global(.handoff-fig) {
    position: absolute;
    display: block;
    text-align: center;
    white-space: pre;
    will-change: transform, opacity;
    backface-visibility: hidden;
    contain: layout paint;
  }
  /* Close to the Photo Clock's baked liquid glass, for the flight. */
  .flight :global(.handoff-fig.glass) {
    color: rgba(255, 255, 255, 0.32);
    -webkit-text-stroke: 0.009em rgba(255, 255, 255, 0.7);
    text-shadow:
      0 0.012em 0 rgba(255, 255, 255, 0.24),
      0 0.05em 0.14em rgba(0, 0, 0, 0.35);
    filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.25));
  }
  .flight :global(.handoff-fig.card) {
    transform-origin: center center;
    color: var(--ink);
  }
</style>
