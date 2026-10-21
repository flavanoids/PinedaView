<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { fade, fly } from "svelte/transition";
  import { FONTS } from "@pinedaview/tokens";
  import PhotoClock from "../cards/PhotoClock.svelte";
  import RoundPhotoClock from "../cards/RoundPhotoClock.svelte";
  import MiniNowPlaying, {
    miniShowing,
    type MiniTrack,
  } from "./MiniNowPlaying.svelte";
  import type { PhotoClockSettings } from "../lib/clockface.svelte";
  import { formatClock } from "../lib/format";
  import { frameX } from "../lib/frame.svelte";
  import { clock } from "../lib/time.svelte";

  let {
    onWake,
    held = false,
    onLeave,
    onSettings,
    font = null,
    color = null,
    photo = false,
    tint = null,
    photoClock,
    weather = null,
    units = "imperial",
    nowPlaying = null,
    paused = false,
  }: {
    onWake: () => void;
    /** Shown now, not by the clock: a tap offers a way out instead of a
        peek, which would only bring the clock back. */
    held?: boolean;
    /** Back to the dashboard for good (lets go of the held clock). */
    onLeave?: () => void;
    onSettings?: () => void;
    /** A FONTS id; null keeps the thin serif. */
    font?: string | null;
    /** #rrggbb; null keeps the soft pink. */
    color?: string | null;
    /** Clock only with photos: the Photo Clock, full screen, instead. */
    photo?: boolean;
    /** The Photo Clock's glass tint: #rrggbb, "auto", or null for clear. */
    tint?: string | null;
    photoClock: PhotoClockSettings;
    weather?: import("../cards/types").WeatherData | null;
    units?: string | null;
    /** The AirPlay track (nowPlaying store), for the corner music card. */
    nowPlaying?: MiniTrack | null;
    /** Hold the Photo Clock's current photo (Alternate's handover). */
    paused?: boolean;
  } = $props();

  // The music card fades out on the last track it showed, not on the
  // cleared one play_end leaves behind.
  const musicOn = $derived(miniShowing(nowPlaying));
  let musicCard = $state<HTMLElement | null>(null);
  let lastTrack: MiniTrack | null = null;
  const musicTrack = $derived.by(() => {
    if (musicOn) lastTrack = nowPlaying;
    return lastTrack;
  });

  const stack = $derived(FONTS.find((f) => f.id === font)?.stack);

  // Wide faces (Unbounded, Geist Mono) would run off the sides at the thin
  // serif's size; shrink to 88% of the width a picture frame leaves showing. Re-measured when the face or
  // the digits change, once the face has loaded.
  let timeEl = $state<HTMLSpanElement>();
  let fit = $state(1);
  $effect(() => {
    void stack;
    void parts.hh;
    void parts.mm;
    const el = timeEl;
    if (!el) return;
    let live = true;
    void document.fonts.ready.then(() => {
      if (!live) return;
      const w = el.offsetWidth;
      const shown = window.innerWidth - 2 * frameX(window.innerWidth);
      fit = w ? Math.min(1, (shown * 0.88) / w) : 1;
    });
    return () => {
      live = false;
    };
  });

  // The way out of a held clock, up for a few seconds after a tap.
  let offering = $state(false);
  let offerTimer: ReturnType<typeof setTimeout> | undefined;
  function tapped(): void {
    if (!held) return onWake();
    clearTimeout(offerTimer);
    offering = !offering;
    if (offering) offerTimer = setTimeout(() => (offering = false), 8000);
  }
  $effect(() => () => clearTimeout(offerTimer));

  const parts = $derived(formatClock(clock.now));
  // The colon breathes with the seconds. Driven by a class the 1 s clock tick
  // flips (a transition, not a CSS animation) so the idle rule that pauses
  // animations after a minute untouched doesn't freeze it mid-fade.
  const lit = $derived(clock.now.getSeconds() % 2 === 0);
  // Creep a few pixels each minute so a screen left on all night never holds
  // the same pixels for five hours.
  const drift = $derived.by(() => {
    const m = clock.now.getHours() * 60 + clock.now.getMinutes();
    return `${((m * 7) % 21) - 10}px, ${((m * 5) % 17) - 8}px`;
  });
</script>

<button
  type="button"
  class="night"
  in:fade={{ duration: 420 }}
  out:fade={{ duration: 240 }}
  aria-label="{parts.time} {parts.ampm}. {held
    ? 'Tap for the dashboard and settings.'
    : 'Tap to show the dashboard.'}"
  onclick={tapped}
>
  {#if photo}
    {#if photoClock.face === "hands"}
      <RoundPhotoClock {tint} date={parts.date} settings={photoClock} />
    {:else}
      <PhotoClock
        {parts}
        {font}
        {tint}
        settings={photoClock}
        {weather}
        {units}
        avoid={musicOn ? "br" : null}
        panel={musicCard}
        {paused}
      />
    {/if}
  {:else}
    <span
      class="time"
      bind:this={timeEl}
      style:translate={drift}
      style:scale={fit}
      style:font-family={stack}
      style:color
      aria-hidden="true"
    >
      {parts.hh}<span class="colon" class:lit>:</span>{parts.mm}
    </span>
  {/if}
</button>
{#if musicOn && musicTrack}
  <MiniNowPlaying track={musicTrack} bind:el={musicCard} />
{/if}
{#if offering}
  <div
    class="way-out"
    role="group"
    aria-label="Clock only"
    transition:fly={{ y: 20, duration: 220 }}
  >
    <button type="button" class="primary" onclick={onLeave}
      >Back to dashboard</button
    >
    {#if onSettings}
      <button type="button" onclick={onSettings}
        ><span aria-hidden="true">⚙</span> Settings</button
      >
    {/if}
  </div>
{/if}

<style>
  .night {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 0;
    border: none;
    background: #000;
    cursor: none;
    z-index: 11;
  }
  .way-out {
    position: fixed;
    left: 50%;
    bottom: 2.5rem;
    translate: -50% 0;
    z-index: 12;
    display: flex;
    gap: 0.75rem;
    padding: 0.6rem;
    border-radius: 999px;
    background: rgb(0 0 0 / 0.55);
    backdrop-filter: blur(12px);
    box-shadow: 0 0.5rem 2rem rgb(0 0 0 / 0.4);
  }
  .way-out button {
    min-height: 3rem;
    padding: 0 1.4rem;
    border: none;
    border-radius: 999px;
    font: 600 1.1rem var(--font-body, sans-serif);
    color: #fff;
    background: rgb(255 255 255 / 0.14);
  }
  .way-out .primary {
    color: #000;
    background: #fff;
  }
  .time {
    font-family: "Cormorant", var(--font-clock);
    font-weight: 300;
    font-size: min(34vw, 62vh);
    line-height: 1;
    letter-spacing: -0.01em;
    font-variant-numeric: lining-nums proportional-nums;
    color: #f6cfdc;
  }
  /* Old-style colon sits low; lift it to the figures' middle. */
  .colon {
    display: inline-block;
    translate: 0 -0.08em;
    margin-inline: 0.02em;
    opacity: 0.2;
    transition: opacity 0.9s ease-in-out;
  }
  .colon.lit {
    opacity: 1;
  }
  @media (prefers-reduced-motion: reduce) {
    .way-out {
      animation: none;
    }
    .colon {
      opacity: 1;
      transition: none;
    }
  }
</style>
