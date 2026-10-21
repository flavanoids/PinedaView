<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The clock's compositions. One block per face; everything sizes in container
  units so the same markup fills the hero cell and shrinks into a Settings
  preview tile. Rendered by Clock.svelte (hero) and ClockFacePreview.svelte.
-->
<script lang="ts">
  import { untrack } from "svelte";
  import type { ClockFace } from "../lib/clockface.svelte";
  import { QLOCK_ROWS, qlockLit, type formatClock } from "../lib/format";
  import { effectiveTier, motion } from "../lib/tier.svelte";

  let {
    now,
    parts,
    words,
    face,
    tile = false,
  }: {
    now: Date;
    parts: ReturnType<typeof formatClock>;
    words: string;
    face: ClockFace;
    /** A 1×1 grid tile rather than the hero cell (word grid and bulge). */
    tile?: boolean;
  } = $props();

  const spoken = $derived(`${parts.time} ${parts.ampm}`);

  // Stack: the rule under the figures is a minute hand — it snaps empty as the
  // minutes swap, then one linear transform transition refills it across the
  // minute. Standard+ only: a 60 s transform keeps the compositor busy every
  // frame, and lite's steady state is fully static. The stamp is a primitive,
  // so the effect runs once a minute, not per tick.
  let ruleEl = $state<HTMLSpanElement>();
  const minuteStamp = $derived(now.getHours() * 60 + now.getMinutes());
  $effect(() => {
    void minuteStamp;
    const el = ruleEl;
    if (!el) return;
    if (motion.reduced || effectiveTier() === "lite") {
      el.style.transition = "";
      el.style.transform = ""; // natural state: the full-width rule
      return;
    }
    const seconds = untrack(() => now.getSeconds());
    el.style.transition = "none";
    el.style.transform = `scaleX(${seconds / 60})`;
    el.getBoundingClientRect(); // commit the snap before the long transition
    el.style.transition = `transform ${(60 - seconds) * 1000}ms linear`;
    el.style.transform = "scaleX(1)";
  });

  // Analog: hands move once a minute (no seconds — a wall clock should be
  // still), so the minute hand steps rather than sweeps.
  const minuteAngle = $derived(now.getMinutes() * 6);
  const hourAngle = $derived(
    (now.getHours() % 12) * 30 + now.getMinutes() * 0.5,
  );

  // Contour: numerals warp around the card's edge, brightening as the hour
  // hand nears them. hourFloat is continuous (not stepped) so that glow
  // blends smoothly from one numeral to the next instead of snapping.
  const contourNumerals = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
  const hourFloat = $derived((now.getHours() % 12) + now.getMinutes() / 60);
  const contourEmphasis = $derived(
    contourNumerals.map((n) => {
      const idx = n % 12;
      const raw = Math.abs(hourFloat - idx);
      const d = Math.min(raw, 12 - raw);
      return Math.max(0, 1 - d / 1.5);
    }),
  );
  const contourPointerAngle = $derived(hourFloat * 30);

  // Word grid: recomputed only when the minute changes, not every tick.
  const qlockMinute = $derived(now.getHours() * 60 + now.getMinutes());
  const qlock = $derived.by(() => {
    void qlockMinute;
    return qlockLit(now);
  });
</script>

{#if face === "words"}
  <div class="face words" role="img" aria-label={spoken}>
    {#key words}<p class="phrase">{words}</p>{/key}
    <span class="date">{parts.date}</span>
  </div>
{:else if face === "poster"}
  <div class="face poster" role="img" aria-label={spoken}>
    <span class="figures" aria-hidden="true">
      {#key parts.hh}<span class="hh">{parts.hh}</span>{/key}
      {#key parts.mm}<span class="mm">{parts.mm}</span>{/key}
    </span>
    <span class="date"
      ><span class="mer">{parts.ampm.toLowerCase()}</span> {parts.date}</span
    >
  </div>
{:else if face === "flip"}
  <div class="face flip" role="img" aria-label={spoken}>
    <div class="flaps" aria-hidden="true">
      {#key parts.hh}<span class="flap">{parts.hh.padStart(2, "0")}</span>{/key}
      {#key parts.mm}<span class="flap">{parts.mm}</span>{/key}
    </div>
    <span class="date"
      ><span class="mer">{parts.ampm.toLowerCase()}</span> {parts.date}</span
    >
  </div>
{:else if face === "seg"}
  <div class="face seg" role="img" aria-label={spoken}>
    <span class="lcd" aria-hidden="true">
      <span class="ghost">88:88</span>
      {#key parts.time}<span class="lit">{parts.time}</span>{/key}
      <span class="mer">{parts.ampm.toLowerCase()}</span>
    </span>
    <span class="date">{parts.date}</span>
  </div>
{:else if face === "analog"}
  <div class="face analog" role="img" aria-label={spoken}>
    <svg class="dial" viewBox="0 0 100 100" aria-hidden="true">
      <circle class="ring" cx="50" cy="50" r="46" />
      <line class="pip" x1="50" y1="6" x2="50" y2="13" />
      <line
        class="hand hour"
        x1="50"
        y1="52"
        x2="50"
        y2="27"
        style:transform={`rotate(${hourAngle}deg)`}
      />
      <line
        class="hand minute"
        x1="50"
        y1="54"
        x2="50"
        y2="15"
        style:transform={`rotate(${minuteAngle}deg)`}
      />
      <circle class="cap" cx="50" cy="50" r="2.6" />
    </svg>
    <span class="date">{parts.date}</span>
  </div>
{:else if face === "contour"}
  <div class="face contour" role="img" aria-label={spoken}>
    <svg class="dial" viewBox="0 0 100 100" aria-hidden="true">
      <path
        id="contourRing"
        class="ring-path"
        d="M 50 10 H 72 A 18 18 0 0 1 90 28 V 72 A 18 18 0 0 1 72 90 H 28 A 18 18 0 0 1 10 72 V 28 A 18 18 0 0 1 28 10 H 50 Z"
      />
      {#each contourNumerals as n, i}
        {@const emphasis = contourEmphasis[i] ?? 0}
        <text
          class="numeral"
          style:font-weight={400 + emphasis * 300}
          style:fill={`color-mix(in srgb, var(--accent) ${Math.round(emphasis * 100)}%, var(--on-card-soft))`}
        >
          <textPath
            href="#contourRing"
            startOffset={`${(i * 100) / 12}%`}
            text-anchor="middle">{n}</textPath
          >
        </text>
      {/each}
      <line
        class="pointer"
        x1="50"
        y1="50"
        x2="50"
        y2="14"
        style:transform={`rotate(${contourPointerAngle}deg)`}
      />
      <line
        class="hand hour"
        x1="50"
        y1="52"
        x2="50"
        y2="30"
        style:transform={`rotate(${hourAngle}deg)`}
      />
      <line
        class="hand minute"
        x1="50"
        y1="54"
        x2="50"
        y2="20"
        style:transform={`rotate(${minuteAngle}deg)`}
      />
      <circle class="cap" cx="50" cy="50" r="2.4" />
    </svg>
    <span class="date">{parts.date}</span>
  </div>
{:else if face === "bulge"}
  <div class="face bulge" class:tile role="img" aria-label={spoken}>
    <div class="disc">
      <svg class="dial" viewBox="0 0 100 100" aria-hidden="true">
        {#each Array(12) as _, i}
          <line
            class="tick"
            class:quarter={i % 3 === 0}
            x1="50"
            y1="9"
            x2="50"
            y2={i % 3 === 0 ? 16 : 13}
            transform={`rotate(${i * 30} 50 50)`}
          />
        {/each}
        <line
          class="hand hour"
          x1="50"
          y1="53"
          x2="50"
          y2="29"
          style:transform={`rotate(${hourAngle}deg)`}
        />
        <line
          class="hand minute"
          x1="50"
          y1="55"
          x2="50"
          y2="18"
          style:transform={`rotate(${minuteAngle}deg)`}
        />
        <circle class="cap" cx="50" cy="50" r="2.8" />
      </svg>
    </div>
    <span class="date">{parts.date}</span>
  </div>
{:else if face === "qlock"}
  <div class="face qlock" class:tile role="img" aria-label={spoken}>
    <div class="board" aria-hidden="true">
      {#each [0, 1, 2, 3] as d}
        <span class="dot" class:on={d < qlock.dots}></span>
      {/each}
      {#each QLOCK_ROWS as row, r}
        {#each row as letter, c}
          <span class="cell" class:on={qlock.lit.has(r * 11 + c)}>{letter}</span
          >
        {/each}
      {/each}
    </div>
    {#if !tile}<span class="date">{parts.date}</span>{/if}
  </div>
{:else}
  <div class="face stack" role="img" aria-label={spoken}>
    <span class="figures" aria-hidden="true">
      {#key parts.hh}<span class="hh">{parts.hh}</span>{/key}
      {#key parts.mm}<span class="mm">{parts.mm}</span>{/key}
      <span class="ap">{parts.ampm.toLowerCase()}</span>
    </span>
    <span class="rule" bind:this={ruleEl}></span>
    <span class="date">{parts.date}</span>
  </div>
{/if}

<style>
  .face {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    min-width: 0;
    container-type: inline-size;
    width: 100%;
  }
  .date {
    font-family: var(--font-body);
    font-size: clamp(0.7rem, 4cqi, var(--type-sm));
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
    text-transform: lowercase;
    letter-spacing: 0.01em;
    margin-top: 0.6em;
  }
  .date .mer {
    color: var(--on-card);
    margin-right: 0.6ch;
  }

  /* ── Stacked: hour over minutes, one carved block ──────────────────────── */
  .stack {
    align-items: center;
  }
  .stack .figures {
    display: grid;
    justify-items: center;
  }
  .stack .hh,
  .stack .mm {
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-variation-settings:
      "SOFT" 24,
      "WONK" 0;
    font-weight: 700;
    font-size: clamp(2rem, 26cqi, 15rem);
    line-height: 0.9;
    letter-spacing: -0.04em;
    font-variant-numeric: lining-nums proportional-nums;
    color: var(--on-card);
    animation: swap-in 460ms ease both;
  }
  .stack .mm {
    margin-top: 0.06em;
  }
  .stack .ap {
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-size: clamp(0.8rem, 6cqi, var(--type-md));
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: lowercase;
    color: var(--on-card-soft);
    margin-top: 0.35em;
  }
  .stack .rule {
    transform-origin: 0 50%;
    width: 2.2ch;
    height: 2px;
    background: color-mix(in srgb, var(--on-card) 24%, transparent);
    margin: 0.5em 0 0.1em;
  }
  .stack .date {
    align-self: center;
  }

  /* ── Words: the time spelled out ──────────────────────────────────────── */
  .words .phrase {
    margin: 0;
    max-width: 7ch;
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-variation-settings:
      "SOFT" 60,
      "WONK" 1;
    font-weight: 440;
    font-size: clamp(1.6rem, 20cqi, 13rem);
    line-height: 0.92;
    letter-spacing: -0.02em;
    text-transform: lowercase;
    text-wrap: balance;
    color: var(--on-card);
    animation: swap-in 460ms ease both;
  }

  /* ── Poster: massive condensed column ─────────────────────────────────── */
  .poster .figures {
    display: grid;
    justify-items: start;
  }
  .poster .hh,
  .poster .mm {
    font-family: "Anton", "Haettenschweiler", "Arial Narrow", sans-serif;
    font-weight: 400;
    font-size: clamp(2.6rem, 40cqi, 20rem);
    line-height: 0.82;
    letter-spacing: 0.005em;
    color: var(--on-card);
    animation: swap-in 420ms ease both;
  }

  /* ── Flip board: split-flap panels ───────────────────────────────────── */
  .flip .flaps {
    display: flex;
    gap: 0.12em;
    font-size: clamp(1.6rem, 27cqi, 11rem);
  }
  .flip .flap {
    position: relative;
    display: block;
    padding: 0.12em 0.16em 0.14em;
    border-radius: 0.08em;
    background: linear-gradient(
      var(--card-bg, #1c1a17) 0%,
      color-mix(in srgb, var(--on-card) 12%, var(--card-bg, #1c1a17)) 49.6%,
      var(--card-bg, #14120f) 50.4%,
      color-mix(in srgb, var(--on-card) 7%, var(--card-bg, #14120f)) 100%
    );
    box-shadow: inset 0 0 0 1px
      color-mix(in srgb, var(--on-card) 10%, transparent);
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    letter-spacing: 0.01em;
    line-height: 1;
    color: var(--on-card);
    font-variant-numeric: tabular-nums;
    transform-origin: center top;
    animation: flip-down 480ms cubic-bezier(0.3, 0.9, 0.4, 1) both;
  }
  /* The gap where the two halves of a real flap meet. */
  .flip .flap::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: 2px;
    transform: translateY(-1px);
    background: color-mix(in srgb, var(--card-bg, #000) 75%, transparent);
  }

  /* ── Seven-segment: an LCD watch, on purpose ─────────────────────────── */
  .seg .lcd {
    position: relative;
    display: inline-flex;
    align-items: baseline;
    gap: 0.28em;
    font-family: "DSEG7Classic", "Courier New", monospace;
    font-size: clamp(1.2rem, 15cqi, 7rem);
    line-height: 1;
    letter-spacing: 0.02em;
  }
  .seg .ghost {
    color: color-mix(in srgb, var(--on-card) 12%, transparent);
  }
  .seg .lit {
    position: absolute;
    left: 0;
    top: 0;
    color: var(--on-card);
    animation: swap-in 300ms linear both;
  }
  .seg .mer {
    font-family: var(--font-body);
    font-size: 0.26em;
    font-weight: var(--weight-label);
    text-transform: lowercase;
    letter-spacing: 0.08em;
    color: var(--on-card-soft);
  }

  /* ── Analog: two hands on a bare face ────────────────────────────────── */
  .analog {
    align-items: center;
  }
  .analog .dial {
    width: min(74cqi, 30rem);
    height: min(74cqi, 30rem);
    overflow: visible;
  }
  .analog .ring {
    fill: none;
    stroke: color-mix(in srgb, var(--on-card) 22%, transparent);
    stroke-width: 1.1;
  }
  .analog .pip {
    stroke: var(--accent);
    stroke-width: 3;
    stroke-linecap: round;
  }
  .analog .hand {
    stroke: var(--on-card);
    stroke-linecap: round;
    transform-box: view-box;
    transform-origin: 50px 50px;
    transition: transform 520ms cubic-bezier(0.3, 0.9, 0.35, 1);
  }
  .analog .hour {
    stroke-width: 4.2;
  }
  .analog .minute {
    stroke-width: 3;
  }
  .analog .cap {
    fill: var(--accent);
  }
  .analog .date {
    align-self: center;
  }

  /* ── Contour: numerals warped along the card's edge ──────────────────── */
  .contour {
    align-items: center;
  }
  .contour .dial {
    width: min(92cqi, 34rem);
    height: min(92cqi, 34rem);
    overflow: visible;
  }
  .contour .ring-path {
    fill: none;
    stroke: none;
  }
  .contour .numeral {
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-variation-settings:
      "SOFT" 40,
      "WONK" 0;
    font-size: 11px;
    font-variant-numeric: lining-nums proportional-nums;
    transition:
      font-weight 900ms ease,
      fill 900ms ease;
  }
  .contour .pointer {
    stroke: var(--accent);
    stroke-width: 1.4;
    stroke-linecap: round;
    transform-box: view-box;
    transform-origin: 50px 50px;
    transition: transform 520ms cubic-bezier(0.3, 0.9, 0.35, 1);
  }
  .contour .hand {
    stroke: var(--on-card);
    stroke-linecap: round;
    transform-box: view-box;
    transform-origin: 50px 50px;
    transition: transform 520ms cubic-bezier(0.3, 0.9, 0.35, 1);
  }
  .contour .hour {
    stroke-width: 3.6;
  }
  .contour .minute {
    stroke-width: 2.4;
  }
  .contour .cap {
    fill: var(--accent);
  }
  .contour .date {
    align-self: center;
  }

  /* ── Bulge: a dial pressed up out of the card ─────────────────────────
     Neumorphic: the disc is the card's own colour, so all of the shape is
     shadow — dark inset at the top and below the rim, pale inset at the
     bottom and above it, which reads as a dome lit from above. Static paint
     only; the hands are the one thing that moves. */
  .bulge {
    align-items: center;
    /* Shading is mixed from the card colour itself, not picked per theme:
       the stage's darkness says nothing about the card's (warm is a light
       stage with dark cards). */
    --bulge-hi: color-mix(in srgb, white 16%, var(--card-bg, #282622));
    --bulge-lo: color-mix(in srgb, black 38%, var(--card-bg, #282622));
  }
  .bulge .disc {
    /* Shadows scale with the disc so the dome keeps its shape from the hero
       down to a Settings preview. */
    --d: min(68cqi, 27rem);
    width: var(--d);
    aspect-ratio: 1;
    margin: calc(var(--d) * 0.07) 0 calc(var(--d) * 0.04);
    border-radius: 50%;
    background: var(--card-bg, transparent);
    box-shadow:
      0 calc(var(--d) * -0.06) calc(var(--d) * 0.06) var(--bulge-hi),
      inset 0 calc(var(--d) * -0.06) calc(var(--d) * 0.06) var(--bulge-hi),
      0 calc(var(--d) * 0.06) calc(var(--d) * 0.06) var(--bulge-lo),
      inset 0 calc(var(--d) * 0.06) calc(var(--d) * 0.06) var(--bulge-lo);
  }
  /* Tile: a dvh ceiling like the word grid's — a kiosk row can be far
     shorter than it is wide. Disc + margins + date stay inside ~30dvh. */
  .bulge.tile .disc {
    --d: min(62cqi, 21dvh);
  }
  .bulge.tile .date {
    font-size: min(var(--type-sm), 2.2dvh, 5cqi);
  }
  .bulge .dial {
    display: block;
    width: 100%;
    height: 100%;
  }
  .bulge .tick {
    stroke: color-mix(in srgb, var(--on-card) 30%, transparent);
    stroke-width: 1.4;
    stroke-linecap: round;
  }
  .bulge .tick.quarter {
    stroke: color-mix(in srgb, var(--on-card) 60%, transparent);
    stroke-width: 2.2;
  }
  .bulge .hand {
    stroke: var(--on-card);
    stroke-linecap: round;
    transform-box: view-box;
    transform-origin: 50px 50px;
    transition: transform 520ms cubic-bezier(0.3, 0.9, 0.35, 1);
  }
  .bulge .hour {
    stroke-width: 4.4;
  }
  .bulge .minute {
    stroke-width: 2.8;
  }
  .bulge .cap {
    fill: var(--accent);
  }
  .bulge .date {
    align-self: center;
  }

  /* ── Word grid: QLOCKTWO's letter board, in the clock's own Fraunces ─── */
  .qlock {
    align-items: center;
  }
  .qlock .board {
    position: relative;
    display: grid;
    grid-template-columns: repeat(11, 1fr);
    width: min(92cqi, 34rem);
    /* Room at the corners for the four minute dots. */
    padding: 1.6em;
    font-size: min(5.4cqi, 2rem);
  }
  .qlock .cell {
    display: grid;
    place-items: center;
    height: 1.55em;
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    /* Fully soft and wonky: the groovy end of Fraunces, where the curves
       swell and the terminals kick. */
    font-variation-settings:
      "SOFT" 100,
      "WONK" 1;
    font-weight: 400;
    color: color-mix(in srgb, var(--on-card) 16%, transparent);
    transition:
      color 900ms ease,
      font-weight 900ms ease;
  }
  .qlock .cell.on {
    font-weight: 800;
    color: color-mix(in srgb, var(--accent) 30%, var(--on-card));
  }
  .qlock .dot {
    position: absolute;
    width: 0.4em;
    height: 0.4em;
    border-radius: 50%;
    background: color-mix(in srgb, var(--on-card) 16%, transparent);
    transition: background 900ms ease;
  }
  .qlock .dot.on {
    background: var(--accent);
  }
  /* Clockwise from top-left, like the original. */
  .qlock .dot:nth-child(1) {
    top: 0.6em;
    left: 0.6em;
  }
  .qlock .dot:nth-child(2) {
    top: 0.6em;
    right: 0.6em;
  }
  .qlock .dot:nth-child(3) {
    bottom: 0.6em;
    right: 0.6em;
  }
  .qlock .dot:nth-child(4) {
    bottom: 0.6em;
    left: 0.6em;
  }
  .qlock .date {
    align-self: center;
    margin-top: 0;
  }
  /* Tile: no date, tighter rows, and a dvh ceiling — on the locked kiosk
     grid a 1×1 row can be far shorter than it is wide (see Clock.svelte's
     .hh/.mm), and cqi alone would crop the bottom rows. The board is ~15.2em
     tall, so 1.9dvh keeps it inside the ~31dvh the stacked tile already
     needs: wherever that tile fits, this one does. */
  .qlock.tile .board {
    width: 100%;
    padding: 1.1em;
    font-size: min(6.4cqi, 1.9dvh);
  }
  .qlock.tile .cell {
    height: 1.3em;
  }
  .qlock.tile .dot {
    width: 0.35em;
    height: 0.35em;
  }
  .qlock.tile .dot:nth-child(1),
  .qlock.tile .dot:nth-child(2) {
    top: 0.35em;
  }
  .qlock.tile .dot:nth-child(3),
  .qlock.tile .dot:nth-child(4) {
    bottom: 0.35em;
  }
  .qlock.tile .dot:nth-child(1),
  .qlock.tile .dot:nth-child(4) {
    left: 0.35em;
  }
  .qlock.tile .dot:nth-child(2),
  .qlock.tile .dot:nth-child(3) {
    right: 0.35em;
  }

  /* One motion moment: the value that just changed animates in once, then the
     face is still. Off entirely for Lite / reduced-motion. */
  @keyframes swap-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @keyframes flip-down {
    from {
      transform: perspective(400px) rotateX(-88deg);
      opacity: 0.4;
    }
    to {
      transform: perspective(400px) rotateX(0);
      opacity: 1;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .phrase,
    .hh,
    .mm,
    .flap,
    .lit {
      animation: none;
    }
    .analog .hand,
    .bulge .hand {
      transition: none;
    }
    .contour .numeral,
    .contour .pointer,
    .contour .hand,
    .qlock .cell,
    .qlock .dot {
      transition: none;
    }
  }
  :global(:root[data-motion="lite"]) .phrase,
  :global(:root[data-motion="lite"]) .hh,
  :global(:root[data-motion="lite"]) .mm,
  :global(:root[data-motion="lite"]) .flap,
  :global(:root[data-motion="lite"]) .lit {
    animation: none;
  }
  :global(:root[data-motion="lite"]) .analog .hand,
  :global(:root[data-motion="lite"]) .bulge .hand {
    transition: none;
  }
  :global(:root[data-motion="lite"]) .contour .numeral,
  :global(:root[data-motion="lite"]) .contour .pointer,
  :global(:root[data-motion="lite"]) .contour .hand,
  :global(:root[data-motion="lite"]) .qlock .cell,
  :global(:root[data-motion="lite"]) .qlock .dot {
    transition: none;
  }
</style>
