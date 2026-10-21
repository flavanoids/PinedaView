<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The round Photo Clock: the library's photos in a disc on black, crossfading
  one to the next, with liquid glass hour and minute hands (and, if chosen, a
  second hand) over them. The glass is drawn live by lib/glassHands, bending
  whichever photo is behind it. The hands tick, or glide at 60 frames a
  second when Smooth is on.
-->
<script lang="ts">
  import { untrack } from "svelte";
  import { createClient, type Photo } from "@pinedaview/protocol";

  import type { PhotoClockSettings } from "../lib/clockface.svelte";
  import { findLight, type Light } from "../lib/glass";
  import { discCrop, GlassHands, type Hand, type RGB } from "../lib/glassHands";
  import { readLocal, writeLocal } from "../lib/storage";
  import { motion } from "../lib/tier.svelte";

  let {
    settings,
    tint = null,
    date = "",
    holdMs = 30_000,
  }: {
    /** Glass, opacity, date, second hand and smooth motion. */
    settings: PhotoClockSettings;
    /** The glass tint: #rrggbb, "auto" (each photo's own), or null. */
    tint?: string | null;
    /** Shown under the hub when the date is on. */
    date?: string;
    /** How long each photo stays before the next fades in. */
    holdMs?: number;
  } = $props();

  // Shared with the full-screen Photo Clock, so switching faces carries on
  // from the same photo.
  const RESUME_KEY = "pineda.photoClockResume";
  const FADE_MS = 2000;
  const RELIST_MS = 5 * 60_000;
  const client = createClient(import.meta.env.VITE_API_URL ?? "");

  let root = $state<HTMLDivElement>();
  let canvas = $state<HTMLCanvasElement>();
  let side = $state(0);
  $effect(() => {
    const el = root;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (box) side = Math.floor(Math.min(box.width, box.height));
    });
    observer.observe(el);
    return () => observer.disconnect();
  });

  // ── Photos: two slots, the one on top fading in over the other ──
  let photos: Photo[] = [];
  let index = 0;
  let sources = $state<[string, string]>(["", ""]);
  let rots = $state<[number, number]>([0, 0]);
  let tints = $state<[string, string]>(["", ""]);
  let top = $state<0 | 1>(0);
  const imgs: [HTMLImageElement | null, HTMLImageElement | null] = [null, null];
  const lights: [Light | null, Light | null] = [null, null];
  let fadeStart = -Infinity;

  let renderer: GlassHands | null = null;
  /** No WebGL here: plain hands, drawn as SVG. */
  let plain = $state(false);

  const frosted = $derived(settings.glass === "frosted");

  /** Hand slot i's photo to the glass, cropped to the disc as shown.
      Frosted glass sees it through a tiny copy, smoothly scaled up. */
  function upload(i: 0 | 1): void {
    const img = imgs[i];
    if (!img || !renderer || !side) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const crop = discCrop(
      img,
      rots[i],
      frosted ? 48 : Math.min(1024, Math.round(side * dpr)),
    );
    lights[i] = findLight(crop, sources[i]);
    renderer.setPhoto(i, crop);
  }

  async function load(i: 0 | 1, p: Photo): Promise<boolean> {
    const url = client.photoDisplayUrl(p.name);
    const img = new Image();
    img.src = url;
    try {
      await img.decode();
    } catch {
      return false;
    }
    imgs[i] = img;
    sources[i] = url;
    rots[i] = p.rotation ?? 0;
    tints[i] = p.tint ?? "";
    upload(i);
    return true;
  }

  async function show(p: Photo): Promise<void> {
    const next: 0 | 1 = sources[top] ? (top === 0 ? 1 : 0) : top;
    if (!(await load(next, p))) return;
    if (next !== top) {
      top = next;
      fadeStart = performance.now();
      wake();
    }
    writeLocal(RESUME_KEY, p.name);
    if (photos.length > 1) {
      const nextIndex = (index + 1) % photos.length;
      const nextPhoto = photos[nextIndex];
      if (nextPhoto) {
        new Image().src = client.photoDisplayUrl(nextPhoto.name);
      }
    }
  }

  function begin(list: Photo[]): void {
    photos = list;
    if (!list.length) return;
    const resumeAt = readLocal(RESUME_KEY);
    const prev = resumeAt ? list.findIndex((p) => p.name === resumeAt) : -1;
    index = prev >= 0 ? (prev + 1) % list.length : 0;
    void show(list[index]!);
  }

  $effect(() => {
    void holdMs;
    untrack(() => void client.listPhotos().then(begin, () => undefined));
    const step = setInterval(() => {
      if (photos.length < 2) return;
      index = (index + 1) % photos.length;
      void show(photos[index]!);
    }, holdMs);
    const relist = setInterval(() => {
      void client.listPhotos().then(
        (list) => {
          if (!photos.length) return begin(list);
          const current = photos[index]?.name;
          photos = list;
          index = Math.max(
            0,
            list.findIndex((p) => p.name === current),
          );
        },
        () => undefined,
      );
    }, RELIST_MS);
    return () => {
      clearInterval(step);
      clearInterval(relist);
    };
  });

  // ── The glass ──
  $effect(() => {
    const el = canvas;
    if (!el) return;
    renderer = GlassHands.create(el);
    plain = !renderer;
    const lost = (e: Event) => {
      e.preventDefault();
      renderer = null;
      plain = true;
    };
    el.addEventListener("webglcontextlost", lost);
    return () => {
      el.removeEventListener("webglcontextlost", lost);
      renderer?.dispose();
      renderer = null;
    };
  });

  // Size the canvas to the disc, and re-crop when the size or the frost changes.
  $effect(() => {
    const el = canvas;
    const s = side;
    void frosted;
    if (!el || !s || !renderer) return;
    renderer.resize(el, s, s, Math.min(2, window.devicePixelRatio || 1));
    untrack(() => {
      upload(0);
      upload(1);
      wake();
    });
  });

  function hex(h: string | null | undefined): RGB | null {
    if (!h || !/^#[0-9a-f]{6}$/i.test(h)) return null;
    return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as RGB;
  }

  const smooth = $derived(settings.sweep && !motion.reduced);
  const seconds = $derived(settings.seconds);

  /** Hand angles for `now`: ticking hands step on the second (and the
      minute hand on the minute); smooth ones are continuous. */
  function angles(now: Date): { h: number; m: number; s: number } {
    const ms = smooth ? now.getMilliseconds() / 1000 : 0;
    const s = now.getSeconds() + ms;
    const m = now.getMinutes() + (smooth ? s / 60 : 0);
    const h = (now.getHours() % 12) + m / 60;
    const turn = Math.PI * 2;
    return { h: (h / 12) * turn, m: (m / 60) * turn, s: (s / 60) * turn };
  }

  let plainAngles = $state({ h: 0, m: 0, s: 0 });

  function draw(): void {
    const a = angles(new Date());
    if (!renderer) {
      plainAngles = a;
      return;
    }
    const k = side / 1600;
    const hands: Hand[] = [
      { angle: a.h, length: 400 * k, tail: 50 * k, radius: 19 * k },
      { angle: a.m, length: 640 * k, tail: 70 * k, radius: 14 * k },
    ];
    if (seconds)
      hands.push({ angle: a.s, length: 690 * k, tail: 120 * k, radius: 5 * k });
    const t = Math.min(1, (performance.now() - fadeStart) / FADE_MS);
    // Smoothstep, near enough the photo's ease-in-out to keep in step.
    const p = t * t * (3 - 2 * t);
    const mix = top === 1 ? p : 1 - p;
    const light = lights[top] ?? lights[top === 0 ? 1 : 0];
    const lu = (light?.u ?? 0.15) - 0.5;
    const lv = (light?.v ?? -0.3) - 0.5;
    const ll = Math.hypot(lu, lv) || 1;
    renderer.draw(
      hands,
      (seconds ? 24 : 22) * k,
      {
        flat: settings.glass === "flat",
        milk: settings.opacity,
        tint: hex(tint === "auto" ? tints[top] : tint),
        light: [lu / ll, lv / ll],
        lightRgb: light?.rgb ?? [255, 250, 240],
      },
      mix,
    );
  }

  // ── The beat: every frame while gliding with a second hand or fading a
  // photo; otherwise on the second (ticking), or four times a second
  // (gliding without a second hand, where a minute hand's motion is too
  // slow to need more). ──
  let timer: ReturnType<typeof setTimeout> | undefined;
  let raf = 0;
  function beat(): void {
    timer = undefined;
    raf = 0;
    draw();
    const fading = performance.now() - fadeStart < FADE_MS;
    if ((smooth && seconds) || fading) {
      raf = requestAnimationFrame(beat);
    } else {
      const wait = smooth ? 250 : 1000 - (Date.now() % 1000) + 5;
      timer = setTimeout(beat, wait);
    }
  }
  function wake(): void {
    if (timer !== undefined) clearTimeout(timer);
    if (raf) cancelAnimationFrame(raf);
    beat();
  }
  $effect(() => {
    // Re-run when the beat's inputs or the look change.
    void smooth;
    void seconds;
    void settings.glass;
    void settings.opacity;
    void tint;
    void top;
    untrack(wake);
    return () => {
      if (timer !== undefined) clearTimeout(timer);
      if (raf) cancelAnimationFrame(raf);
      timer = undefined;
      raf = 0;
    };
  });

  const ticks = Array.from({ length: 12 }, (_, i) => {
    const a = (i / 12) * Math.PI * 2;
    return { i, x: Math.sin(a), y: -Math.cos(a) };
  });
  const deg = (r: number): number => (r * 180) / Math.PI;
</script>

<div class="round-photo-clock" bind:this={root}>
  <div
    class="disc"
    style:width="{side}px"
    style:height="{side}px"
    style:--fade-ms="{FADE_MS}ms"
  >
    {#each [0, 1] as i (i)}
      {#if sources[i]}
        <img
          class="photo"
          class:on={top === i}
          src={sources[i]}
          alt=""
          style:transform={rots[i] ? `rotate(${rots[i]}deg)` : undefined}
        />
      {/if}
    {/each}

    <svg class="ticks" viewBox="0 0 1600 1600" aria-hidden="true">
      {#each ticks as t (t.i)}
        <line
          x1={800 + t.x * (t.i % 3 ? 744 : 726)}
          y1={800 + t.y * (t.i % 3 ? 744 : 726)}
          x2={800 + t.x * 770}
          y2={800 + t.y * 770}
          stroke-width={t.i % 3 ? 6 : 10}
        />
      {/each}
    </svg>

    {#if settings.date && date}
      <div class="date">{date}</div>
    {/if}

    <canvas class="glass" bind:this={canvas} class:hidden={plain}></canvas>
    {#if plain}
      <svg class="plain" viewBox="0 0 1600 1600" aria-hidden="true">
        <g transform="rotate({deg(plainAngles.h)} 800 800)">
          <line x1="800" y1="850" x2="800" y2="400" stroke-width="38" />
        </g>
        <g transform="rotate({deg(plainAngles.m)} 800 800)">
          <line x1="800" y1="870" x2="800" y2="160" stroke-width="28" />
        </g>
        {#if seconds}
          <g transform="rotate({deg(plainAngles.s)} 800 800)">
            <line x1="800" y1="920" x2="800" y2="110" stroke-width="10" />
          </g>
        {/if}
        <circle cx="800" cy="800" r="22" />
      </svg>
    {/if}
    {#if settings.grain > 0}
      <div
        class="grain-overlay"
        style:opacity={settings.grain}
        aria-hidden="true"
      ></div>
    {/if}
  </div>
</div>

<style>
  .round-photo-clock {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    background: #000;
    overflow: hidden;
  }
  .disc {
    position: relative;
    border-radius: 50%;
    overflow: hidden;
    background: #000;
    isolation: isolate;
  }
  .photo {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  /* The new photo fades in over the old, which stays at full strength
     beneath it, so the disc never dims to the black behind both. */
  .photo.on {
    z-index: 1;
    animation: fade-in var(--fade-ms) cubic-bezier(0.45, 0, 0.55, 1) both;
  }
  @keyframes fade-in {
    from {
      opacity: 0;
    }
  }
  .ticks,
  .plain,
  .glass {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 2;
  }
  .ticks line {
    stroke: rgb(255 255 255 / 0.85);
    stroke-linecap: round;
  }
  /* Static, so its shadow is painted once, not every frame. */
  .ticks {
    filter: drop-shadow(0 2px 4px rgb(0 0 0 / 0.45));
  }
  .glass.hidden {
    display: none;
  }
  .plain line {
    stroke: rgb(255 255 255 / 0.85);
    stroke-linecap: round;
  }
  .plain circle {
    fill: rgb(255 255 255 / 0.9);
  }
  /* A plain pill, no backdrop blur: the hands sweep over it, and a blur
     under them would be redrawn every frame. */
  .date {
    position: absolute;
    z-index: 2;
    left: 50%;
    top: 69%;
    transform: translateX(-50%);
    font-family: var(--font-body, -apple-system, sans-serif);
    font-size: max(14px, 2.4cqmin);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    white-space: nowrap;
    color: rgb(255 255 255 / 0.92);
    background: rgb(0 0 0 / 0.32);
    padding: 0.45em 1.3em;
    border-radius: 40px;
    border: 1px solid rgb(255 255 255 / 0.2);
  }
  @media (prefers-reduced-motion: reduce) {
    .photo.on {
      animation: none;
    }
  }

  .grain-overlay {
    position: absolute;
    inset: 0;
    z-index: 3;
    pointer-events: none;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
    background-repeat: repeat;
    background-size: 140px 140px;
    mix-blend-mode: overlay;
    border-radius: 50%;
  }
</style>
