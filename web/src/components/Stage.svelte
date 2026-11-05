<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { createClient, type ViewModel } from "@pinedaview/protocol";
  import { tick, untrack } from "svelte";

  import { cardComponent } from "../cards";
  import { cardStale } from "../cards/types";
  import {
    cancelEdit,
    edit,
    enterEdit,
    fullStack,
    moveCard,
  } from "../lib/edit.svelte";
  import {
    animateHeroContract,
    animateHeroExpand,
    cellMotionOn,
    leave,
    measure,
    play,
    type Rects,
  } from "../lib/cellMotion";
  import { gesture } from "../lib/gestures";
  import {
    columnCount,
    heroItem,
    rowCount,
    trailingSpan,
    type GridItem,
  } from "../lib/grid";
  import { fillsPanel, getLayout, resolveTier } from "../layouts/resolve";
  import { platform } from "../lib/platform.svelte";
  import { prefs } from "../lib/prefs.svelte";
  import { shuffle } from "../lib/shuffle.svelte";
  import { videoHero } from "../lib/videoHero.svelte";
  import Detail from "./Detail.svelte";
  import EditBar from "./EditBar.svelte";
  import Hero from "./Hero.svelte";

  interface Props {
    view: ViewModel;
    deviceId: string;
  }
  let { view, deviceId }: Props = $props();

  const client = createClient(import.meta.env.VITE_API_URL ?? "");
  const layout = $derived(getLayout(view.layout));

  let width = $state(typeof window === "undefined" ? 1024 : window.innerWidth);
  let height = $state(typeof window === "undefined" ? 0 : window.innerHeight);
  let stageEl = $state<HTMLElement | undefined>();
  $effect(() => {
    const el = stageEl;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      width = entries[0]?.contentRect.width ?? width;
      height = entries[0]?.contentRect.height ?? height;
    });
    observer.observe(el);
    return () => observer.disconnect();
  });
  const tier = $derived(resolveTier(layout, width, height));

  // A hand-placed layout from the layout builder: every card sits in its own
  // box, nothing reflows, and the biggest box hosts the hero.
  const grid = $derived(view.grid ?? null);
  const gridRows = $derived(grid ? rowCount(grid.items) : 0);
  const gridHero = $derived(grid ? heroItem(grid.items) : undefined);
  function boxStyle(item: GridItem | undefined): {
    col?: string;
    row?: string;
  } {
    return item
      ? {
          col: `${item.x + 1} / span ${item.w}`,
          row: `${item.y + 1} / span ${item.h}`,
        }
      : {};
  }

  // The "video" card doesn't sit in the grid like the others — on its
  // schedule it takes over the whole hero-sized cell the other cards would
  // otherwise fill, then disappears entirely so they come back. See
  // videoHero.svelte.ts for the on/off timer.
  const hasVideoCard = $derived(view.cards.some((c) => c.id === "video"));
  $effect(() => {
    if (hasVideoCard) videoHero.start();
    else videoHero.stop();
  });
  const videoActive = $derived(
    hasVideoCard && videoHero.active && !edit.active && !grid,
  );

  let detailCard = $state<string | null>(null);
  let dragIndex = $state<number | null>(null);

  function startEdit(): void {
    // A hand-placed layout is edited in the layout builder, not here.
    if (view.locked || grid) return;
    const hero = view.hero.kind === "card" ? (view.hero.card ?? null) : null;
    enterEdit(
      hero,
      view.cards.map((c) => c.id),
    );
  }

  function onCardPointerDown(event: PointerEvent, index: number): void {
    if (!edit.active) return;
    dragIndex = index;
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  }
  function onCardPointerEnter(index: number): void {
    if (edit.active && dragIndex !== null && dragIndex !== index) {
      moveCard(dragIndex, index);
      dragIndex = index;
    }
  }
  function onCardPointerUp(): void {
    dragIndex = null;
  }

  let announce = $state("");

  function humanize(id: string): string {
    return id.replace(/-/g, " ");
  }

  function onCardKeydown(
    event: KeyboardEvent,
    card: { id: string },
    index: number,
  ): void {
    const meta = view.cards.find((c) => c.id === card.id);
    if (!edit.active) {
      if ((event.key === "Enter" || event.key === " ") && meta?.detail) {
        event.preventDefault();
        detailCard = card.id;
      }
      return;
    }
    const to =
      event.key === "ArrowUp" || event.key === "ArrowLeft"
        ? index - 1
        : event.key === "ArrowDown" || event.key === "ArrowRight"
          ? index + 1
          : null;
    if (to === null || to < 0 || to >= edit.stack.length) return;
    event.preventDefault();
    moveCard(index, to);
    announce = `${humanize(card.id)} moved to position ${to + 1} of ${edit.stack.length}`;
    void tick().then(() => {
      const cells =
        stageEl?.querySelectorAll<HTMLElement>(".cell:not(.hero)") ?? [];
      cells[to]?.focus();
    });
  }

  async function persist(target: "device" | "profile"): Promise<void> {
    const stack = fullStack();
    if (target === "device") {
      await client.updateDevice(deviceId, { card_stack: stack });
    } else {
      await client.updateProfile(view.profile_id, { card_stack: stack });
    }
    cancelEdit();
  }

  const rows = $derived(
    edit.active
      ? edit.stack.map((id) => ({ id, stale: false }))
      : videoActive
        ? view.cards.filter((c) => c.id === "video")
        : view.cards.filter((c) => c.id !== "video"),
  );

  const trailing = $derived(
    edit.active || grid
      ? 1
      : trailingSpan(
          columnCount(tier.columns),
          tier.heroColSpan,
          tier.heroRowSpan,
          rows.length,
        ),
  );

  // Cell motion (lib/cellMotion.ts): note where every cell sits before the
  // DOM updates, then glide each one from there once it has. The deps are
  // everything that can move a cell; reading them is the subscription.
  let before: Rects | null = null;
  let entered = false;
  function layoutDeps(): unknown[] {
    return [rows, tier, grid, trailing, view.hero];
  }
  $effect.pre(() => {
    layoutDeps();
    before = stageEl && entered ? measure(stageEl) : null;
  });
  $effect(() => {
    layoutDeps();
    const el = stageEl;
    if (!el) return;
    const first = !entered;
    entered = true;
    untrack(() => {
      if (!cellMotionOn()) return;
      play(el, before, {
        first,
        quick: edit.active,
        skip: dragIndex === null ? null : edit.stack[dragIndex],
      });
    });
  });

  // Start / update Dynamic Shuffle when active and not editing or hand-placed grid
  $effect(() => {
    if (prefs.dynamic_shuffle && !edit.active && !grid && !videoActive) {
      shuffle.start(rows.map((r) => r.id));
    } else {
      shuffle.stop();
    }
  });

  let dynamicHeroEl = $state<HTMLElement | undefined>();
  let lastAnimatedCard = "";

  $effect(() => {
    const cardId = shuffle.expandedCard;
    const phase = shuffle.phase;
    const heroEl = dynamicHeroEl;
    if (!stageEl || !cardId || !heroEl) return;

    const sourceEl = stageEl.querySelector<HTMLElement>(
      `[data-cell="${cardId}"]`,
    );
    if (!sourceEl) return;

    if (phase === "expanding" && lastAnimatedCard !== cardId) {
      lastAnimatedCard = cardId;
      animateHeroExpand(heroEl, sourceEl);
    } else if (phase === "contracting" && lastAnimatedCard === cardId) {
      lastAnimatedCard = "";
      animateHeroContract(heroEl, sourceEl);
    }
  });
</script>

<section
  class="stage"
  bind:this={stageEl}
  data-tier={tier.id}
  class:fills={fillsPanel(tier)}
  class:editing={edit.active}
  class:locked={view.locked}
  class:placed={!!grid}
  style:--cols={grid ? `repeat(${grid.cols}, minmax(0, 1fr))` : tier.columns}
  style:--rows={grid ? gridRows : undefined}
  style:--gap={layout.gap}
  style:--cell-min={tier.cellMinHeight}
>
  {#if !view.locked && !edit.active && !grid}
    <button type="button" class="edit-entry" onclick={startEdit}
      >Rearrange cards</button
    >
  {/if}

  <div
    class="cell hero"
    data-cell="__hero"
    style:grid-column={grid
      ? boxStyle(gridHero).col
      : `span ${tier.heroColSpan}`}
    style:grid-row={grid ? boxStyle(gridHero).row : `span ${tier.heroRowSpan}`}
  >
    <div class="hero-inner" class:faded={!!shuffle.expandedCard}>
      <Hero {view} />
    </div>
    {#if shuffle.expandedCard}
      {@const ShuffledCardView = cardComponent(shuffle.expandedCard)}
      {@const sMeta = view.cards.find((c) => c.id === shuffle.expandedCard)}
      <div class="hero-inner dynamic" bind:this={dynamicHeroEl}>
        <ShuffledCardView
          {view}
          stale={sMeta?.stale ? cardStale(view, shuffle.expandedCard) : false}
          hero={true}
          id={shuffle.expandedCard}
        />
      </div>
    {/if}
  </div>

  {#each rows as card, index (card.id)}
    {@const CardView = cardComponent(card.id)}
    {@const meta = view.cards.find((c) => c.id === card.id)}
    {@const interactive = edit.active || !!meta?.detail}
    {@const piPhotoHalf =
      platform.isPi && card.id === "photo" && !edit.active && !grid}
    {@const box = grid
      ? boxStyle(grid.items.find((i) => i.card === card.id))
      : null}
    {@const forceHero = piPhotoHalf || (card.id === "video" && videoActive)}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <!-- `role` and `tabindex` are set together only when the card is actionable
         (has a detail view, or edit mode); the checker can't see the pairing. -->
    <div
      class="cell"
      class:dragging={dragIndex === index}
      class:shuffled-out={shuffle.expandedCard === card.id}
      data-cell={card.id}
      style:grid-column={box
        ? box.col
        : forceHero
          ? `span ${tier.heroColSpan}`
          : index === rows.length - 1
            ? `span ${trailing}`
            : undefined}
      style:grid-row={box
        ? box.row
        : forceHero
          ? `span ${tier.heroRowSpan}`
          : undefined}
      role={interactive ? "button" : undefined}
      tabindex={interactive ? 0 : undefined}
      aria-label={edit.active
        ? `${humanize(card.id)}, card ${index + 1} of ${edit.stack.length}. Use arrow keys to move.`
        : meta?.detail
          ? `${humanize(card.id)}, open details`
          : undefined}
      aria-roledescription={edit.active ? "sortable card" : undefined}
      out:leave
      use:gesture={{
        onTap: () => {
          if (!edit.active && meta?.detail) detailCard = card.id;
        },
        onLongPress: startEdit,
      }}
      onkeydown={(e) => onCardKeydown(e, card, index)}
      onpointerdown={(e) => onCardPointerDown(e, index)}
      onpointerenter={() => onCardPointerEnter(index)}
      onpointerup={onCardPointerUp}
    >
      {#if !meta?.hidden || edit.active}
        <CardView
          {view}
          stale={meta?.stale ? cardStale(view, card.id) : false}
          hero={false}
          id={card.id}
        />
      {/if}
    </div>
  {/each}
</section>

<div class="visually-hidden" role="status" aria-live="polite">{announce}</div>

{#if edit.active}
  <EditBar
    onSaveDevice={() => persist("device")}
    onSaveProfile={() => persist("profile")}
    onCancel={cancelEdit}
  />
{/if}

{#if detailCard}
  <Detail {view} cardId={detailCard} onClose={() => (detailCard = null)} />
{/if}

<svelte:window
  on:keydown={(e) => {
    if (e.key === "Escape" && edit.active) cancelEdit();
  }}
/>

<style>
  .stage {
    position: relative;
    display: grid;
    grid-template-columns: var(--cols);
    /* `max-content` rows + a per-cell min-height floor. `minmax(min, auto)` and
       plain `auto` both collapse the row to the minimum when a flex-item card
       is the track's only content and the grid overflows its scroll container,
       which clipped every tall card. `max-content` sizes each row to its card. */
    grid-auto-rows: max-content;
    gap: var(--gap);
    /* Sparse (the default), not dense: dense backfills any gap by pulling a
       later card ahead of ones still waiting behind it, which desyncs the
       visual order from the configured card_stack. The Pi's forced-2x2 photo
       card (piPhotoHalf, below) is exactly the shape that opens such a gap —
       dense used to "fix" it by reshuffling every card after photo on the
       kiosk. Sparse instead leaves that slot empty, which only costs a blank
       cell — the order stays intact everywhere, Pi included. */
    /* Pad past the notch / Dynamic Island / home indicator when the client runs
       as a standalone home-screen app (viewport-fit=cover puts us edge to edge).
       A picture frame's lip (--frame-x) comes on top at the sides: the cards
       keep their size and reflow into what the frame leaves showing. */
    padding: calc(
        max(var(--gap), env(safe-area-inset-top)) + var(--frame-y, 0px)
      )
      calc(max(var(--gap), env(safe-area-inset-right)) + var(--frame-x, 0px))
      calc(max(var(--gap), env(safe-area-inset-bottom)) + var(--frame-y, 0px))
      calc(max(var(--gap), env(safe-area-inset-left)) + var(--frame-x, 0px));
    height: 100%;
    align-content: start;
    overflow-y: auto;
    touch-action: pan-y;
  }
  .stage.editing {
    touch-action: none;
  }
  /* Locked = no rearranging, and usually a fixed display. Fill the viewport
     rather than leaving dead space under a short stack. */
  .stage.locked {
    align-content: stretch;
  }
  /* A large fixed panel (wide tier — a wall display, a kiosk) has no scroll
     input, so the grid must fit the viewport exactly: equal `1fr` rows that
     always sum to the available height, never a scrollbar. A card taller than
     its row crops at its own edge. Phones and tablets (compact / mid tiers)
     keep a min-content floor and the base `overflow-y: auto`, so a long stack
     still scrolls even when the screen is locked. */
  .stage.locked.fills {
    grid-auto-rows: 1fr;
    overflow: hidden;
  }
  .stage.locked:not(.fills) {
    grid-auto-rows: minmax(min-content, 1fr);
  }
  /* Hand-placed: a builder unit is half an automatic cell a side, so its row
     floor is half the cell floor. A fixed wall display splits its height
     into exactly the layout's rows instead. */
  .stage.placed {
    grid-auto-rows: minmax(calc(var(--cell-min) / 2), auto);
  }
  .stage.placed.locked.fills {
    grid-template-rows: repeat(var(--rows), minmax(0, 1fr));
  }
  .stage.placed .cell {
    min-height: 0;
  }
  /* Only the fit-to-viewport case zeroes the cell / media-frame floors — the
     `1fr` row is what sets the height there. Elsewhere the floors stand. */
  .stage.locked.fills .cell,
  .stage.locked.fills .cell :global(.frame) {
    min-height: 0;
  }
  /* A keyboard-only way into the layout editor (touch uses long-press). Hidden
     until focused, like a skip link. */
  .edit-entry {
    position: absolute;
    left: 50%;
    top: var(--space-2);
    transform: translate(-50%, -150%);
    z-index: 14;
    font: inherit;
    font-size: var(--type-sm);
    padding: 8px 16px;
    border: none;
    border-radius: var(--radius-pill);
    background: var(--accent);
    color: var(--stage);
    cursor: pointer;
  }
  .edit-entry:focus-visible {
    transform: translate(-50%, 0);
  }
  .cell {
    display: flex;
    min-width: 0;
    min-height: var(--cell-min);
    /* Card text sizes to the cell width (see tokens.css @supports block). */
    container-type: inline-size;
    position: relative;
  }
  .cell > :global(*) {
    flex: 1;
  }
  .cell.hero {
    position: relative;
  }
  .hero-inner {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    min-height: 0;
    transition: opacity var(--dur-mid) var(--ease-spring-gentle);
  }
  .hero-inner > :global(*) {
    flex: 1;
  }
  .hero-inner.faded {
    opacity: 0;
    pointer-events: none;
  }
  .hero-inner.dynamic {
    position: absolute;
    inset: 0;
    z-index: 5;
  }
  .cell.shuffled-out {
    opacity: 0.18;
    filter: grayscale(0.5);
    transition:
      opacity 300ms ease,
      filter 300ms ease;
    pointer-events: none;
  }
  .stage.editing .cell {
    cursor: grab;
    transition:
      transform var(--dur-fast) var(--ease-spring),
      box-shadow var(--dur-fast) var(--ease-spring);
  }
  .cell.dragging {
    z-index: 2;
    transform: scale(1.04);
    box-shadow: 0 16px 40px -8px rgba(0, 0, 0, 0.5);
  }

  /* A card that opens: it gives a little under the finger, and a keyboard
     ring shows where focus is (never for a tap). */
  .stage:not(.editing) .cell[role="button"] {
    cursor: pointer;
    border-radius: var(--radius-card, 20px);
    transition: transform var(--dur-fast) var(--ease-spring);
  }
  .stage:not(.editing) .cell[role="button"]:active {
    transform: scale(0.98);
  }
  .cell[role="button"]:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }

  @media (prefers-reduced-motion: reduce) {
    .stage.editing .cell,
    .stage:not(.editing) .cell[role="button"] {
      transition: none;
    }
    .stage:not(.editing) .cell[role="button"]:active {
      transform: none;
    }
  }
  :global(:root[data-lock-hint]) .stage {
    outline: 2px solid var(--accent);
  }
</style>
