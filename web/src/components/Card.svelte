<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Snippet } from "svelte";

  import type { Stale } from "../cards/types";
  import { updatedAgo } from "../lib/ago";
  import { clock } from "../lib/time.svelte";

  interface Props {
    accent?: string;
    stale?: Stale;
    hero?: boolean;
    /** Edge-to-edge content (a photo, a map) — no card padding, so nothing
        of the card's own background shows behind it. Corners still clip to
        the card's radius via the card's own overflow:hidden. */
    bleed?: boolean;
    /** Opt out of the row baseline for a card whose content is naturally
        short relative to its cell — a wide trailing row can leave a
        top-aligned card looking pinned in the corner of mostly empty
        space. Same treatment the hero already gets; ordinary grid tiles
        stay top-aligned by default. */
    centered?: boolean;
    /** Stretch the body to the card's full height, for a card that lays its
        own content out top-to-bottom across the cell. */
    fill?: boolean;
    children: Snippet;
  }

  let {
    accent = "generic",
    stale = false,
    hero = false,
    bleed = false,
    centered = false,
    fill = false,
    children,
  }: Props = $props();

  const staleText = $derived(
    typeof stale === "string"
      ? updatedAgo(stale, clock.now.getTime())
      : "Not updated lately",
  );
</script>

<article
  class="card"
  class:hero
  class:bleed
  class:centered
  class:fill
  style="--card-bg: var(--card-{accent}, var(--card-generic))"
>
  {#if stale}
    <span class="stale">
      <svg viewBox="0 0 16 16" aria-hidden="true"
        ><circle cx="8" cy="8" r="6.25" /><path d="M8 4.5V8l2.5 1.5" /></svg
      >{staleText}
    </span>
  {/if}
  <div class="body">{@render children()}</div>
</article>

<style>
  .card {
    position: relative;
    display: flex;
    min-height: 0;
    min-width: 0;
    flex-direction: column;
    /* Top-aligned so every card's first line lands on the same baseline
       across a row — the grid reads as one system rather than each tile
       floating its own content. The hero opts back into centring below. */
    justify-content: flex-start;
    gap: var(--space-2);
    /* One fixed inset, not a width-relative clamp — otherwise the 2-column
       hero gets ~2.5x the padding of a 1-column tile and the optical frame
       is different on every card. */
    padding: var(--space-4);
    border-radius: var(--radius-card);
    background: var(--card-bg);
    color: var(--on-card);
    overflow: hidden;
    transition:
      transform var(--dur-mid) var(--ease-spring),
      background var(--dur-normal) var(--ease-spring-gentle),
      color var(--dur-normal) var(--ease-spring-gentle),
      box-shadow var(--dur-normal) var(--ease-spring-gentle);
  }
  /* Phones: a tighter inset so a full-width card isn't mostly padding. */
  @media (max-width: 640px) {
    .card {
      padding: var(--space-3);
    }
  }
  .card.bleed {
    padding: 0;
    /* A full-bleed card (Photo, Radar) has one child that must fill the card
       — stretch the body instead of centring it so the media frame inside
       gets real height from flex, in the locked grid as well as scrolling. */
    justify-content: stretch;
  }
  .card.bleed .body,
  .card.fill .body {
    flex: 1;
  }
  /* The hero fills a 2x2 cell — a top-aligned two-line clock leaves it looking
     half-empty. Centre the hero's composition; the row tiles still top-align. */
  .card.hero:not(.bleed),
  .card.centered:not(.bleed) {
    justify-content: center;
  }

  .body {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-height: 0;
  }

  .stale {
    position: absolute;
    top: var(--space-2);
    right: var(--space-2);
    z-index: 1;
    display: inline-flex;
    align-items: center;
    gap: 0.3em;
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    background: color-mix(in srgb, var(--card-bg) 70%, black 30%);
    color: color-mix(in srgb, white 85%, transparent);
    font-size: var(--type-caption);
    font-weight: 500;
    white-space: nowrap;
  }
  .stale svg {
    width: 1em;
    height: 1em;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.5;
    stroke-linecap: round;
  }
</style>
