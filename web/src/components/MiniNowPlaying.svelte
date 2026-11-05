<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts" module>
  /** The slice of the nowPlaying store this needs (see NowPlaying.svelte). */
  export interface MiniTrack {
    title?: string;
    artist?: string;
    playing?: boolean;
    coverRev?: number;
    loading?: unknown;
  }

  /** Only while AirPlay is actually playing a track: not paused, not
      Antigua still fetching it, not a retained title from an old session. */
  export function miniShowing(track: MiniTrack | null | undefined): boolean {
    return !!track?.title && track.playing === true && !track.loading;
  }
</script>

<script lang="ts">
  import { cubicOut } from "svelte/easing";
  import { fade } from "svelte/transition";
  import { coverTint } from "../lib/coverTint";
  import { motion } from "../lib/tier.svelte";

  let {
    track,
    el = $bindable(null),
  }: {
    track: MiniTrack;
    /** The card's element, for the Photo Clock to put its live glass
        behind (it sets `data-live-glass` while it does). */
    el?: HTMLElement | null;
  } = $props();

  const base = import.meta.env.VITE_API_URL ?? "";
  const ms = (n: number) => (motion.reduced ? 0 : n);

  // The art swaps only once the new cover has decoded, so the crossfade is
  // picture to picture, never picture to blank.
  const coverUrl = $derived(
    track.coverRev ? `${base}/api/nowplaying/cover?v=${track.coverRev}` : null,
  );
  let art = $state<string | null>(null);
  let tint = $state<string | undefined>(undefined);
  $effect(() => {
    const url = coverUrl;
    if (!url) return;
    let live = true;
    const img = new Image();
    img.src = url;
    void img
      .decode()
      .catch(() => {})
      .then(() => {
        if (live) art = url;
      });
    void coverTint(url).then((t) => {
      if (live && t) tint = t;
    });
    return () => {
      live = false;
    };
  });

  const textKey = $derived(`${track.title ?? ""}|${track.artist ?? ""}`);

  // Fixed width; the height follows the text. The card's height is set from
  // the content's measured height, so a longer title glides the card taller
  // instead of snapping. Not on the first paint: it arrives at its size.
  let contentH = $state(0);
  let settled = $state(false);
  $effect(() => {
    const id = requestAnimationFrame(() =>
      requestAnimationFrame(() => (settled = true)),
    );
    return () => cancelAnimationFrame(id);
  });

  /** The outgoing lines leave the flow while they fade, so the card sizes
      to the incoming ones alone — one smooth resize, not two. */
  function fadeAway(node: HTMLElement, { duration }: { duration: number }) {
    node.style.position = "absolute";
    node.style.insetInline = "0";
    node.style.top = "50%";
    node.style.translate = "0 -50%";
    return { duration, css: (t: number) => `opacity: ${t}` };
  }

  // Rises and fades in, fades out: no scale, so the live glass behind
  // (sized to the card's untransformed box) stays true to it throughout.
  // Each tells the glass to follow along frame by frame.
  function arrive(node: HTMLElement, { duration }: { duration: number }) {
    node.dispatchEvent(new Event("glass:move"));
    return {
      duration,
      easing: cubicOut,
      css: (t: number) =>
        `opacity: ${t}; transform: translateY(${(1 - t) * 12}px)`,
    };
  }
  function leave(node: HTMLElement, { duration }: { duration: number }) {
    node.dispatchEvent(new Event("glass:move"));
    return { duration, css: (t: number) => `opacity: ${t}` };
  }
</script>

<div
  class="mini"
  bind:this={el}
  class:settled
  style:height={contentH ? `${contentH}px` : undefined}
  style:--tint={tint}
  role="status"
  aria-label="Now playing: {track.title}{track.artist
    ? ` by ${track.artist}`
    : ''}"
  in:arrive={{ duration: ms(520) }}
  out:leave={{ duration: ms(360) }}
>
  <div class="content" bind:offsetHeight={contentH}>
    <div class="art" aria-hidden="true">
      {#if art}
        {#key art}
          <img
            src={art}
            alt=""
            in:fade={{ duration: ms(600) }}
            out:fade={{ duration: ms(600) }}
          />
        {/key}
      {:else}
        <svg viewBox="0 0 24 24" class="note" out:fade={{ duration: ms(600) }}>
          <path d="M9 17.5V6l10-2v11.5" />
          <circle cx="6.5" cy="17.5" r="2.5" />
          <circle cx="16.5" cy="15.5" r="2.5" />
        </svg>
      {/if}
    </div>
    <div class="text" aria-hidden="true">
      {#key textKey}
        <div
          class="lines"
          in:fade={{ duration: ms(480), delay: ms(140) }}
          out:fadeAway={{ duration: ms(260) }}
        >
          <span class="title">{track.title}</span>
          {#if track.artist}<span class="artist">{track.artist}</span>{/if}
        </div>
      {/key}
    </div>
  </div>
</div>

<style>
  /* A small slab of Liquid Glass in the corner: the photo bends through it
     (blur + saturation), a bright rim on top, a faint wash of the cover's
     own colour so it belongs to the record. */
  .mini {
    --edge: min(5vh, 40px);
    position: fixed;
    right: calc(var(--edge) + var(--frame-x, 0px));
    bottom: calc(var(--edge) + var(--frame-y, 0px));
    z-index: 12;
    width: clamp(15rem, 27vmin, 30rem);
    overflow: hidden;
    pointer-events: none;
    --radius: clamp(14px, 2vmin, 30px);
    border-radius: var(--radius);
    transform-origin: 100% 100%;
    color: #fff;
    background:
      linear-gradient(
        160deg,
        rgb(255 255 255 / 0.2),
        rgb(255 255 255 / 0.04) 45%,
        rgb(255 255 255 / 0.08)
      ),
      color-mix(in srgb, var(--tint, #20242c) 26%, rgb(0 0 0 / 0.18));
    backdrop-filter: blur(22px) saturate(1.7) brightness(0.92);
    -webkit-backdrop-filter: blur(22px) saturate(1.7) brightness(0.92);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.42),
      inset 0 0 0 1px rgb(255 255 255 / 0.16),
      inset 0 -1px 0 rgb(0 0 0 / 0.14),
      0 1vmin 3.5vmin rgb(0 0 0 / 0.32);
    transition: background-color 900ms ease;
  }
  /* iOS's sheet curve: quick to start, a long soft landing. */
  .mini.settled {
    transition:
      height 560ms cubic-bezier(0.32, 0.72, 0, 1),
      background-color 900ms ease;
  }
  /* The Photo Clock's live glass is behind it (the same shader, look and
     photos as the clock's figures, rim, light and shadow included): the
     card keeps only a light scrim of the cover's colour for the text. */
  .mini:global([data-live-glass]) {
    background: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    box-shadow: none;
  }
  /* The scrim stops short of the glass's rim (half the rounding wide, as
     PhotoClock bakes it) and feathers into it, so the rim's light and
     bending show as they do on the figures. */
  .mini:global([data-live-glass])::before {
    --rim: calc(var(--radius) * 0.5);
    inset: calc(var(--rim) * 0.7);
    border-radius: calc(var(--radius) - var(--rim) * 0.7);
    background: color-mix(in srgb, var(--tint, #000) 22%, rgb(0 0 0 / 0.24));
    box-shadow: 0 0 calc(var(--rim) * 0.8) calc(var(--rim) * 0.25)
      color-mix(in srgb, var(--tint, #000) 22%, rgb(0 0 0 / 0.24));
    transition: background-color 900ms ease;
  }
  /* The specular sheen across the top edge. */
  .mini::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: radial-gradient(
      120% 70% at 18% 0%,
      rgb(255 255 255 / 0.22),
      transparent 60%
    );
    pointer-events: none;
  }

  .content {
    position: relative;
    display: flex;
    align-items: center;
    gap: clamp(10px, 1.4vmin, 22px);
    padding: clamp(8px, 1.1vmin, 18px);
  }

  .art {
    position: relative;
    flex: none;
    width: clamp(3rem, 6.2vmin, 7rem);
    aspect-ratio: 1;
    border-radius: clamp(8px, 1.1vmin, 16px);
    overflow: hidden;
    background: rgb(255 255 255 / 0.12);
    box-shadow:
      0 0.4vmin 1.2vmin rgb(0 0 0 / 0.3),
      inset 0 0 0 1px rgb(255 255 255 / 0.12);
  }
  .art img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .note {
    position: absolute;
    inset: 28%;
    fill: none;
    stroke: rgb(255 255 255 / 0.7);
    stroke-width: 1.6;
    stroke-linejoin: round;
  }

  .text {
    position: relative;
    flex: 1;
    min-width: 0;
  }
  .lines {
    display: flex;
    flex-direction: column;
    gap: 0.15em;
    min-width: 0;
    font-family: var(--font-body, -apple-system, sans-serif);
    text-shadow: 0 1px 6px rgb(0 0 0 / 0.25);
  }
  .title,
  .artist {
    overflow-wrap: anywhere;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .title {
    font-size: clamp(0.95rem, 1.85vmin, 1.9rem);
    font-weight: 600;
    line-height: 1.18;
    -webkit-line-clamp: 3;
    line-clamp: 3;
  }
  .artist {
    font-size: clamp(0.8rem, 1.5vmin, 1.5rem);
    line-height: 1.22;
    color: rgb(255 255 255 / 0.74);
    -webkit-line-clamp: 2;
    line-clamp: 2;
  }
</style>
