<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { createClient, type components } from "@pinedaview/protocol";
  import { untrack } from "svelte";
  import { cubicInOut } from "svelte/easing";

  import { chooseLayout, letterRange } from "../lib/collage";

  type Takeover = components["schemas"]["Takeover"];
  type ImageSearch = components["schemas"]["ImageSearchTakeover"];
  type ImageItem = components["schemas"]["ImageItem"];

  interface Props {
    takeover: Takeover;
  }
  let { takeover }: Props = $props();

  const client = createClient(import.meta.env.VITE_API_URL ?? "");
  const card = $derived(takeover.card as ImageSearch);

  // A picture none of whose sources worked leaves the collage, and the rest
  // close up around it. `soft` ones are shown whole over a blur of
  // themselves: too small for their tile, or a shape it would crop hard.
  let failed = $state<Record<string, boolean>>({});
  let loaded = $state<Record<string, boolean>>({});
  let soft = $state<Record<string, boolean>>({});

  const shown = $derived(
    (card.images ?? []).filter((i) => !failed[i.id]).slice(0, 8),
  );
  let boxW = $state(0);
  let boxH = $state(0);
  // A comparison ("Fuji vs Honeycrisp") is two labelled sides, side by
  // side (stacked on a portrait screen), each laid out on its own.
  const sections = $derived.by(() => {
    const byId = new Map(shown.map((i) => [i.id, i]));
    const sides = (card.groups ?? [])
      .map((g) => ({
        label: g.label,
        items: g.ids.flatMap((id) => byId.get(id) ?? []),
      }))
      .filter((g) => g.items.length > 0);
    const parts = sides.length > 1 ? sides : [{ label: "", items: shown }];
    const box = boxW > 0 && boxH > 0 ? boxW / boxH : 16 / 10;
    const each =
      parts.length === 1
        ? box
        : boxH > boxW
          ? (box * parts.length) / 0.9
          : (box / parts.length) * 0.9;
    return parts.map((p) => ({
      ...p,
      layout: chooseLayout(
        p.items.map((i) => i.aspect_ratio ?? 1),
        each,
      ),
    }));
  });
  // Arrival order, across the sides.
  const order = $derived(sections.flatMap((sec) => sec.items));
  const active = $derived(card.highlight?.toUpperCase() ?? null);
  const hint = $derived(letterRange(shown.map((i) => i.id)));
  const heading = $derived(
    card.query.charAt(0).toUpperCase() + card.query.slice(1),
  );

  // The bar drains over whatever time is left (as on the recipe card).
  // Opening a picture gives the card fresh time (a new expires_at): the bar
  // refills and drains that instead.
  const firstExpiry = untrack(() => takeover.expires_at);
  const totalMs = $derived(
    Date.parse(takeover.expires_at) - Date.parse(takeover.shown_at),
  );
  const leftMs = $derived(
    Math.max(0, Date.parse(takeover.expires_at) - Date.now()),
  );
  const drainFrom = $derived(
    takeover.expires_at !== firstExpiry || totalMs <= 0 ? 1 : leftMs / totalMs,
  );

  // The server fetches and shrinks each picture (image_proxy): many sites
  // refuse the kiosk loading them directly. shown_at keys the browser cache
  // to this card, since letters repeat from one search to the next.
  function picture(id: string, size: "thumb" | "full"): string {
    const v = encodeURIComponent(takeover.shown_at);
    const again = retried[id] ? "&again=1" : "";
    return `/api/takeover/images/${encodeURIComponent(id)}?size=${size}&v=${v}${again}`;
  }

  // One more try before a picture leaves: a server restart or a moment on
  // the standby shouldn't empty the collage for good.
  let retried = $state<Record<string, boolean>>({});
  function missing(id: string): void {
    if (retried[id]) {
      failed[id] = true;
      return;
    }
    setTimeout(() => (retried[id] = true), 1500);
  }

  function arrived(event: Event, item: ImageItem): void {
    const img = event.currentTarget as HTMLImageElement;
    const tile = img.parentElement?.getBoundingClientRect();
    if (tile && tile.width > 0 && img.naturalWidth > 0) {
      const upscale = Math.max(
        tile.width / img.naturalWidth,
        tile.height / img.naturalHeight,
      );
      const tileAspect = tile.width / tile.height;
      const aspect = img.naturalWidth / img.naturalHeight;
      const kept = Math.min(tileAspect, aspect) / Math.max(tileAspect, aspect);
      soft[item.id] = upscale > 1.8 || kept < 0.55;
    }
    if (img.naturalHeight > 0) {
      natural[item.id] = img.naturalWidth / img.naturalHeight;
    }
    loaded[item.id] = true;
  }

  // The opened picture fills the screen, whole: never cropped or stretched.
  const zoomed = $derived(
    shown.find((i) => i.id.toUpperCase() === active) ?? null,
  );
  let natural = $state<Record<string, number>>({});
  const tiles: Record<string, HTMLElement> = {};

  // Opening a picture from the collage zooms it out of its tile, and "go
  // back" zooms it home; "next" from one open picture to another fades.
  let stepping = false;
  let was: string | null = null;
  $effect.pre(() => {
    const now = zoomed?.id ?? null;
    stepping = was !== null && now !== null && was !== now;
    was = now;
  });

  function zoom(node: HTMLElement, { id }: { id: string }) {
    const fade = { duration: 320, css: (t: number) => `opacity: ${t}` };
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return { duration: 0 };
    }
    const tile = tiles[id]?.getBoundingClientRect();
    const box = node.getBoundingClientRect();
    const photo = node.querySelector<HTMLElement>(".zoom-photo");
    if (stepping || !tile || !tile.width || !box.width || !photo) return fade;
    // Where the whole picture sits on the screen, and how much bigger it
    // must be to cover the tile it came from, centred on the tile.
    const item = shown.find((i) => i.id === id);
    const aspect = natural[id] ?? item?.aspect_ratio ?? 1;
    const w = Math.min(box.width, box.height * aspect);
    const h = w / aspect;
    const grow = Math.max(tile.width / w, tile.height / h);
    const dx = tile.left + tile.width / 2 - (box.left + box.width / 2);
    const dy = tile.top + tile.height / 2 - (box.top + box.height / 2);
    const inset = [
      tile.top - box.top,
      box.right - tile.right,
      box.bottom - tile.bottom,
      tile.left - box.left,
    ];
    const radius = parseFloat(getComputedStyle(tiles[id]!).borderRadius) || 0;
    return {
      duration: 560,
      easing: cubicInOut,
      css: (t: number) => {
        const u = 1 - t;
        const clip = inset.map((v) => `${v * u}px`).join(" ");
        return `clip-path: inset(${clip} round ${radius * u}px);`;
      },
      tick: (t: number) => {
        const u = 1 - t;
        photo.style.transform = `translate(${dx * u}px, ${dy * u}px) scale(${1 + (grow - 1) * u})`;
      },
    };
  }

  // The collage itself leaves (its time is up, or "stop the display") by
  // fading back into whatever the screen was showing.
  function leave(_node: HTMLElement) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return { duration: 0 };
    }
    return {
      duration: 420,
      easing: cubicInOut,
      css: (t: number) =>
        `opacity: ${t}; transform: scale(${0.97 + 0.03 * t});`,
    };
  }

  // A tap does what "tell me about B" / "back" does by voice.
  function focus(id: string | null): void {
    void client.updateTakeover({ highlight: id }).catch(() => {});
  }

  function dismiss(): void {
    void client.clearTakeover().catch(() => {});
  }
</script>

<div
  class="collage"
  class:spotlit={active !== null}
  style:--left={`${leftMs}ms`}
  out:leave|global
>
  <header>
    <div class="title">
      <p class="kicker">Pictures</p>
      <h1>{heading}</h1>
    </div>
    <p class="hint">
      <span>Say <strong>“show me {shown[0]?.id ?? "A"}”</strong></span>
      <span class="or">or ask about <strong>{hint}</strong></span>
    </p>
    <button type="button" class="close" onclick={dismiss} aria-label="Close">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M18 6 6 18M6 6l12 12" />
      </svg>
    </button>
  </header>

  <div class="stage">
    <main
      class="sections"
      class:stacked={boxH > boxW}
      bind:clientWidth={boxW}
      bind:clientHeight={boxH}
    >
      {#each sections as sec (sec.label)}
        <section class="side">
          {#if sec.label}
            <h2 class="side-label">{sec.label}</h2>
          {/if}
          <div
            class="grid"
            style:grid-template-columns={`repeat(${sec.layout.cols}, minmax(0, 1fr))`}
            style:grid-template-rows={`repeat(${sec.layout.rows}, minmax(0, 1fr))`}
            style:grid-template-areas={sec.layout.areas.join(" ")}
          >
            {#each sec.items as item, idx (item.id)}
              {@const lit = active === item.id.toUpperCase()}
              <div
                class="tile"
                class:hero={idx === 0}
                class:lit
                bind:this={tiles[item.id]}
                class:loaded={loaded[item.id]}
                class:soft={soft[item.id]}
                style:grid-area={sec.layout.slots[idx]}
                style:--i={order.indexOf(item)}
                role="button"
                tabindex="0"
                aria-label={`Picture ${item.id}`}
                onclick={() => focus(item.id)}
                onkeydown={(e) => e.key === "Enter" && focus(item.id)}
              >
                <img
                  class="backdrop"
                  src={picture(item.id, "thumb")}
                  alt=""
                  aria-hidden="true"
                  decoding="async"
                />
                <img
                  class="photo"
                  src={picture(item.id, "full")}
                  alt={item.title || card.query}
                  decoding="async"
                  onload={(e) => arrived(e, item)}
                  onerror={() => missing(item.id)}
                />
                <span class="badge">{item.id}</span>
                <div class="caption">
                  {#if item.title}
                    <h2>{item.title}</h2>
                  {/if}
                  {#if item.source}
                    <span class="source">{item.source}</span>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </section>
      {/each}
    </main>
  </div>

  <!-- An each of one: the picture going away keeps its own item while it
       zooms home, after `zoomed` has already moved on. -->
  {#each zoomed ? [zoomed] : [] as z (z.id)}
    <div
      class="zoom"
      transition:zoom|global={{ id: z.id }}
      role="button"
      tabindex="0"
      aria-label="Back to all the pictures"
      onclick={() => focus(null)}
      onkeydown={(e) => e.key === "Enter" && focus(null)}
    >
      <img
        class="backdrop"
        src={picture(z.id, "thumb")}
        alt=""
        aria-hidden="true"
      />
      <img
        class="zoom-photo"
        src={picture(z.id, "full")}
        alt={z.title || card.query}
      />
      <div class="zoom-caption">
        <span class="badge">{z.id}</span>
        <div class="zoom-text">
          {#if z.title}
            <h2>{z.title}</h2>
          {/if}
          {#if z.source}
            <span class="source">{z.source}</span>
          {/if}
          {#if z.snippet}
            <p class="snippet">{z.snippet}</p>
          {/if}
        </div>
        <p class="zoom-hint">Say “next”, “previous” or “go back”</p>
      </div>
    </div>
  {/each}

  {#key takeover.expires_at}
    <div class="drain" aria-hidden="true" style:--from={drainFrom}></div>
  {/key}
</div>

<style>
  .collage {
    position: fixed;
    inset: 0;
    z-index: 25;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: var(--space-3);
    padding: calc(
        max(var(--space-4), env(safe-area-inset-top)) + var(--frame-y, 0px)
      )
      calc(
        max(var(--space-4), env(safe-area-inset-right)) + var(--frame-x, 0px)
      )
      calc(var(--space-4) + var(--frame-y, 0px))
      calc(max(var(--space-4), env(safe-area-inset-left)) + var(--frame-x, 0px));
    background: var(--stage);
    color: var(--on-stage);
    font-family: var(--font-body);
    overflow: hidden;
    user-select: none;
  }

  header {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    min-width: 0;
  }
  .title {
    flex: 1;
    min-width: 0;
  }
  .kicker {
    margin: 0;
    color: var(--accent);
    font-family: var(--font-display);
    font-weight: var(--weight-label);
    font-size: var(--type-sm);
  }
  h1 {
    margin: 0;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: calc(var(--type-lg) * 0.8);
    line-height: 1.1;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
  .hint {
    margin: 0;
    flex-shrink: 0;
    display: grid;
    justify-items: end;
    gap: 0.15em;
    color: var(--on-stage-soft);
    font-size: var(--type-sm);
  }
  .hint strong {
    color: var(--on-stage);
    font-weight: var(--weight-label);
  }
  .or {
    font-size: var(--type-caption);
  }
  .close {
    flex-shrink: 0;
    display: grid;
    place-items: center;
    width: calc(2.6rem * var(--ui-scale));
    aspect-ratio: 1;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: color-mix(in srgb, var(--on-stage) 10%, transparent);
    color: var(--on-stage-soft);
    cursor: pointer;
  }
  .close svg {
    width: 45%;
    fill: none;
    stroke: currentColor;
    stroke-width: 2.4;
    stroke-linecap: round;
  }

  .stage {
    display: grid;
    min-height: 0;
  }
  .sections {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
    gap: var(--space-5);
    min-height: 0;
    transition:
      opacity var(--dur-mid) ease,
      transform var(--dur-mid) var(--ease-spring);
  }
  .sections.stacked {
    grid-auto-flow: row;
    grid-auto-rows: minmax(0, 1fr);
  }
  .side {
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: var(--space-2);
    min-width: 0;
    min-height: 0;
  }
  .side:only-child {
    grid-template-rows: minmax(0, 1fr);
  }
  .side-label {
    display: flex;
    align-items: center;
    gap: 0.5em;
    color: var(--on-stage);
    font-size: var(--type-md);
  }
  .side-label::before {
    content: "";
    width: 0.3em;
    height: 1em;
    border-radius: var(--radius-pill);
    background: var(--accent);
  }
  .grid {
    display: grid;
    gap: var(--space-3);
    min-height: 0;
  }
  /* The open picture has lifted out of its tile. */
  .tile.lit {
    visibility: hidden;
  }
  .tile {
    cursor: pointer;
  }

  .tile {
    position: relative;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    border-radius: var(--radius-card);
    background: color-mix(in srgb, var(--on-stage) 8%, var(--stage));
    transition:
      opacity var(--dur-normal) ease,
      filter var(--dur-normal) ease,
      box-shadow var(--dur-normal) ease;
  }

  img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  /* The engine's thumbnail, blurred: the tile's placeholder while the
     picture arrives, and the backdrop behind a soft one. */
  .backdrop {
    filter: blur(1.4rem) saturate(1.2) brightness(0.7);
    transform: scale(1.15);
  }
  .photo {
    opacity: 0;
    transition: opacity var(--dur-slow) ease;
  }
  .loaded .photo {
    opacity: 1;
  }
  .soft .photo {
    object-fit: contain;
  }

  .badge {
    position: absolute;
    top: var(--space-2);
    left: var(--space-2);
    display: grid;
    place-items: center;
    width: calc(2.4rem * var(--ui-scale));
    aspect-ratio: 1;
    border-radius: 50%;
    background: rgb(0 0 0 / 0.55);
    box-shadow: 0 0 0 0.12em rgb(255 255 255 / 0.35);
    color: #fff;
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: var(--type-md);
    line-height: 1;
    transition:
      background var(--dur-normal) ease,
      color var(--dur-normal) ease,
      transform var(--dur-normal) var(--ease-spring);
  }

  /* Photos are any colour, so the caption sits on its own dark scrim
     whatever the theme. */
  .caption {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    display: grid;
    gap: 0.2em;
    padding: var(--space-5) var(--space-3) var(--space-2);
    background: linear-gradient(
      to top,
      rgb(0 0 0 / 0.78),
      rgb(0 0 0 / 0.45) 60%,
      transparent
    );
    color: #fff;
  }
  h2 {
    margin: 0;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    font-family: var(--font-display);
    font-weight: var(--weight-label);
    font-size: var(--type-caption);
    line-height: 1.2;
    text-wrap: balance;
  }
  .hero h2 {
    font-size: var(--type-sm);
  }
  .source {
    font-size: calc(var(--type-caption) * 0.8);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    opacity: 0.75;
  }
  .snippet {
    margin: 0;
    font-size: var(--type-sm);
    line-height: 1.35;
    opacity: 0.85;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
  }
  /* Full screen: the whole picture over a blur of itself, its caption on
     a scrim at the bottom. Above the header; below the countdown. */
  .zoom {
    position: fixed;
    inset: 0;
    z-index: 2;
    overflow: hidden;
    background: var(--stage);
    cursor: zoom-out;
  }
  .zoom .backdrop {
    filter: blur(2rem) saturate(1.1) brightness(0.55);
  }
  .zoom-photo {
    object-fit: contain;
    transform-origin: center;
  }
  .zoom-caption {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: flex-end;
    gap: var(--space-3);
    padding: var(--space-6, 4rem) calc(var(--space-5) + var(--frame-x, 0px))
      calc(var(--space-4) + var(--frame-y, 0px));
    background: linear-gradient(to top, rgb(0 0 0 / 0.8), transparent);
    color: #fff;
  }
  .zoom-caption .badge {
    position: static;
    flex-shrink: 0;
    width: calc(3rem * var(--ui-scale));
    background: var(--accent);
    box-shadow: none;
    color: var(--stage);
    font-size: var(--type-lg);
  }
  .zoom-text {
    flex: 1;
    display: grid;
    gap: 0.25em;
    min-width: 0;
  }
  .zoom-text h2 {
    font-weight: var(--weight-display);
    font-size: var(--type-md);
  }
  .zoom-hint {
    margin: 0;
    flex-shrink: 0;
    font-size: var(--type-caption);
    opacity: 0.75;
  }

  .lit {
    box-shadow: 0 0 0 0.2rem var(--accent);
  }
  .lit .badge {
    background: var(--accent);
    color: var(--stage);
  }

  .drain {
    position: absolute;
    z-index: 3;
    left: 0;
    right: 0;
    bottom: var(--frame-y, 0px);
    height: calc(0.3rem * var(--ui-scale));
    background: var(--accent);
    transform-origin: left center;
    transform: scaleX(var(--from));
    animation: drain var(--left) linear forwards;
    opacity: 0.85;
  }
  @keyframes drain {
    from {
      transform: scaleX(var(--from));
    }
    to {
      transform: scaleX(0);
    }
  }

  @media (prefers-reduced-motion: no-preference) {
    .collage {
      animation: rise var(--dur-mid) var(--ease-spring) both;
    }
    /* Tiles arrive one after another, best first. */
    .tile {
      animation: arrive var(--dur-slow) var(--ease-spring) both;
      animation-delay: calc(var(--i) * 70ms);
    }
    /* The big picture drifts slowly while the collage is up. */
    .hero:not(.soft) .photo {
      animation: drift 40s linear both;
    }
    .spotlit .hero .photo {
      animation-play-state: paused;
    }
    .zoom-caption {
      animation: caption-in var(--dur-mid) ease 0.45s both;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .drain {
      animation: none;
    }
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: scale(0.985);
    }
  }
  @keyframes arrive {
    from {
      opacity: 0;
      transform: translateY(1.5vh) scale(0.97);
    }
  }
  @keyframes caption-in {
    from {
      opacity: 0;
      transform: translateY(1rem);
    }
  }
  @keyframes drift {
    from {
      transform: scale(1.02);
    }
    to {
      transform: scale(1.1) translate(-1.5%, -1%);
    }
  }

  @media (orientation: portrait) {
    .or {
      display: none;
    }
  }
</style>
