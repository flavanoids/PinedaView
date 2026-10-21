<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  Cross-fades through a fixed set of items on a dwell timer, with a row of
  cycle dots — the web port of the legacy app's multilingual-phrase rotation
  (pineda/ui/spanish_phrase.py). Two stacked layers dissolve into each other;
  Lite / reduced-motion swap hard instead. The grid stack sizes to the tallest
  item so the card's row height doesn't jump between items.

  It pauses while a pointer is over it or focus is inside it (so a closer look
  in the detail view doesn't flip away mid-read) and while the tab is hidden.
-->
<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    /** Number of items to rotate through. */
    count: number;
    /** Dwell time per item, milliseconds. */
    intervalMs: number;
    /** Show the cycle-dot indicator. */
    dots?: boolean;
    /** "fade" (default) or "rise" — a small upward drift that reads as a page
        turn rather than a dissolve. */
    motion?: "fade" | "rise";
    /** Grow to the parent's height so each item can spread down the card. */
    fill?: boolean;
    /** Renders item `i`. Called for both the outgoing and incoming layer. */
    item: Snippet<[number]>;
  }
  let {
    count,
    intervalMs,
    dots = true,
    motion = "fade",
    fill = false,
    item,
  }: Props = $props();

  let index = $state(0);
  // Which item each of the two layers is showing, and which layer is on top.
  let shown = $state<[number, number]>([0, 0]);
  let top = $state(0);
  let held = $state(false);

  // `count` arrives as a getter prop — the cards feed it `facts.length`, and
  // every view-model push re-evaluates that with a new array identity, which
  // a raw getter has no value check for. Routing it through a derived adds
  // one: only a real count change restarts the rotation, so the SSE feed's
  // pushes can't keep resetting it back to item 0 forever.
  const total = $derived(count);

  // Pause the dwell timer while a pointer is over the card or focus is inside
  // it — a closer look in the detail view shouldn't flip away mid-read. An
  // action rather than inline handlers so the a11y linter stays quiet on the
  // otherwise-static container.
  function hoverPause(node: HTMLElement) {
    const hold = () => (held = true);
    const release = () => (held = false);
    const events: [string, () => void][] = [
      ["pointerenter", hold],
      ["pointerleave", release],
      ["focusin", hold],
      ["focusout", release],
    ];
    for (const [name, fn] of events) node.addEventListener(name, fn);
    return {
      destroy() {
        for (const [name, fn] of events) node.removeEventListener(name, fn);
      },
    };
  }

  $effect(() => {
    // Restart cleanly whenever the source set changes (new day, new data).
    const n = total;
    index = 0;
    shown = [0, 0];
    top = 0;
    if (n < 2) return;
    const id = setInterval(() => {
      if (held || document.hidden) return;
      index = (index + 1) % n;
      const back = 1 - top;
      shown[back] = index;
      top = back;
    }, intervalMs);
    return () => clearInterval(id);
  });
</script>

<div class="cycler" class:rise={motion === "rise"} class:fill use:hoverPause>
  <div class="stack">
    {#each shown as which, i (i)}
      <div
        class="layer"
        class:show={i === top}
        aria-hidden={i === top ? undefined : "true"}
      >
        {@render item(which)}
      </div>
    {/each}
  </div>
  {#if dots && count > 1}
    <span class="dots" aria-hidden="true">
      {#each { length: count } as _, i (i)}
        <span class="dot" class:on={i === index} data-i={i}></span>
      {/each}
    </span>
  {/if}
</div>

<style>
  .cycler {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-width: 0;
  }
  .stack {
    display: grid;
    min-width: 0;
  }
  .cycler.fill,
  .cycler.fill .stack {
    flex: 1;
    min-height: 0;
  }
  /* The one row is exactly the stack's height, so an item can size itself to
     the space it has (see lib/fitText) instead of growing the row. */
  .cycler.fill .stack {
    grid-template-rows: minmax(0, 1fr);
  }
  .cycler.fill .layer {
    min-height: 0;
  }
  .layer {
    grid-area: 1 / 1;
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: var(--space-2);
    opacity: 0;
    /* 0.4s crossfade — matches the legacy card's _FADE_DURATION. */
    transition:
      opacity 400ms linear,
      transform 400ms var(--ease-spring, ease);
  }
  .layer:not(.show) {
    pointer-events: none;
  }
  .layer.show {
    opacity: 1;
  }
  /* "rise": the incoming layer settles up into place; the outgoing one sinks
     back to the +10px rest position as it fades. */
  .cycler.rise .layer {
    transform: translateY(10px);
  }
  .cycler.rise .layer.show {
    transform: none;
  }
  @media (prefers-reduced-motion: reduce) {
    .layer {
      transition: none;
    }
    .cycler.rise .layer {
      transform: none;
    }
  }
  :global(:root[data-motion="lite"]) .layer {
    transition: none;
  }
  :global(:root[data-motion="lite"]) .cycler.rise .layer {
    transform: none;
  }
  .dots {
    display: inline-flex;
    gap: 6px;
    align-items: center;
  }
  .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--on-card-faint);
  }
  .dot.on {
    background: var(--on-card-soft);
  }
</style>
