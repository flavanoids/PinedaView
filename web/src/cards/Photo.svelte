<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import QRCode from "qrcode";
  import { tick } from "svelte";
  import { createClient, type Photo } from "@pinedaview/protocol";

  import Card from "../components/Card.svelte";
  import { gesture } from "../lib/gestures";
  import { prefs } from "../lib/prefs.svelte";
  import { mirror, previewId } from "../lib/preview.svelte";
  import { photoShare } from "../lib/photoShare.svelte";
  import { readLocal, writeLocal } from "../lib/storage";
  import { motion } from "../lib/tier.svelte";
  import type { CardProps } from "./types";

  let { view, stale, hero }: CardProps = $props();

  // Where the slideshow left off, by photo name, so a reload or overnight
  // reboot resumes mid-deck instead of restarting at the first photo every
  // time — with 250+ photos on a 10s cycle, a fresh start never got far.
  const RESUME_KEY = "pineda.photoResume";

  const client = createClient(import.meta.env.VITE_API_URL ?? "");
  // The QR opens a small menu (photos, theme, restart) rather than dropping
  // a phone straight into the full kiosk dashboard or just the uploader.
  // On the kiosk the page comes from its local failover proxy, so
  // location.origin is loopback; ask the server for its LAN address instead.
  const loopback = /^(localhost|127\.|\[::1\])/.test(location.hostname);
  let menuUrl = $state(loopback ? "" : `${location.origin}/menu`);
  // Keep asking until it answers (e.g. mid server restart): a loopback QR is
  // useless to a phone, so never fall back to it.
  async function fetchMenuUrl(): Promise<void> {
    for (let wait = 2_000; ; wait = Math.min(wait * 2, 60_000)) {
      try {
        const r = await fetch(
          `${import.meta.env.VITE_API_URL ?? ""}/api/menu-url`,
        );
        if (r.ok) {
          menuUrl = ((await r.json()) as { url: string }).url;
          return;
        }
      } catch {
        /* retry */
      }
      await new Promise((done) => setTimeout(done, wait));
    }
  }
  // Ask again every minute: a failover swaps the server behind the proxy
  // without reloading the page, and the QR should name whichever is serving.
  let asking = false;
  function recheckMenuUrl(): void {
    if (asking) return;
    asking = true;
    void fetchMenuUrl().finally(() => (asking = false));
  }
  $effect(() => {
    if (!loopback) return;
    recheckMenuUrl();
    const timer = setInterval(recheckMenuUrl, 60_000);
    return () => clearInterval(timer);
  });

  // Hold each photo for Settings → Photos → "Show each photo for" (20s by
  // default), then a slow 1.6s crossfade. Not much under 10s on the kiosk:
  // every swap is a decode + GPU upload there.
  const holdMs = $derived(prefs.photo_hold_s * 1000);

  /** The slideshow's order (Settings → Photos → Order): yours, newest
      first, or shuffled afresh each time the screen loads. */
  function arrange(list: Photo[], order: string): Photo[] {
    if (order === "newest") {
      const when = (p: Photo) => p.taken_at ?? p.uploaded_at;
      return [...list].sort((a, b) => when(b) - when(a));
    }
    if (order === "shuffle") {
      const out = [...list];
      for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [out[i], out[j]] = [out[j]!, out[i]!];
      }
      return out;
    }
    return list;
  }

  let photos = $state<Photo[]>([]);
  let qr = $state("");
  let index = $state(0);
  // Two stacked <img> layers that cross-dissolve; `top` is the visible one.
  let sources = $state<[string, string]>(["", ""]);
  let rots = $state<[number, number]>([0, 0]);
  let top = $state(0);
  let imgs = $state<(HTMLImageElement | undefined)[]>([]);
  let swapping = false;

  /** The showing photo's Live Photo clip, looped like a gif over its still
      (the clip's middle frame). Not in the menu's miniature, and not when
      motion is turned down. */
  const live = $derived.by(() => {
    const p = photos[index];
    return p?.motion && !previewId && !motion.reduced && !motion.batterySaver
      ? client.photoMotionUrl(p.name)
      : "";
  });
  let playing = $state(false);
  $effect(() => {
    void live;
    playing = false;
  });

  // Keep the browser's decode cache warm for the photo after this one, so the
  // next crossfade has nothing to wait on.
  function preload(i: number): void {
    const p = photos[i];
    if (p) new Image().src = client.photoDisplayUrl(p.name);
  }

  $effect(() => {
    const order = prefs.photo_order;
    void client.listPhotos().then((fetched) => {
      const list = arrange(fetched, order);
      photos = list;
      if (list.length === 0) return;
      if (previewId) {
        // The menu's miniature: start on the real screen's photo.
        const at = list.findIndex((p) => p.name === mirror.photo);
        index = Math.max(0, at);
      } else {
        // The Photo Clock's photo when it hands over to the cards; otherwise
        // the one after where the slideshow left off.
        const shared = list.findIndex((p) => p.name === photoShare.name);
        const resumeAt = readLocal(RESUME_KEY);
        const prev = resumeAt ? list.findIndex((p) => p.name === resumeAt) : -1;
        index = shared >= 0 ? shared : prev >= 0 ? (prev + 1) % list.length : 0;
      }
      const start = list[index];
      if (!start) return;
      sources[top] = client.photoDisplayUrl(start.name);
      rots[top] = start.rotation ?? 0;
      if (previewId) return;
      photoShare.name = start.name;
      writeLocal(RESUME_KEY, start.name);
      void client.reportShowing(view.device_id, "photo", start.name);
      preload((index + 1) % list.length);
    });
  });

  // The menu acts on whichever screen was scanned, so name this one.
  const scanUrl = $derived(
    menuUrl ? `${menuUrl}?screen=${encodeURIComponent(view.device_id)}` : "",
  );

  $effect(() => {
    if (!scanUrl) return;
    void QRCode.toString(scanUrl, {
      type: "svg",
      margin: 1,
      color: { light: "#0000" },
    }).then((svg) => (qr = svg));
  });

  $effect(() => {
    if (photos.length < 2 || previewId) return;
    const id = setInterval(() => void step(1), holdMs);
    return () => clearInterval(id);
  });

  // The menu's miniature crossfades when the real screen does.
  $effect(() => {
    if (!previewId || !mirror.photo) return;
    const at = photos.findIndex((p) => p.name === mirror.photo);
    if (at >= 0 && at !== index) void show(at, 1);
  });

  // Mounted early, out of sight, while the Photo Clock is still up: keep up
  // with its swipes so the handoff lands on the photo that was showing.
  $effect(() => {
    const name = photoShare.name;
    if (previewId || !name || photos[index]?.name === name) return;
    const at = photos.findIndex((p) => p.name === name);
    if (at >= 0) void show(at, 1);
  });

  function step(delta: number): Promise<void> {
    return show((index + delta + photos.length) % photos.length, delta);
  }

  async function show(nextIndex: number, delta: number): Promise<void> {
    if (photos.length < 2 || swapping) return;
    swapping = true;
    try {
      const next = photos[nextIndex];
      if (!next) return;
      const back = (1 - top) as 0 | 1;
      sources[back] = client.photoDisplayUrl(next.name);
      rots[back] = next.rotation ?? 0;
      await tick();
      // Wait until the incoming frame is actually ready to paint — otherwise a
      // slow decode lands *during* the opacity fade and the whole card
      // hitches. If decode isn't supported / rejects, fall through anyway.
      try {
        await imgs[back]?.decode();
      } catch {
        /* show it regardless */
      }
      top = back;
      index = nextIndex;
      if (previewId) return;
      photoShare.name = next.name;
      writeLocal(RESUME_KEY, next.name);
      void client.reportShowing(view.device_id, "photo", next.name);
      preload((nextIndex + delta + photos.length) % photos.length);
    } finally {
      swapping = false;
    }
  }
</script>

<Card accent="generic" {stale} {hero} bleed={photos.length > 0}>
  <div
    class="frame"
    class:hero
    class:fit={prefs.photo_fit === "fit"}
    use:gesture={{
      onSwipe: (g) => {
        if (g === "swipe-left") void step(1);
        if (g === "swipe-right") void step(-1);
      },
    }}
  >
    {#if photos.length > 0}
      {#each sources as src, i (i)}
        <img
          class="layer"
          class:show={i === top}
          bind:this={imgs[i]}
          {src}
          alt=""
          decoding="async"
          fetchpriority={i === top ? "high" : "low"}
          style:--rot="{rots[i]}deg"
        />
      {/each}
      {#key live}
        {#if live}
          <!-- Fades in once frames are coming, so a slow start just shows the still. -->
          <video
            class="layer motion"
            class:show={playing}
            src={live}
            muted
            playsinline
            autoplay
            loop
            onplaying={() => (playing = true)}
            onemptied={() => (playing = false)}
            style:--rot="{rots[top]}deg"
          ></video>
        {/if}
      {/key}
      {#if qr}
        <a class="badge" href={scanUrl} aria-label="Scan for settings">
          <!-- eslint-disable-next-line svelte/no-at-html-tags -- qrcode lib output -->
          {@html qr}
          <span class="badge-label" aria-hidden="true">Settings</span>
        </a>
      {/if}
    {:else}
      <div class="invite">
        {#if qr}
          <!-- eslint-disable-next-line svelte/no-at-html-tags -- qrcode lib output -->
          <div class="bigqr">{@html qr}</div>
        {/if}
        <span class="l1">Scan for photos &amp; settings</span>
        <span class="l2">{menuUrl}</span>
      </div>
    {/if}
  </div>
</Card>

<style>
  .frame {
    position: relative;
    align-self: stretch;
    flex: 1;
    min-height: max(var(--cell-min), 38vw);
    border-radius: inherit;
    overflow: hidden;
    touch-action: pan-y;
    /* A black bed so the first frame's fade-in and any letterbox sliver read
       as photographic rather than as the card colour flashing through. */
    background: #000;
  }
  .frame.hero {
    min-height: min(56vh, 60vw);
  }
  .layer {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    /* Fill the card edge to edge regardless of the photo's aspect ratio. */
    object-fit: cover;
    object-position: center;
    opacity: 0;
    /* Promote each layer to its own compositor surface so the crossfade is a
       GPU opacity blend — no per-frame repaint, smooth even on the Pi. The
       `--rot` is a manual rotation from the photo editor (0 for almost every
       photo — the camera's EXIF orientation is honoured automatically). */
    transform: translateZ(0) rotate(var(--rot, 0deg));
    will-change: opacity;
    transition: opacity 1600ms ease;
  }
  .layer.show {
    opacity: 1;
  }
  .motion {
    transition-duration: 400ms;
  }
  /* "Show the whole photo": letterboxed on the black bed, nothing cropped. */
  .fit .layer {
    object-fit: contain;
  }
  /* Only a hard accessibility opt-out kills the fade now — the Pi keeps it,
     since a composited opacity blend is cheap once decode is done up front. */
  @media (prefers-reduced-motion: reduce) {
    .layer {
      transition: none;
    }
  }
  /* Top-left, so it sits in the corner opposite the news card's "Read"
     code. The label is white on a dark fade out of the corner; the code
     sits on a frosted plate (translucent white, dark modules) that lets
     the photo's colour through without costing a scanner its contrast. A
     plain gradient and alpha, not a backdrop blur — that would
     re-rasterise under every crossfade on the Pi. */
  .frame:has(.badge)::after {
    content: "";
    position: absolute;
    /* --badge-x/y: a round screen moves the code in from the clipped corner. */
    left: calc(var(--badge-x, 18px) - 18px);
    top: calc(var(--badge-y, 18px) - 18px);
    width: calc(var(--qr-badge) * 2.6);
    height: calc(var(--qr-badge) * 2.4);
    background: radial-gradient(
      closest-side at 0% 0%,
      rgba(0, 0, 0, 0.5),
      rgba(0, 0, 0, 0.24) 55%,
      transparent
    );
    pointer-events: none;
  }
  .badge {
    position: absolute;
    z-index: 1;
    left: var(--badge-x, 18px);
    top: var(--badge-y, 18px);
    width: var(--qr-badge);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    text-decoration: none;
  }
  /* Says what the code is for, so a guest doesn't wonder whether it's safe. */
  .badge-label {
    font-size: var(--type-caption);
    font-weight: 600;
    line-height: 1.1;
    white-space: nowrap;
    color: #fff;
    text-shadow: 0 1px 6px rgba(0, 0, 0, 0.7);
  }
  .badge :global(svg) {
    display: block;
    width: 100%;
    aspect-ratio: 1;
    height: auto;
    padding: 4px;
    background: rgba(255, 255, 255, 0.8);
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.25);
  }
  .badge :global(path) {
    stroke: #16161a;
  }
  .invite {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-3);
    text-align: center;
    color: var(--on-card);
  }
  .bigqr {
    width: min(46%, var(--qr-size));
    aspect-ratio: 1;
    padding: 10px;
    background: #fff;
    border-radius: 12px;
  }
  .bigqr :global(svg) {
    display: block;
    width: 100%;
    height: 100%;
  }
  .l1 {
    font-size: var(--type-md);
  }
  .l2 {
    font-size: var(--type-sm);
    color: var(--on-card-soft);
    word-break: break-all;
  }
</style>
