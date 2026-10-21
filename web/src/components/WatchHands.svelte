<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { CENTRE_H, tickRadius } from "../lib/round";
  import { clock } from "../lib/time.svelte";

  // Circle mode's clock: a chapter ring (numerals at the quarters, ticks
  // between) and hour and minute hands over the cards. Drawn in a fixed
  // 1600-unit box that scales with the disc. The minute hand's tip lands on
  // the ring, like a watch; the hour hand stops inside the centre card.

  interface Props {
    /** A soft dark pool under the hub, for when the centre card is a photo. */
    shade?: boolean;
  }
  let { shade = false }: Props = $props();

  const R = 800;
  const rr = tickRadius() * R;
  const HAND = "#ffffff";
  const UNDER = "rgba(14, 8, 16, 0.34)";
  const MIN_LEN = rr - 24;
  const HOUR_LEN = Math.min(R * 0.5, CENTRE_H * R + 20);

  const ticks = Array.from({ length: 12 }, (_, i) => {
    const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
    return { i, cos: Math.cos(a), sin: Math.sin(a) };
  });

  // A primitive, so the 1 s tick only turns the hands once a minute.
  const minuteOf12h = $derived(
    (clock.now.getHours() % 12) * 60 + clock.now.getMinutes(),
  );

  // Unwrapped angles, so 12:59 → 1:00 steps forward instead of spinning
  // back round. Kept outside $state: only the minute drives the effect.
  let curM = 0;
  let curH = 0;
  let placed = false;
  let angM = $state(0);
  let angH = $state(0);
  let spring = $state(false);
  $effect(() => {
    const m = minuteOf12h;
    const step = (cur: number, to: number): number =>
      cur + ((((to - cur) % 360) + 540) % 360) - 180;
    const nextM = step(curM, (m % 60) * 6);
    // Spring only for an ordinary one-minute step, never on first paint or
    // after a sleep/wake jump.
    spring = placed && Math.abs(nextM - curM) <= 6.01;
    curM = nextM;
    curH = step(curH, m / 2);
    angM = curM;
    angH = curH;
    placed = true;
  });
</script>

<svg
  class="hands"
  class:spring
  viewBox="0 0 1600 1600"
  role="img"
  aria-label="Clock"
>
  {#if shade}
    <defs>
      <radialGradient id="hub-shade">
        <stop offset="0" stop-color="rgb(14 8 16 / 0.38)" />
        <stop offset="0.6" stop-color="rgb(14 8 16 / 0.12)" />
        <stop offset="1" stop-color="rgb(14 8 16 / 0)" />
      </radialGradient>
    </defs>
    <circle cx={R} cy={R} r={R * 0.42} fill="url(#hub-shade)" />
  {/if}

  <g class="ring">
    {#each ticks as t (t.i)}
      {#if t.i % 3 === 0}
        <text
          x={R + t.cos * rr}
          y={R + t.sin * rr}
          text-anchor="middle"
          dominant-baseline="central">{t.i === 0 ? 12 : t.i}</text
        >
      {:else}
        <line
          x1={R + t.cos * (rr - 9)}
          y1={R + t.sin * (rr - 9)}
          x2={R + t.cos * (rr + 9)}
          y2={R + t.sin * (rr + 9)}
        />
      {/if}
    {/each}
  </g>

  <g class="hg" style:transform="rotate({angH}deg)">
    <line
      x1={R}
      y1={R + 46}
      x2={R}
      y2={R - HOUR_LEN}
      stroke={UNDER}
      stroke-width="34"
    />
    <line
      x1={R}
      y1={R + 46}
      x2={R}
      y2={R - HOUR_LEN}
      stroke={HAND}
      stroke-width="26"
    />
  </g>
  <g class="hg" style:transform="rotate({angM}deg)">
    <line
      x1={R}
      y1={R + 64}
      x2={R}
      y2={R - MIN_LEN}
      stroke={UNDER}
      stroke-width="26"
    />
    <line
      x1={R}
      y1={R + 64}
      x2={R}
      y2={R - MIN_LEN}
      stroke={HAND}
      stroke-width="18"
    />
  </g>
  <circle cx={R} cy={R} r="16" fill={HAND} stroke={UNDER} stroke-width="5" />
  <circle class="jewel" cx={R} cy={R} r="6.7" />
</svg>

<style>
  .hands {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    opacity: 0.9;
  }
  .hands line {
    stroke-linecap: round;
  }
  .ring text {
    fill: var(--on-stage);
    font-family: var(--font-clock);
    font-size: 34px;
    font-weight: 560;
    font-variation-settings: "opsz" 144;
  }
  .ring line {
    stroke: var(--on-stage);
    stroke-width: 5;
  }
  .jewel {
    fill: var(--accent);
  }
  /* The face's one moving part: the minute hand steps once a minute with a
     small overshoot, like a station clock. */
  .hg {
    transform-box: view-box;
    transform-origin: 50% 50%;
  }
  .spring .hg {
    transition: transform 700ms cubic-bezier(0.3, 1.8, 0.5, 1);
  }
  @media (prefers-reduced-motion: reduce) {
    .spring .hg {
      transition: none;
    }
  }
  :global(:root[data-reduce-motion="true"]) .spring .hg {
    transition: none;
  }
</style>
