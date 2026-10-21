<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  Only ever rendered while Stage has it in its "on" phase (see videoHero.svelte.ts
  and Stage.svelte) — mounting is what starts the embed and unmounting tears it
  down, so there's no player sitting idle/buffering off-screen for the 3+
  minutes it's hidden, and every time it comes back it's back at the live edge.
-->
<script lang="ts">
  import { createClient } from "@pinedaview/protocol";

  import Card from "../components/Card.svelte";
  import { platform } from "../lib/platform.svelte";
  import type { CardProps } from "./types";

  let { stale, hero }: CardProps = $props();
  const client = createClient(import.meta.env.VITE_API_URL ?? "");

  const YOUTUBE_ID_RE =
    /(?:youtube\.com\/(?:live\/|watch\?(?:.*&)?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{11})/;

  function videoId(url: string): string | null {
    return YOUTUBE_ID_RE.exec(url)?.[1] ?? null;
  }

  let youtubeUrl = $state("");
  $effect(() => {
    void client
      .getCardSettings("video")
      .then((s) => (youtubeUrl = String(s.values.youtubeUrl ?? "")));
  });

  // YouTube's own player only ever fits *inside* whatever box it's given —
  // it letterboxes rather than crops. To go edge to edge we instead oversize
  // the iframe itself (classic CSS "cover" math against the fixed 16:9 embed
  // ratio) and clip it with the frame's own overflow:hidden, centred so a
  // too-wide frame loses its left/right edges rather than gaining bars.
  let frameEl = $state<HTMLDivElement | undefined>();
  let frameSize = $state({ w: 0, h: 0 });
  $effect(() => {
    const el = frameEl;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (box) frameSize = { w: box.width, h: box.height };
    });
    observer.observe(el);
    return () => observer.disconnect();
  });
  const playerBox = $derived.by(() => {
    const { w, h } = frameSize;
    if (!w || !h) return null;
    const scale = Math.max(w / 16, h / 9);
    return { width: `${16 * scale}px`, height: `${9 * scale}px` };
  });

  const id = $derived(videoId(youtubeUrl));
  // A live stream is near-certainly VP9 — the codec YouTube defaults to —
  // and a Pi 4's decoder block only takes H.264 in hardware, so this is pure
  // software decode there (measured: ~2 cores just for one embed). `vq` is a
  // long-deprecated, best-effort hint, but it's the only lever available
  // short of proxying the stream ourselves — capping it to 360p on a Pi cuts
  // the pixel count (and so the software-decode cost) to a quarter of 720p.
  const embedSrc = $derived(
    id
      ? `https://www.youtube-nocookie.com/embed/${id}` +
          `?autoplay=1&mute=1&controls=0&modestbranding=1&rel=0&playsinline=1&vq=${platform.isPi ? "medium" : "hd720"}`
      : null,
  );
</script>

<Card accent="generic" {stale} {hero} bleed={!!embedSrc}>
  {#if embedSrc}
    <div class="frame" bind:this={frameEl}>
      <iframe
        class="player"
        src={embedSrc}
        title="Live video"
        allow="autoplay; encrypted-media"
        allowfullscreen
        style:width={playerBox?.width ?? "100%"}
        style:height={playerBox?.height ?? "100%"}
      ></iframe>
    </div>
  {:else}
    <div class="invite">
      <span class="l1">No live video yet</span>
      <span class="l2"
        >Add a YouTube link in Settings › Cards & layout › Card options.</span
      >
    </div>
  {/if}
</Card>

<style>
  .frame {
    position: relative;
    align-self: stretch;
    flex: 1;
    min-height: var(--cell-min);
    border-radius: inherit;
    overflow: hidden;
    background: #000;
  }
  .player {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    border: none;
  }
  .invite {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    text-align: center;
    color: var(--on-card);
  }
  .l1 {
    font-size: var(--type-md);
  }
  .l2 {
    font-size: var(--type-sm);
    color: var(--on-card-soft);
  }
</style>
