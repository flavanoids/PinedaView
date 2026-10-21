<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { currentFace } from "../lib/clockface.svelte";
  import { formatClock, formatWords } from "../lib/format";
  import { clock } from "../lib/time.svelte";
  import ClockFaces from "./ClockFaces.svelte";
  import type { CardProps } from "./types";

  let { hero }: CardProps = $props();

  const parts = $derived(formatClock(clock.now));
  const words = $derived(formatWords(clock.now));
  const face = $derived(currentFace());
  const tileFace = $derived(face === "qlock" || face === "bulge");
</script>

<Card accent="clock" {hero} fill={!hero && !tileFace}>
  {#if hero}
    <ClockFaces now={clock.now} {parts} {words} {face} />
  {:else if tileFace}
    <!-- The word grid and the bulge dial read at tile size too; the other
         faces need the hero's room, so a tile falls back to the stack below. -->
    <ClockFaces now={clock.now} {parts} {words} {face} tile />
  {:else}
    <!-- A grid tile, or a phone: the hero's "stack" face shrunk to fit — hour
         over minutes in Fraunces, no colon, a quiet date line. -->
    <div class="mini" role="img" aria-label="{parts.time} {parts.ampm}">
      <span class="figs">
        <span class="hh">{parts.hh}</span>
        <span class="mm">{parts.mm}</span>
      </span>
      <span class="date"
        ><span class="mer">{parts.ampm.toLowerCase()}</span> {parts.date}</span
      >
    </div>
  {/if}
</Card>

<style>
  /* The tile sizes itself from its own box (a size container filling the
     card), so the figures and date always fit and sit dead centre, whatever
     shape the row gives it. */
  .mini {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 0;
    width: 100%;
    container-type: size;
    /* Phones size rows to content, and a size container has none, so give
       it a floor from the cell's width. */
    min-height: 46cqi;
  }
  .figs {
    display: grid;
    justify-items: center;
  }
  .hh,
  .mm {
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-variation-settings:
      "SOFT" 28,
      "WONK" 0;
    font-weight: 700;
    /* Two lines of figures plus the date take about three quarters of the
       box's height, leaving an even margin above and below. */
    font-size: min(33cqh, 44cqi, 17rem);
    line-height: 0.86;
    letter-spacing: -0.04em;
    font-variant-numeric: lining-nums proportional-nums;
    color: var(--on-card);
  }
  .mm {
    margin-top: 0.02em;
  }
  .date {
    font-family: var(--font-body);
    font-size: min(var(--type-sm), 6.5cqh, 6cqi);
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
    text-transform: lowercase;
    letter-spacing: 0.01em;
    margin-top: 0.7em;
  }
  .date .mer {
    color: var(--on-card);
    margin-right: 0.5ch;
  }
</style>
