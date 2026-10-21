<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- A live miniature of the screen being edited (Settings → Cards & layout):
     the same grid the Stage draws, in the cards' own colours, so turning a
     card off or picking a new large card shows at once — tiles close the
     gap, grow into the big space and give it up, with the Stage's own
     motion (lib/cellMotion). It follows the optimistic save, so it moves
     before the server answers, and works for a screen across the house. -->
<script lang="ts">
  import { untrack } from "svelte";
  import type { Device, Profile } from "@pinedaview/protocol";

  import {
    cellMotionOn,
    leave,
    measure,
    play,
    type Rects,
  } from "../lib/cellMotion";
  import { columnCount, heroItem, TINT_SLOT, trailingSpan } from "../lib/grid";
  import { getLayout, resolveTier } from "../layouts/resolve";

  interface Props {
    screen: Device;
    profile: Profile;
    /** The screen's cards, in order, before any are turned off. */
    stack: string[];
    here: boolean;
    name: (card: string) => string;
    /** The card whose row is under the pointer or focus. */
    pointing: string | null;
  }
  let { screen, profile, stack, here, name, pointing }: Props = $props();

  // Same picks as the server (view.py _hero / _place); the music takeover
  // and cards with nothing to show today aren't modelled.
  const HERO_ELIGIBLE = ["photo", "clock", "weather"];
  // Feeds other cards, or takes the whole screen on a schedule.
  const NO_TILE = new Set(["daily-content", "video"]);

  let width = $state(typeof window === "undefined" ? 1280 : window.innerWidth);
  const tier = $derived.by(() => {
    const layout = getLayout(screen.layout ?? profile.layout);
    // Another screen's width isn't known; it's most likely the wall display.
    return here ? resolveTier(layout, width) : resolveTier(layout, Infinity);
  });

  interface Tile {
    card: string;
    col: string;
    row?: string;
    hero: boolean;
  }

  const tiles = $derived.by((): Tile[] => {
    const grid = screen.grid;
    if (grid) {
      const big = heroItem(grid.items);
      return grid.items
        .filter((i) => !NO_TILE.has(i.card))
        .map((i) => ({
          card: i.card,
          col: `${i.x + 1} / span ${i.w}`,
          row: `${i.y + 1} / span ${i.h}`,
          hero: i === big,
        }));
    }
    const off = new Set(screen.cards_off ?? []);
    const shown = stack.filter((c) => !off.has(c) && !NO_TILE.has(c));
    const pinned = screen.hero_card || profile.hero_card;
    const hero =
      pinned && shown.includes(pinned)
        ? pinned
        : (HERO_ELIGIBLE.find((c) => shown.includes(c)) ?? shown[0]);
    const body = shown.filter((c) => c !== hero);
    const cols = columnCount(tier.columns);
    const last = trailingSpan(
      cols,
      tier.heroColSpan,
      tier.heroRowSpan,
      body.length,
    );
    return [
      ...(hero
        ? [
            {
              card: hero,
              col: `span ${tier.heroColSpan}`,
              row: `span ${tier.heroRowSpan}`,
              hero: true,
            },
          ]
        : []),
      ...body.map((card, i) => ({
        card,
        col: i === body.length - 1 ? `span ${last}` : "auto",
        hero: false,
      })),
    ];
  });

  const cols = $derived(
    screen.grid ? screen.grid.cols : columnCount(tier.columns),
  );
  // A hand-placed unit is half a cell a side.
  const rowScale = $derived(screen.grid ? 0.5 : 1);
  const compact = $derived(cols === 1);

  // The tile that just arrived or just took the big space: a brief ring so
  // the eye finds what the switch did.
  let fresh = $state<string | null>(null);
  let freshTimer: ReturnType<typeof setTimeout> | undefined;
  let seen: { cards: Set<string>; hero: string | undefined } | null = null;
  $effect(() => {
    const cards = new Set(tiles.map((t) => t.card));
    const hero = tiles.find((t) => t.hero)?.card;
    untrack(() => {
      if (seen) {
        const added = [...cards].find((c) => !seen?.cards.has(c));
        const lit = added ?? (hero !== seen.hero ? hero : undefined);
        if (lit) {
          fresh = lit;
          clearTimeout(freshTimer);
          freshTimer = setTimeout(() => (fresh = null), 1100);
        }
      }
      seen = { cards, hero };
    });
    return () => clearTimeout(freshTimer);
  });

  let el = $state<HTMLElement>();
  let before: Rects | null = null;
  let entered = false;
  $effect.pre(() => {
    void tiles;
    void cols;
    before = el && entered ? measure(el) : null;
  });
  $effect(() => {
    void tiles;
    void cols;
    const root = el;
    if (!root) return;
    const first = !entered;
    entered = true;
    untrack(() => {
      if (cellMotionOn())
        play(root, before, { first, quick: false, morph: true });
    });
  });

  // Settings keeps every section rendered, closed ones hidden, so the
  // mount-time stagger would play unseen: run it each time the section
  // opens and the miniature gets a size.
  $effect(() => {
    const root = el;
    if (!root || typeof ResizeObserver === "undefined") return;
    let shown = false;
    const observer = new ResizeObserver(([entry]) => {
      const now = (entry?.contentRect.width ?? 0) > 0;
      if (now && !shown && cellMotionOn())
        play(root, null, { first: true, quick: false });
      shown = now;
    });
    observer.observe(root);
    return () => observer.disconnect();
  });

  const described = $derived(
    tiles.length
      ? `${name(tiles.find((t) => t.hero)?.card ?? tiles[0]?.card ?? "")} large, then ${tiles
          .filter((t) => !t.hero)
          .map((t) => name(t.card))
          .join(", ")}`
      : "No cards showing",
  );
</script>

<svelte:window bind:innerWidth={width} />

<figure class="model" class:compact>
  <div
    class="screen"
    bind:this={el}
    role="img"
    aria-label="How {here ? 'this screen' : screen.name} looks: {described}"
    style:--cols={cols}
    style:--row-scale={rowScale}
  >
    {#each tiles as tile (tile.card)}
      <span
        class="tile"
        class:hero={tile.hero}
        class:fresh={fresh === tile.card}
        class:pointing={pointing === tile.card}
        data-cell={tile.card}
        style:grid-column={tile.col}
        style:grid-row={tile.row}
        style:background="var(--card-{TINT_SLOT[tile.card] ?? 'generic'})"
        out:leave
      >
        <span class="name">{name(tile.card)}</span>
      </span>
    {:else}
      <span class="empty">Turn a card on to fill the screen.</span>
    {/each}
  </div>
</figure>

<style>
  /* Pinned to the top of the section while its switches scroll under it,
     so the screen stays in view whichever row is being changed. */
  .model {
    container-type: inline-size;
    position: sticky;
    top: 0;
    z-index: 1;
    margin: 0 0 var(--space-3);
    padding: var(--space-1) 0 var(--space-2);
    /* The section's fill, made opaque, so rows scroll under it unseen. */
    background: color-mix(in srgb, var(--on-stage) 5%, var(--stage));
  }
  .screen {
    position: relative;
    display: grid;
    grid-template-columns: repeat(var(--cols), minmax(0, 1fr));
    /* A cell a little wider than tall, as on the wall. */
    grid-auto-rows: calc(
      (100cqi - (var(--cols) - 1) * 3px) / var(--cols) * 0.42 * var(--row-scale)
    );
    gap: 3px;
    padding: 5px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--on-stage) 7%, black);
    box-shadow: inset 0 0 0 1px
      color-mix(in srgb, var(--on-stage) 12%, transparent);
  }
  /* A phone stacks one card per row: draw it phone-shaped, not a tall bar. */
  .compact .screen {
    width: min(9.5rem, 46%);
    margin-inline: auto;
    grid-auto-rows: 1.05rem;
    border-radius: 14px;
    padding: 6px 5px;
  }
  .tile {
    position: relative;
    display: flex;
    align-items: flex-end;
    min-width: 0;
    padding: 3px 5px;
    border-radius: 4px;
  }
  .hero {
    padding: 6px 8px;
  }
  /* Card colours run light and dark within one theme, so the name sits on a
     scrap of the sheet's own colour rather than guessing an ink per card. */
  .name {
    max-width: 100%;
    padding: 1px 5px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--stage) 78%, transparent);
    color: var(--on-stage);
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: 0.62rem;
    line-height: 1.25;
    font-weight: 500;
  }
  .hero .name {
    font-size: 0.8rem;
    font-weight: 600;
  }
  .compact .tile {
    align-items: center;
    padding: 0 5px;
    border-radius: 3px;
  }
  .compact .name,
  .compact .hero .name {
    padding: 0 4px;
    font-size: 0.55rem;
  }
  /* Rings are a pseudo-element faded on opacity, so they stay off the main
     thread while the tiles move. */
  .tile::after {
    content: "";
    position: absolute;
    inset: -2px;
    border-radius: 6px;
    box-shadow: 0 0 0 2px var(--accent);
    opacity: 0;
    pointer-events: none;
  }
  .pointing::after {
    opacity: 0.55;
  }
  .fresh::after {
    animation: lit 1.1s ease-out;
  }
  @keyframes lit {
    0%,
    35% {
      opacity: 1;
    }
    100% {
      opacity: 0;
    }
  }
  .empty {
    grid-column: 1 / -1;
    padding: var(--space-3) var(--space-2);
    text-align: center;
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
  }
  @media (prefers-reduced-motion: no-preference) {
    .tile::after {
      transition: opacity var(--dur-fast) linear;
    }
  }
</style>
