<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { ViewModel } from "@pinedaview/protocol";

  import { cardComponent } from "../cards";
  import { cardStale } from "../cards/types";
  import { bands, cardAspect, RIM } from "../lib/round";
  import Hero from "./Hero.svelte";
  import WatchHands from "./WatchHands.svelte";

  // Circle mode (Settings → Appearance → Shape): a disc the height of the
  // screen on black, up to four cards in rows that run out to its rim, and
  // the hands over them as the clock. Slots are fixed — `view.circle` is the
  // order (centre, top, bottom L→R) and a card that isn't ready leaves its
  // slot empty rather than moving the others. The rectangle layout (Stage)
  // is untouched; App picks one or the other.

  let { view }: { view: ViewModel } = $props();

  let stageEl = $state<HTMLElement | undefined>();
  let diameter = $state(
    typeof window === "undefined"
      ? 800
      : Math.min(window.innerWidth, window.innerHeight),
  );
  $effect(() => {
    const el = stageEl;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (box) diameter = Math.min(box.width, box.height);
    });
    observer.observe(el);
    return () => observer.disconnect();
  });

  const slots = $derived(view.circle ?? []);
  /** The chapter ring's width: the cards stop at its inner edge. */
  const ring = $derived((RIM * diameter) / 2);
  const layout = $derived(
    bands(slots.length, diameter, (slot) => cardAspect(slots[slot])),
  );

  // Media cards fill their whole band; the rest keep their words inside the
  // band's text box (lib/round contentBox) so nothing runs into the rim.
  const FULL_BLEED = new Set([
    "photo",
    "on-this-day",
    "radar",
    "home-cams",
    "traffic",
    "video",
  ]);
</script>

<section class="round" bind:this={stageEl} aria-label="Dashboard">
  <div class="disc" style:width="{diameter}px" style:height="{diameter}px">
    <div class="face" style:inset="{ring}px">
      {#each layout as band (slots[band.slot])}
        {@const id = slots[band.slot]!}
        {@const meta = view.cards.find((c) => c.id === id)}
        {@const CardView = cardComponent(id)}
        {@const bleed = FULL_BLEED.has(id)}
        <div
          class="band"
          class:inset={!bleed}
          data-cell={id}
          style:left="{band.x - ring}px"
          style:top="{band.y - ring}px"
          style:width="{band.w}px"
          style:height="{band.h}px"
          style:--box-t="{band.box.y}px"
          style:--box-l="{band.box.x}px"
          style:--box-r="{band.w - band.box.x - band.box.w}px"
          style:--box-b="{band.h - band.box.y - band.box.h}px"
          style:--badge-x="{band.box.x}px"
          style:--badge-y="{band.box.y}px"
        >
          {#if band.slot === 0}
            <Hero {view} />
          {:else if meta && !meta.hidden}
            <CardView
              {view}
              stale={meta.stale ? cardStale(view, id) : false}
              hero={false}
              {id}
            />
          {/if}
        </div>
      {/each}
    </div>
    <WatchHands
      shade={view.hero.kind === "card" && view.hero.card === "photo"}
    />
  </div>
</section>

<style>
  .round {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    /* A picture frame's lip narrows the room the disc is sized to. */
    padding-inline: var(--frame-x, 0px);
    padding-block: var(--frame-y, 0px);
    /* Outside the disc is plain black: nothing to draw there. */
    background: #000;
    overflow: hidden;
  }
  .disc {
    position: relative;
    border-radius: 50%;
    overflow: hidden;
    background: var(--stage);
    /* Its own layer, so a card repainting doesn't re-clip the whole face. */
    isolation: isolate;
  }
  /* Inside the chapter ring: the cards run out to it and curve with it. */
  .face {
    position: absolute;
    border-radius: 50%;
    overflow: hidden;
  }
  .band {
    position: absolute;
    overflow: hidden;
    border-radius: 20px;
  }
  /* The card fills its band edge to edge (its colour runs out to the rim)
     and sizes its type to its text box, by height as well as width, since
     a band is wide and short. */
  .disc .band > :global(*) {
    position: absolute;
    inset: 0;
    box-sizing: border-box;
    border-radius: 0;
    container-type: size;
    --type-hero: calc(
      clamp(2.25rem, min(20cqi, 46cqh), 13rem) * var(--ui-scale)
    );
    --type-xl: calc(clamp(1.4rem, min(20cqi, 34cqh), 7rem) * var(--ui-scale));
    --type-lg: calc(clamp(1.05rem, min(12cqi, 22cqh), 4rem) * var(--ui-scale));
    --type-md: calc(clamp(0.9rem, min(6cqi, 13cqh), 1.75rem) * var(--ui-scale));
    --type-sm: calc(clamp(0.8rem, min(4.2cqi, 9cqh), 1.3rem) * var(--ui-scale));
    --type-caption: calc(
      clamp(0.68rem, min(3cqi, 7cqh), 1.1rem) * var(--ui-scale)
    );
  }
  .disc .band.inset > :global(*) {
    padding: var(--box-t) var(--box-r) var(--box-b) var(--box-l);
    justify-content: center;
  }
</style>
