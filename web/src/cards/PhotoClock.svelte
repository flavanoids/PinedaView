<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The "photo" clock face: the library's photos 30 s each, the time in
  glass numerals over them, and — when the server has cut the subject out
  (photos.py, rembg) — that cutout laid on top so people stand in front of
  the time.
-->
<script lang="ts">
  import { tick, untrack } from "svelte";
  import { createClient, type Photo } from "@pinedaview/protocol";
  import { FONTS } from "@pinedaview/tokens";
  import {
    PHOTO_CLOCK_FONTS,
    type PhotoClockSettings,
  } from "../lib/clockface.svelte";
  import { formatClock, formatTemp, parseClockTime } from "../lib/format";
  import { frameX } from "../lib/frame.svelte";
  import {
    bake,
    bakePanel,
    bakeShape,
    findLight,
    LOOKS,
    type Figures,
    type Light,
    type LookName,
    type RGB,
    type Shape,
  } from "../lib/glass";
  import { photoInks } from "../lib/clockInk";
  import { coverCrop, GlassDigits, type SlotView } from "../lib/glassDigits";
  import { pickNext, recentLimit } from "../lib/photoPick";
  import { photoShare } from "../lib/photoShare.svelte";
  import { platform } from "../lib/platform.svelte";
  import { readLocal, writeLocal } from "../lib/storage";
  import {
    SWIPE_MS,
    swipeEasing,
    swipeProgress,
    swipeTimeAt,
  } from "../lib/swipeCurve";
  import { effectiveTier, motion } from "../lib/tier.svelte";
  import { glyphFor } from "../components/WeatherGlyph.svelte";
  import type { WeatherData } from "./types";

  let {
    parts,
    font = null,
    tint = null,
    settings,
    holdMs = 30_000,
    weather = null,
    units = "imperial",
    avoid = null,
    panel = null,
    share = true,
    paused = false,
  }: {
    parts: ReturnType<typeof formatClock>;
    /** The phone's Clock only font (a FONTS id); null keeps this screen's
        own photo clock font. */
    font?: string | null;
    /** The glass tint: #rrggbb, "auto" (each photo's own, worked out on
        the server), or null for clear icy glass. */
    tint?: string | null;
    /** Font, size and glass: the screen's own, or Settings' draft while
        it's previewing them. */
    settings: PhotoClockSettings;
    /** How long each photo stays before the next swipes in. */
    holdMs?: number;
    weather?: WeatherData | null;
    units?: string | null;
    /** A corner something else is using (the music card): the date
        picks among the other three. */
    avoid?: "tl" | "tr" | "bl" | "br" | null;
    /** A card over the clock (the music card) to put the same live glass
        behind: its box, rounding, fade and resizes are followed. The card
        is told by a `data-live-glass` attribute while the glass is on, so
        it can drop its CSS stand-in. */
    panel?: HTMLElement | null;
    /** Trade the photo on screen with the Photo card (lib/photoShare);
        off for Settings' preview. */
    share?: boolean;
    /** Hold the current photo (Alternate, while it hands over to the cards,
        so the photo doesn't change under the move). */
    paused?: boolean;
  } = $props();

  const RESUME_KEY = "pineda.photoClockResume";
  /** The photos shown lately, newest last (lib/photoPick). */
  const RECENT_KEY = "pineda.photoClockRecent";
  const FADE_MS = 1200;
  const FADE_HANDOFF_MS = 600;
  const SWIPE_EASE = swipeEasing();
  /** When the next photo covers half the screen: the time's frost and its
      tuck behind the cutout switch over to it then. */
  const HANDOFF_MS = Math.round(SWIPE_MS * swipeTimeAt(0.5));
  const RELIST_MS = 5 * 60_000;

  const client = createClient(import.meta.env.VITE_API_URL ?? "");

  let photos = $state<Photo[]>([]);
  let index = $state(0);
  let top = $state(0);
  /** The slot the time is dressed for (its frost and whether it tucks
      behind the cutout): it follows `top` halfway through the swipe. */
  let face = $state(0);
  /** The slot parked off the right edge, about to swipe in. */
  let entering = $state(-1);
  /** The slot swiping out: it keeps its drift until it's gone, rather than
      snapping back to where its drift began as it leaves. */
  let leaving = $state(-1);
  let sources = $state<[string, string]>(["", ""]);
  let subjects = $state<[string, string]>(["", ""]);
  let rots = $state<[number, number]>([0, 0]);
  /** Each slot's photo's own tint, for "auto". */
  let tints = $state<[string, string]>(["", ""]);
  /** Each slot's photo's dominant colours, for the colour looks. */
  let palettes = $state<[string[], string[]]>([[], []]);
  /** Liquid, frosted and crystal are glass, drawn live or baked; flat and
      the colour looks are CSS alone. */
  const isGlass = (g: string): g is LookName =>
    g === "liquid" || g === "frosted" || g === "crystal";
  /** The glass's look (the CSS looks have none of their own). */
  const look = $derived(
    LOOKS[isGlass(settings.glass) ? settings.glass : "liquid"],
  );
  /** A colour look (lib/clockInk): mesh, match, opposite, chrome, print or
      neon; null for glass and flat. */
  const inkLook = $derived(
    isGlass(settings.glass) || settings.glass === "flat"
      ? null
      : settings.glass,
  );
  /** Its inks, from the photo the time is dressed for; a picked tint wins. */
  const inks = $derived(
    inkLook
      ? photoInks(
          tint && tint !== "auto" ? tint : tints[face] || null,
          palettes[face],
        )
      : null,
  );
  const glassTint = $derived(
    (tint === "auto" ? tints[face] : tint) || undefined,
  );
  let masks = $state<[Mask | null, Mask | null]>([null, null]);
  /** A tiny copy of each slot's photo; scaled up, it's the frost the glass
      figures are filled with. */
  let frosts = $state<[string, string]>(["", ""]);
  let swapping = false;
  /** Mid-swipe: the date steps out, and bakes wait until the photo lands
      (a bake holds the main thread for a good part of a second on a Pi). */
  let swiping = $state(false);
  let landed: Promise<void> = Promise.resolve();
  let land = (): void => {};
  /** The figures as text. Multi-line when stacked (hours over minutes),
      row with colon otherwise. */
  const text = $derived(
    settings.layout === "stack"
      ? `${parts.hh}\n${parts.mm}`
      : `${parts.hh}:${parts.mm}`,
  );

  const tempStr = $derived(
    settings.weather && weather?.current?.tempC != null
      ? formatTemp(
          weather.current.tempC,
          units === "metric" ? "metric" : "imperial",
        )
      : "",
  );
  const glyphStr = $derived(
    settings.weather && weather?.current?.code
      ? glyphFor(weather.current.code, weather.current.isDay ?? true)
      : "",
  );
  const dateLabel = $derived(
    tempStr && glyphStr ? `${parts.date} · ${tempStr} ${glyphStr}` : parts.date,
  );

  function formatWhisper(p: Photo | undefined): string {
    if (!p) return "";
    if (p.taken_at) {
      const date = new Date(p.taken_at * 1000);
      if (!isNaN(date.getTime())) {
        const now = new Date();
        const years = now.getFullYear() - date.getFullYear();
        const monthYear = date.toLocaleDateString(undefined, {
          month: "long",
          year: "numeric",
        });
        if (years >= 1) {
          return `${monthYear} · ${years} yr${years === 1 ? "" : "s"} ago`;
        }
        return date.toLocaleDateString(undefined, {
          month: "long",
          day: "numeric",
          year: "numeric",
        });
      }
    }
    return "";
  }

  let whisperActive = $state(false);
  let whisperTimer: ReturnType<typeof setTimeout> | null = null;
  let whisperHideTimer: ReturnType<typeof setTimeout> | null = null;
  const currentPhoto = $derived(photos[index]);
  const whisperText = $derived(
    settings.whisper ? formatWhisper(currentPhoto) : "",
  );

  function triggerWhisper(): void {
    if (whisperTimer) clearTimeout(whisperTimer);
    if (whisperHideTimer) clearTimeout(whisperHideTimer);
    whisperActive = false;
    if (!settings.whisper || !formatWhisper(photos[index])) return;
    whisperTimer = setTimeout(() => {
      whisperActive = true;
      whisperHideTimer = setTimeout(() => {
        whisperActive = false;
      }, 5000);
    }, 3000);
  }

  $effect(() => {
    if (settings.whisper) {
      triggerWhisper();
    } else {
      whisperActive = false;
    }
    return () => {
      if (whisperTimer) clearTimeout(whisperTimer);
      if (whisperHideTimer) clearTimeout(whisperHideTimer);
    };
  });

  /** A Live Photo's clip, played when its photo lands, the time in front
      and the cutout away (it wouldn't match the moving subject); then it
      fades back to the still — the clip's middle frame — the subject steps
      in front of the time, and a moment later it plays again. */
  let clip = $state("");
  let moving = $state(false);
  /** Frames are coming: fade the clip in over its still. */
  let started = $state(false);
  let clipEl = $state<HTMLVideoElement>();
  const SETTLE_MS = 1500;

  function clipEnded(): void {
    moving = false;
    const url = clip;
    setTimeout(() => {
      if (clip !== url || !clipEl) return;
      clipEl.currentTime = 0;
      moving = true;
      void clipEl.play().catch(() => (moving = false));
    }, SETTLE_MS);
  }

  function playClip(p: Photo | undefined): void {
    const url =
      p?.motion &&
      !motion.reduced &&
      !motion.batterySaver &&
      effectiveTier() !== "lite"
        ? client.photoMotionUrl(p.name)
        : "";
    clip = url;
    started = false;
    moving = Boolean(url);
    // A clip that never starts mustn't keep the subject away for good.
    setTimeout(() => {
      if (clip === url && !started) moving = false;
    }, 5000);
  }

  let root = $state<HTMLDivElement>();
  let width = $state(0);
  let height = $state(0);
  /** What a picture frame hides on each side, px: everything that's read
      stays inside it, while the photos still run under the frame's lip. */
  const fx = $derived(frameX(width));

  /** A coarse alpha mask of a cutout: where the subject is, and the top of
      it (as a fraction of the photo's height). */
  interface Mask {
    w: number;
    h: number;
    alpha: Uint8Array;
    top: number;
  }

  const MASK_W = 96;
  /** Where the subject's top should land, as a fraction of the screen
      height: low enough to leave the time some sky, high enough that heads
      overlap the figures. */
  const HEAD_AT = 0.24;
  /** Past either share hidden, the time comes to the front. */
  const MAX_HIDDEN = 0.25;
  const MAX_HIDDEN_DIGIT = 0.4;

  /** The image at `url` drawn into a canvas `w` px wide, or null if it
      won't decode. */
  async function draw(url: string, w: number) {
    const img = new Image();
    img.src = url;
    try {
      await img.decode();
    } catch {
      return null;
    }
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = Math.max(
      1,
      Math.round((w * img.naturalHeight) / img.naturalWidth),
    );
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx?.drawImage(img, 0, 0, w, canvas.height);
    return ctx && canvas;
  }

  async function readMask(url: string): Promise<Mask | null> {
    const canvas = await draw(url, MASK_W);
    if (!canvas) return null;
    const { width: w, height: h } = canvas;
    const rgba = canvas.getContext("2d")!.getImageData(0, 0, w, h).data;
    const alpha = new Uint8Array(w * h);
    let top = 1;
    for (let y = 0; y < h; y++) {
      let row = 0;
      for (let x = 0; x < w; x++) {
        const on = (rgba[(y * w + x) * 4 + 3] ?? 0) > 127 ? 1 : 0;
        alpha[y * w + x] = on;
        row += on;
      }
      if (top === 1 && row > w * 0.02) top = y / h;
    }
    return { w, h, alpha, top };
  }

  /** object-fit: cover's scale and offset for a mask in this box, with the
      crop slid down or up so the subject's top sits at HEAD_AT. */
  function fit(m: Mask) {
    const scale = Math.max(width / m.w, height / m.h);
    const spare = m.h * scale - height; // px cropped off vertically
    const want = m.top * m.h * scale - HEAD_AT * height;
    const dy = spare > 0 ? Math.min(Math.max(want, 0), spare) : spare / 2;
    return {
      scale,
      x: (width - m.w * scale) / 2,
      y: -dy,
      pos: spare > 0 ? `50% ${(dy / spare) * 100}%` : "50% 50%",
    };
  }

  function position(i: number): string {
    const m = masks[i];
    return m && !rots[i] && width && height ? fit(m).pos : "50% 50%";
  }

  /** How much of the time the cutout would hide: the share of the whole
      figures' box, and of the worst-covered character in it. One digit
      gone (a shoe over the "3") makes the time unreadable even when the
      box as a whole is mostly clear. */
  let hidden = $state({ all: 1, worst: 1 });
  $effect(() => {
    const m = masks[face];
    const chars = text;
    void settings.size;
    void family;
    void digitFit;
    void shift;
    if (!m || rots[face] || !root || !width || !height) {
      hidden = { all: 1, worst: 1 };
      return;
    }
    const box = root;
    let live = true;
    void document.fonts.ready.then(() => {
      const digits = box.querySelector(".clock-layer .digits");
      if (!live || !digits) return;
      const r = digits.getBoundingClientRect();
      const o = box.getBoundingClientRect();
      const { scale, x, y } = fit(m);
      const isStack = chars.includes("\n");
      const cells = isStack ? 4 : chars.length;
      const on = new Array<number>(cells).fill(0);
      const all = new Array<number>(cells).fill(0);
      const step = Math.max(8, Math.round(scale));
      const midY = (r.top + r.bottom) / 2 - o.top;
      for (let cy = r.top - o.top; cy < r.bottom - o.top; cy += step) {
        for (let cx = r.left - o.left; cx < r.right - o.left; cx += step) {
          let cell = 0;
          if (isStack) {
            const row = cy < midY ? 0 : 1;
            const col = Math.min(
              1,
              Math.floor(((cx - (r.left - o.left)) / r.width) * 2),
            );
            cell = row * 2 + col;
          } else {
            cell = Math.min(
              cells - 1,
              Math.floor(((cx - (r.left - o.left)) / r.width) * cells),
            );
          }
          const mx = Math.floor((cx - x) / scale);
          const my = Math.floor((cy - y) / scale);
          all[cell] = (all[cell] ?? 0) + 1;
          if (mx >= 0 && my >= 0 && mx < m.w && my < m.h)
            on[cell] = (on[cell] ?? 0) + (m.alpha[my * m.w + mx] ?? 0);
        }
      }
      const total = all.reduce((a, b) => a + b, 0);
      let worst = 0;
      if (isStack) {
        all.forEach((cnt, i) => {
          if (cnt) worst = Math.max(worst, (on[i] ?? 0) / cnt);
        });
      } else {
        chars.split("").forEach((ch, i) => {
          if (ch !== ":" && all[i])
            worst = Math.max(worst, (on[i] ?? 0) / all[i]!);
        });
      }
      hidden = {
        all: total ? on.reduce((a, b) => a + b, 0) / total : 1,
        worst,
      };
    });
    return () => {
      live = false;
    };
  });

  /** The share of a screen box the subject covers, sampled every 8 px. */
  function covered(
    m: Mask,
    left: number,
    topY: number,
    bw: number,
    bh: number,
    step = 8,
  ) {
    const { scale, x, y } = fit(m);
    let on = 0;
    let all = 0;
    for (let cy = topY; cy < topY + bh; cy += step) {
      for (let cx = left; cx < left + bw; cx += step) {
        const mx = Math.floor((cx - x) / scale);
        const my = Math.floor((cy - y) / scale);
        all++;
        if (mx >= 0 && my >= 0 && mx < m.w && my < m.h)
          on += m.alpha[my * m.w + mx] ?? 0;
      }
    }
    return all ? on / all : 0;
  }

  type Corner = "tl" | "tr";
  /** The corner for the date: top-left or top-right in the header, picking
      whichever leaves the photo's subject clearest (or opposite the time
      when it's off centre). */
  const corner = $derived.by((): Corner => {
    const m = masks[face];
    const taken =
      spots[face] === "left" ? "tl" : spots[face] === "right" ? "tr" : null;
    const free = (c: Corner) => c !== avoid && c !== taken;
    if (taken === "tl" && free("tr")) return "tr";
    if (taken === "tr" && free("tl")) return "tl";
    if (!m || rots[face] || !width || !height) return free("tl") ? "tl" : "tr";
    const bw = width * 0.3;
    const bh = height * 0.14;
    const tlCover = covered(m, fx, 0, bw, bh, 16);
    const trCover = covered(m, width - fx - bw, 0, bw, bh, 16);
    if (!free("tl")) return "tr";
    if (!free("tr")) return "tl";
    return trCover < tlCover - 0.05 ? "tr" : "tl";
  });

  /** A slot's photo as a small grid of brightness (0–1), cropped and laid
      out as the screen shows it: how bright it is behind the glass, and
      where it's calm enough for the time. */
  interface Luma {
    w: number;
    h: number;
    L: Float32Array;
  }
  const LUMA_W = 96;
  let lumas = $state.raw<[Luma | null, Luma | null]>([null, null]);

  async function readLuma(i: 0 | 1): Promise<Luma | null> {
    const url = sources[i];
    if (!url || rots[i] || !width || !height) return null;
    const photo = await photoFor(url);
    if (!photo) return null;
    const [px = 0.5, py = 0.5] = position(i)
      .split(" ")
      .map((v) => parseFloat(v) / 100);
    const c = coverCrop(photo.img, width, height, [px, py], 0, LUMA_W / width);
    let rgba: Uint8ClampedArray;
    try {
      rgba = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
    } catch {
      return null;
    }
    const L = new Float32Array(c.width * c.height);
    for (let k = 0; k < L.length; k++)
      L[k] =
        (0.2126 * rgba[k * 4]! +
          0.7152 * rgba[k * 4 + 1]! +
          0.0722 * rgba[k * 4 + 2]!) /
        255;
    return { w: c.width, h: c.height, L };
  }

  /** A screen box's mean brightness, and how busy it is: the mean step
      between neighbouring cells, which is low for sky and wall and high
      for leaves, crowds and brickwork. */
  function lumaIn(
    lm: Luma,
    left: number,
    topY: number,
    bw: number,
    bh: number,
  ) {
    const sx = lm.w / width;
    const sy = lm.h / height;
    const x0 = Math.min(lm.w - 1, Math.max(0, Math.floor(left * sx)));
    const y0 = Math.min(lm.h - 1, Math.max(0, Math.floor(topY * sy)));
    const x1 = Math.min(lm.w, Math.max(x0 + 1, Math.ceil((left + bw) * sx)));
    const y1 = Math.min(lm.h, Math.max(y0 + 1, Math.ceil((topY + bh) * sy)));
    let sum = 0;
    let busy = 0;
    for (let y = y0; y < y1; y++) {
      for (let x = x0; x < x1; x++) {
        const v = lm.L[y * lm.w + x]!;
        sum += v;
        busy +=
          Math.abs(v - lm.L[y * lm.w + Math.min(x + 1, lm.w - 1)]!) +
          Math.abs(v - lm.L[Math.min(y + 1, lm.h - 1) * lm.w + x]!);
      }
    }
    const n = (x1 - x0) * (y1 - y0);
    return { luma: sum / n, busy: busy / n };
  }

  /** Where the time sits across the top: the middle, unless a side of
      this photo is clearly calmer (sky, not branches) or the subject would
      stand over most of the middle. */
  type Spot = "left" | "centre" | "right";
  let spots = $state<[Spot, Spot]>(["centre", "centre"]);
  /** The figures' box at the centre spot, as drawn (scaled). */
  let fig = $state<{ w: number; h: number; top: number } | null>(null);
  /** The time's gap to the screen's side at the left or right spot. */
  const TIME_EDGE = 0.06;
  /** How far the figures can move off the middle and stay clear of the
      side (and the frame), px. */
  const room = (f: { w: number }): number =>
    width / 2 - fx - width * TIME_EDGE - f.w / 2;

  function dxFor(spot: Spot | undefined): number {
    if (!spot || spot === "centre" || !fig) return 0;
    const reach = Math.max(0, room(fig));
    return spot === "left" ? -reach : reach;
  }
  /** The face's spot as an offset from the middle, px. */
  const shift = $derived(dxFor(spots[face]));

  /** How much of a spot's time figures a cutout would hide: mean and worst digit cell. */
  function spotCutoutCover(
    m: Mask,
    left: number,
    topY: number,
    bw: number,
    bh: number,
  ): { all: number; worst: number } {
    const { scale, x, y } = fit(m);
    const chars = text;
    const isStack = chars.includes("\n");
    const cells = isStack ? 4 : chars.length;
    const on = new Array<number>(cells).fill(0);
    const all = new Array<number>(cells).fill(0);
    const step = Math.max(8, Math.round(scale));
    const midY = topY + bh / 2;
    for (let cy = topY; cy < topY + bh; cy += step) {
      for (let cx = left; cx < left + bw; cx += step) {
        let cell = 0;
        if (isStack) {
          const row = cy < midY ? 0 : 1;
          const col = Math.min(1, Math.floor(((cx - left) / bw) * 2));
          cell = row * 2 + col;
        } else {
          cell = Math.min(cells - 1, Math.floor(((cx - left) / bw) * cells));
        }
        const mx = Math.floor((cx - x) / scale);
        const my = Math.floor((cy - y) / scale);
        all[cell] = (all[cell] ?? 0) + 1;
        if (mx >= 0 && my >= 0 && mx < m.w && my < m.h)
          on[cell] = (on[cell] ?? 0) + (m.alpha[my * m.w + mx] ?? 0);
      }
    }
    const total = all.reduce((a, b) => a + b, 0);
    let worst = 0;
    if (isStack) {
      all.forEach((cnt, i) => {
        if (cnt) worst = Math.max(worst, (on[i] ?? 0) / cnt);
      });
    } else {
      chars.split("").forEach((ch, i) => {
        if (ch !== ":" && all[i])
          worst = Math.max(worst, (on[i] ?? 0) / all[i]!);
      });
    }
    return {
      all: total ? on.reduce((a, b) => a + b, 0) / total : 0,
      worst,
    };
  }

  function chooseSpot(i: 0 | 1): Spot {
    const lm = lumas[i];
    const f = fig;
    // Too little room either side to be worth a move.
    if (!lm || !f || !width || room(f) < width * 0.12) return "centre";
    const m = settings.depth && hasCutout(i) ? masks[i] : null;
    const score = (s: Spot): number => {
      const left = width / 2 + dxFor(s) - f.w / 2;
      const { busy } = lumaIn(lm, left, f.top, f.w, f.h);
      let penalty = 0;
      if (m) {
        const cover = spotCutoutCover(m, left, f.top, f.w, f.h);
        if (cover.worst >= MAX_HIDDEN_DIGIT) {
          penalty += 2.0 * cover.worst;
        } else if (cover.worst > 0.1) {
          penalty += 0.8 * cover.worst;
        }
        if (cover.all > MAX_HIDDEN) {
          penalty += 1.0 * (cover.all - MAX_HIDDEN);
        }
      }
      return busy + penalty;
    };
    const mid = score("centre");
    const [side, best] = (["left", "right"] as const)
      .map((s) => [s, score(s)] as const)
      .reduce((a, b) => (b[1] < a[1] ? b : a));
    return best < mid * SPOT_GAIN && mid - best > SPOT_MIN ? side : "centre";
  }
  const SPOT_GAIN = 0.75;
  const SPOT_MIN = 0.015;

  /** Read slot i's brightness and pick its spot, once its crop is known. */
  async function readSlot(i: 0 | 1): Promise<void> {
    const url = sources[i];
    const lm = await readLuma(i);
    await document.fonts.ready; // the figures measured (fig) first
    if (sources[i] !== url) return;
    lumas = i === 0 ? [lm, lumas[1]] : [lumas[0], lm];
    spots[i] = chooseSpot(i);
  }

  /** Mid-swipe, while the time fades out of one spot and into another. */
  let relocating = $state(false);

  /** A 40 px wide copy of the photo as a data URL: the browser's smooth
      upscale of it is a cheap, even blur. "" if it won't decode. */
  async function readFrost(url: string): Promise<string> {
    return (await draw(url, 40))?.toDataURL("image/jpeg", 0.8) ?? "";
  }

  const frostCache = new Map<string, string>();
  async function getFrost(
    url: string,
    img?: HTMLImageElement,
  ): Promise<string> {
    if (!url) return "";
    const cached = frostCache.get(url);
    if (cached) return cached;
    let frost = "";
    if (img && img.naturalWidth && img.naturalHeight) {
      const w = 40;
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = Math.max(
        1,
        Math.round((w * img.naturalHeight) / img.naturalWidth),
      );
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (ctx) {
        ctx.drawImage(img, 0, 0, w, canvas.height);
        frost = canvas.toDataURL("image/jpeg", 0.8);
      }
    } else {
      frost = await readFrost(url);
    }
    if (frost) {
      frostCache.set(url, frost);
      if (frostCache.size > 20)
        frostCache.delete(frostCache.keys().next().value!);
    }
    return frost;
  }

  async function loadFrost(
    i: number,
    url: string,
    img?: HTMLImageElement,
  ): Promise<void> {
    const frost = await getFrost(url, img);
    if (sources[i] === url) frosts[i] = frost;
  }

  const maskCache = new Map<string, Promise<Mask | null>>();
  function maskFor(url: string): Promise<Mask | null> {
    if (!url) return Promise.resolve(null);
    let p = maskCache.get(url);
    if (!p) {
      p = readMask(url);
      maskCache.set(url, p);
      if (maskCache.size > 20) maskCache.delete(maskCache.keys().next().value!);
    }
    return p;
  }

  /** Load slot i's cutout mask; ignored if the slot has moved on. */
  async function loadMask(i: number, url: string): Promise<void> {
    const m = url ? await maskFor(url) : null;
    if (subjects[i] === url) masks[i] = m;
  }

  const family = $derived(
    FONTS.find((f) => f.id === font)?.stack ??
      (
        PHOTO_CLOCK_FONTS.find((f) => f.id === settings.font) ??
        PHOTO_CLOCK_FONTS[0]
      )?.family ??
      "sans-serif",
  );

  // The glass, baked into a canvas over the (then invisible) DOM figures
  // whenever the minute, the photo or a setting changes. Not for flat
  // glass or a hand-rotated photo; until it's ready, the CSS glass shows.
  // One canvas per slot, so the next photo's glass is baked before it
  // swipes in and the handoff halfway is only a switch.
  type GlassBox = { left: number; top: number; width: number; height: number };
  let glassEls = $state<[HTMLCanvasElement | null, HTMLCanvasElement | null]>([
    null,
    null,
  ]);
  let glassBoxes = $state<[GlassBox | null, GlassBox | null]>([null, null]);
  /** The slot being readied to swipe in; it bakes as well as the face. */
  let pending = $state(-1);
  /** Each slot's latest bake, for step() to wait on before swiping. */
  const baked: [Promise<void>, Promise<void>] = [
    Promise.resolve(),
    Promise.resolve(),
  ];
  const seen = new Map<
    string,
    Promise<{ img: HTMLImageElement; light: Light } | null>
  >();
  function photoFor(url: string) {
    let p = seen.get(url);
    if (!p) {
      const img = new Image();
      img.src = url;
      p = img.decode().then(
        () => ({ img, light: findLight(img, url) }),
        () => null,
      );
      seen.set(url, p);
      if (seen.size > 12) seen.delete(seen.keys().next().value!);
    }
    return p;
  }
  const bakes = [0, 0];
  /** Booleans, so a slot re-bakes only when it starts being needed, not
      whenever `face` or `pending` move. */
  const wanted0 = $derived(face === 0 || pending === 0);
  const wanted1 = $derived(face === 1 || pending === 1);
  function bakeSlot(i: 0 | 1): void {
    const url = sources[i];
    const chars = text;
    const glass = settings.glass;
    const lk = look;
    const milk = settings.opacity;
    const hex = (tint === "auto" ? tints[i] : tint) || undefined;
    const fitScale = digitFit;
    void family;
    void settings.size;
    const box = root;
    const canvas = glassEls[i];
    const pos = position(i);
    const needed = i === 0 ? wanted0 : wanted1;
    const dx = dxFor(spots[i]);
    const lm = lumas[i];
    if (live) {
      glassBoxes[i] = null; // the live glass has it
      return;
    }
    if (
      !needed ||
      !url ||
      !isGlass(glass) ||
      rots[i] ||
      !box ||
      !canvas ||
      !width ||
      !height
    ) {
      if (!needed) return; // keep what it has; it's off screen
      glassBoxes[i] = null;
      return;
    }
    const id = ++bakes[i]!;
    baked[i] = Promise.all([photoFor(url), document.fonts.ready]).then(
      async ([photo]) => {
        // Not while a photo is moving: wait for it to land. Then a frame's
        // grace: dragging the opacity slider asks for many bakes, and only
        // the last one in each frame needs doing.
        if (swiping) await landed;
        await new Promise((r) => requestAnimationFrame(r));
        const el = box.querySelector<HTMLElement>(".clock-layer .digits");
        if (id !== bakes[i] || !photo || !el || live) return;
        const { img, light } = photo;
        const scale = Math.max(
          width / img.naturalWidth,
          height / img.naturalHeight,
        );
        const [px, py] = pos.split(" ").map((v) => parseFloat(v) / 100);
        const r = el.getBoundingClientRect();
        const o = box.getBoundingClientRect();
        const cs = getComputedStyle(el);
        const size = parseFloat(cs.fontSize) * fitScale;
        const pad = size * 0.3;
        // The figures stand at the face's spot; this slot's may differ.
        const moved = dx - shift;
        const next = {
          left: r.left - o.left - pad + moved,
          top: r.top - o.top - pad,
          width: r.width + pad * 2,
          height: r.height + pad * 2,
        };
        const ok = bake({
          canvas,
          img,
          scale,
          x: (width - img.naturalWidth * scale) * (px ?? 0.5),
          y: (height - img.naturalHeight * scale) * (py ?? 0.5),
          ...next,
          cx: r.left - o.left + r.width / 2 + moved,
          cy: r.top - o.top + r.height / 2,
          text: chars,
          font: (n) =>
            `${cs.fontStyle} ${cs.fontWeight} ${n}px ${cs.fontFamily}`,
          size,
          spacing: (parseFloat(cs.letterSpacing) || 0) * fitScale,
          look: lk,
          milk,
          tint: hex
            ? ([1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [
                number,
                number,
                number,
              ])
            : null,
          light,
          glare: lm
            ? lumaIn(lm, next.left, next.top, next.width, next.height).luma
            : 0.5,
        });
        glassBoxes[i] = ok ? next : null;
      },
    );
  }
  // The cutout's drift runs on its photo's clock. Each starts when its
  // image mounts, and a cutout that turns up a moment after its photo
  // would otherwise trail it for the whole hold, the person doubled.
  $effect(() => {
    const i = top;
    void subjects[i];
    void sources[i];
    void settings.drift;
    void settings.depth;
    let live = true;
    void tick().then(() =>
      requestAnimationFrame(() => {
        if (!live || !root) return;
        const drift = (sel: string) =>
          root
            ?.querySelector<HTMLElement>(`img.${sel}[data-slot="${i}"]`)
            ?.getAnimations()
            .find((a) => a instanceof CSSAnimation);
        const photo = drift("photo-layer");
        const cut = drift("cutout-layer");
        if (photo && cut && photo.currentTime !== null)
          cut.currentTime = photo.currentTime;
      }),
    );
    return () => {
      live = false;
    };
  });
  $effect(() => bakeSlot(0));
  $effect(() => bakeSlot(1));

  // The live glass (lib/glassDigits.ts): the figures' shape baked once a
  // minute, the photos bent through it on the GPU every frame they move,
  // so the glass travels with a swipe instead of switching halfway. The
  // next minute's shape is baked ahead, so the minute turns without a
  // wait. Without WebGL, the per-slot bakes above do the job.
  let liveEl = $state<HTMLCanvasElement | null>(null);
  let live = $state(false);
  let gd: GlassDigits | null = null;
  let liveBox = $state<GlassBox | null>(null);
  /** Each slot's photo uploaded for its current source (and where its
      light sits in the photo's box, CSS px). */
  let slotReady = $state<[boolean, boolean]>([false, false]);
  const slotUrls = ["", ""];
  const slotLights: [
    { x: number; y: number; rgb: RGB } | null,
    { x: number; y: number; rgb: RGB } | null,
  ] = [null, null];
  /** The figures the live shape was baked for (and its look), and next
      minute's. */
  let liveSpec: Figures | null = null;
  let liveLook: typeof look | null = null;
  let nextShape: {
    spec: Figures;
    shape: Shape;
    look: typeof look;
  } | null = null;
  /** CPU work on the shape; a swipe waits for it rather than stutter. */
  let shapeWork: Promise<void> = Promise.resolve();
  let shapeId = 0;
  const preps = [0, 0];
  const liveOn = $derived(
    live && liveBox != null && slotReady[face] && isGlass(settings.glass),
  );

  $effect(() => {
    const el = liveEl;
    if (!el) return;
    const r = GlassDigits.create(el);
    if (!r) return;
    gd = r;
    live = true;
    const lost = (e: Event): void => {
      e.preventDefault();
      gd = null;
      live = false;
      liveBox = null;
    };
    el.addEventListener("webglcontextlost", lost);
    return () => {
      el.removeEventListener("webglcontextlost", lost);
      r.dispose();
      gd = null;
      live = false;
    };
  });

  const nextFrame = (): Promise<void> =>
    new Promise((r) => requestAnimationFrame(() => r()));

  const hexRgb = (hex: string | undefined): RGB | null =>
    hex
      ? ([1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as RGB)
      : null;

  /** Upload slot i's photo, cropped and blurred as the glass sees it. */
  function prepSlot(i: 0 | 1): void {
    const url = sources[i];
    const glass = settings.glass;
    const blur = look.blur;
    const pos = position(i);
    const w = width;
    const h = height;
    const needed = i === 0 ? wanted0 : wanted1;
    if (!live || !needed) return;
    if (!url || !isGlass(glass) || !w || !h) {
      slotReady[i] = false;
      return;
    }
    if (slotUrls[i] !== url) slotReady[i] = false;
    const id = ++preps[i]!;
    baked[i] = photoFor(url).then(async (photo) => {
      if (swiping) await landed;
      await nextFrame();
      if (id !== preps[i] || !photo || !gd) return;
      const { img, light } = photo;
      const [px = 0.5, py = 0.5] = pos
        .split(" ")
        .map((v) => parseFloat(v) / 100);
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      // Liquid glass sees the photo nearly sharp; frosted, through a blur
      // that hides a half-size copy.
      const res = Math.min(dpr, 2048 / Math.max(w, h)) * (blur >= 8 ? 0.5 : 1);
      const crop = coverCrop(img, w, h, [px, py], blur, res);
      gd.setPhoto(i, crop);
      pd?.setPhoto(i, crop);
      const scale = Math.max(w / img.naturalWidth, h / img.naturalHeight);
      slotLights[i] = {
        x:
          (w - img.naturalWidth * scale) * px +
          light.u * img.naturalWidth * scale,
        y:
          (h - img.naturalHeight * scale) * py +
          light.v * img.naturalHeight * scale,
        rgb: light.rgb,
      };
      slotUrls[i] = url;
      slotReady[i] = true;
      kick();
    });
  }
  $effect(() => prepSlot(0));
  $effect(() => prepSlot(1));

  /** The figures as laid out now: the box the glass covers and its font. */
  function measure(chars: string, fitScale: number): Figures | null {
    const box = root;
    const el = box?.querySelector<HTMLElement>(".clock-layer .digits");
    if (!box || !el) return null;
    const r = el.getBoundingClientRect();
    const o = box.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const size = parseFloat(cs.fontSize) * fitScale;
    const pad = size * 0.3;
    return {
      left: r.left - o.left - pad,
      top: r.top - o.top - pad,
      width: r.width + pad * 2,
      height: r.height + pad * 2,
      cx: r.left - o.left + r.width / 2,
      cy: r.top - o.top + r.height / 2,
      text: chars,
      font: (n) => `${cs.fontStyle} ${cs.fontWeight} ${n}px ${cs.fontFamily}`,
      size,
      spacing: (parseFloat(cs.letterSpacing) || 0) * fitScale,
    };
  }

  /** The same shape, wherever it stands: a shape baked for one can be
      drawn for the other. */
  const sameFigures = (a: Figures, b: Figures): boolean =>
    Math.abs(a.cx - a.left - (b.cx - b.left)) < 0.5 &&
    Math.abs(a.cy - a.top - (b.cy - b.top)) < 0.5 &&
    Math.abs(a.width - b.width) < 0.5 &&
    Math.abs(a.height - b.height) < 0.5 &&
    a.size === b.size &&
    a.spacing === b.spacing &&
    a.font(1) === b.font(1);

  function applyShape(spec: Figures, shape: Shape | null): void {
    if (!gd || !liveEl) return;
    // The minute turning: the old figures dissolve over the new.
    if (shape && liveSpec && liveSpec.text !== spec.text) ghost();
    if (shape) gd.setShape(liveEl, shape);
    liveSpec = spec;
    liveBox = {
      left: spec.left,
      top: spec.top,
      width: spec.width,
      height: spec.height,
    };
    // Now, not next frame: a resized canvas is blank until drawn.
    render(true);
    schedulePrebake();
  }

  /** A copy of the glass as it stands, faded out over what replaces it. The
      figures that don't change are the same under it, so they hold still;
      only the digit that turns crossfades. */
  let ghostEl = $state<HTMLCanvasElement | null>(null);
  const GHOST_MS = 700;
  function ghost(): void {
    const el = ghostEl;
    const box = liveBox;
    if (!el || !liveEl || !box || !liveOn || swiping || motion.reduced) return;
    // Drawn again now, so the WebGL canvas still holds it to copy.
    render(true);
    el.width = liveEl.width;
    el.height = liveEl.height;
    const cx = el.getContext("2d");
    if (!cx) return;
    cx.drawImage(liveEl, 0, 0);
    el.style.left = `${box.left}px`;
    el.style.top = `${box.top}px`;
    el.style.width = `${box.width}px`;
    el.style.height = `${box.height}px`;
    el.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: GHOST_MS,
      easing: "ease-in-out",
    });
  }

  $effect(() => {
    const chars = text;
    void family;
    void settings.size;
    void settings.layout;
    const fitScale = digitFit;
    const glass = settings.glass;
    const lk = look;
    void shift;
    if (!live || !liveEl || !root || !width || !height) return;
    if (!isGlass(glass)) {
      liveBox = null;
      return;
    }
    // Only moved to another spot: the shape it has, drawn there.
    const was = liveSpec;
    if (was && gd?.ready && liveLook === lk && was.text === chars) {
      const spec = measure(chars, fitScale);
      if (spec && sameFigures(spec, was)) {
        untrack(() => applyShape(spec, null));
        return;
      }
    }
    const id = ++shapeId;
    // Baked ahead for this minute and laid out the same: on screen in the
    // same frame as the new figures.
    const ahead = nextShape;
    nextShape = null;
    if (ahead && ahead.spec.text === chars && ahead.look === lk) {
      const spec = measure(chars, fitScale);
      if (spec && sameFigures(spec, ahead.spec)) {
        liveLook = lk;
        untrack(() => applyShape(spec, ahead.shape));
        return;
      }
    }
    shapeWork = document.fonts.ready.then(async () => {
      if (swiping) await landed;
      await nextFrame();
      if (id !== shapeId) return;
      const spec = measure(chars, fitScale);
      const shape = spec && bakeShape(spec, lk);
      if (!spec || !shape) {
        liveBox = null;
        return;
      }
      liveLook = lk;
      applyShape(spec, shape);
    });
  });

  // Next minute's shape, baked a little after this one lands. Only when
  // its figures fill the same box (a wider hour, 9:59 → 10:00, is baked
  // when it comes) and the clock is the real one, not a preview's.
  let prebakeTimer: ReturnType<typeof setTimeout> | undefined;
  function schedulePrebake(): void {
    clearTimeout(prebakeTimer);
    prebakeTimer = setTimeout(() => {
      const spec = liveSpec;
      if (!spec || !gd) return;
      const now = new Date();
      const cur = formatClock(now);
      if (cur.hh !== parts.hh || cur.mm !== parts.mm) return;
      const at = new Date(now);
      at.setSeconds(0, 0);
      at.setMinutes(at.getMinutes() + 1);
      const np = formatClock(at);
      const chars =
        settings.layout === "stack"
          ? `${np.hh}\n${np.mm}`
          : `${np.hh}:${np.mm}`;
      if (chars.length !== spec.text.length) return;
      shapeWork = (async () => {
        if (swiping) await landed;
        const next = { ...spec, text: chars };
        const lk = look;
        const shape = bakeShape(next, lk);
        if (shape && liveSpec === spec)
          nextShape = { spec: next, shape, look: lk };
      })();
    }, 1500);
  }
  $effect(() => () => clearTimeout(prebakeTimer));

  const OFF: SlotView = {
    on: 0,
    toUv: new Float32Array([1, 0, 0, 0, 1, 0, 0, 0, 1]),
    light: [0, -1],
    lightRgb: [255, 255, 255],
    tint: null,
    glare: 0,
  };
  const matrixOf = (t: string): DOMMatrix =>
    !t || t === "none" ? new DOMMatrix() : new DOMMatrix(t);

  /** CSS's ease-out, for the drift. */
  function easeOut(x: number): number {
    const bez = (t: number, p1: number, p2: number) =>
      3 * p1 * t * (1 - t) ** 2 + 3 * p2 * t * t * (1 - t) + t ** 3;
    let lo = 0;
    let hi = 1;
    for (let k = 0; k < 18; k++) {
      const m = (lo + hi) / 2;
      if (bez(m, 0, 0.58) < x) lo = m;
      else hi = m;
    }
    return bez((lo + hi) / 2, 0, 1);
  }

  /** Each slot's elements and running animations, looked up once (a look
      brings the page's style up to date: milliseconds on a Pi, every
      frame) and from then on read by their clocks alone. Forgotten
      whenever the slots change role. */
  type Running = {
    img: HTMLElement;
    slide: HTMLElement;
    move?: Animation;
    drift?: Animation;
  };
  let running: [Running | null, Running | null] = [null, null];
  const forget = (): void => {
    running = [null, null];
  };
  function runningFor(i: 0 | 1): Running | null {
    const known = running[i];
    if (known?.img.isConnected) return known;
    const img = root?.querySelector<HTMLElement>(
      `img.photo-layer[data-slot="${i}"]`,
    );
    const slide = img?.parentElement;
    if (!img || !slide) return null;
    const r: Running = {
      img,
      slide,
      move: slide
        .getAnimations()
        .find(
          (a) =>
            a instanceof CSSTransition && a.transitionProperty === "transform",
        ),
      drift: img.getAnimations().find((a) => a instanceof CSSAnimation),
    };
    running[i] = r;
    return r;
  }
  const clockOf = (a: Animation | undefined): number | null =>
    a && typeof a.currentTime === "number" ? a.currentTime : null;

  /** Slot i's photo → screen right now: its swipe and its drift worked out
      from their animations' clocks and the curves they run (swipeCurve,
      and the photo-drift keyframes below), so the glass follows the very
      animation the compositor is running. A fade reads the page instead. */
  function slotMatrix(i: 0 | 1, r: Running): { m: DOMMatrix; on: number } {
    const ox = width / 2;
    const oy = height / 2;
    if (settings.transition === "fade") {
      const sc = getComputedStyle(r.slide);
      return {
        m: new DOMMatrix()
          .translate(ox, oy)
          .multiply(matrixOf(sc.transform))
          .multiply(matrixOf(getComputedStyle(r.img).transform))
          .translate(-ox, -oy),
        on: parseFloat(sc.opacity) || 0,
      };
    }
    const mt = clockOf(r.move);
    let x: number;
    if (mt !== null) {
      const p = swipeProgress(mt / SWIPE_MS);
      x = i === top ? width * (1 - p) : -width * p;
    } else x = i === entering ? width : i === top ? 0 : -width;
    // photo-drift: scale(1 → 1.04) translate(0 → -0.6%), ease-out.
    const dt = clockOf(r.drift);
    const dur = Number(r.drift?.effect?.getTiming().duration) || holdMs;
    const e = dt === null ? 0 : easeOut(Math.min(1, Math.max(0, dt / dur)));
    return {
      m: new DOMMatrix()
        .translate(ox + x, oy)
        .rotate(rots[i] ?? 0)
        .scale(1 + 0.04 * e)
        .translate(-0.006 * width * e, -0.006 * height * e)
        .translate(-ox, -oy),
      on: 1,
    };
  }

  /** Slot i as it is on screen right now, lit towards glass in `area` —
      the figures', unless given. */
  function slotView(i: 0 | 1, area?: GlassBox): SlotView {
    const light = slotLights[i];
    const r = runningFor(i);
    if (!r || !light || !slotReady[i] || !liveSpec) return OFF;
    const box = area ?? liveBox;
    const cx = area ? area.left + area.width / 2 : undefined;
    const cy = area ? area.top + area.height / 2 : undefined;
    const lm = lumas[i];
    const { m, on } = slotMatrix(i, r);
    const inv = m.inverse();
    const lp = m.transformPoint({ x: light.x, y: light.y });
    const lx = lp.x - (cx ?? liveSpec.cx);
    const ly = lp.y - (cy ?? liveSpec.cy);
    const ll = Math.hypot(lx, ly) || 1;
    return {
      on,
      toUv: new Float32Array([
        inv.a / width,
        inv.b / height,
        0,
        inv.c / width,
        inv.d / height,
        0,
        inv.e / width,
        inv.f / height,
        1,
      ]),
      light: [lx / ll, ly / ll],
      lightRgb: light.rgb,
      tint: hexRgb((tint === "auto" ? tints[i] : tint) || undefined),
      glare:
        lm && box
          ? lumaIn(lm, box.left, box.top, box.width, box.height).luma
          : 0.5,
    };
  }

  // Every frame while a photo moves; a few times a second while it only
  // drifts (a fraction of a pixel a frame); otherwise when something
  // changes. A frame that matches the last one isn't redrawn.
  const DRIFT_FRAME_MS = 125;
  let raf = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let lastSig = "";
  const drifting = $derived(
    settings.drift && !motion.reduced && !motion.batterySaver,
  );

  function render(force = false): void {
    if (!gd?.ready || !liveBox || !liveOn) return;
    const views: [SlotView, SlotView] = [slotView(0), slotView(1)];
    const sig = views
      .map(
        (v) => `${v.on}|${v.toUv.join(",")}|${v.tint}|${v.lightRgb}|${v.glare}`,
      )
      .join(";");
    if (!force && !swiping && sig === lastSig) return;
    lastSig = sig;
    gd.draw(liveBox, look, settings.opacity, views);
  }

  function frame(): void {
    raf = 0;
    render();
    renderPanel();
    if (swiping || panelMoving()) raf = requestAnimationFrame(frame);
    else if (drifting) timer = setTimeout(kick, DRIFT_FRAME_MS);
  }

  /** Draw on the next frame (and keep going while things move). */
  function kick(): void {
    clearTimeout(timer);
    timer = undefined;
    if (!raf) raf = requestAnimationFrame(frame);
  }
  $effect(() => {
    // Settings and tints change the glass without moving anything.
    void settings.opacity;
    void tint;
    void tints[0];
    void tints[1];
    void lumas;
    void liveOn;
    void drifting;
    void settings.transition;
    void look;
    forget();
    lastSig = "";
    kick();
    return () => {
      cancelAnimationFrame(raf);
      raf = 0;
      clearTimeout(timer);
    };
  });

  // The panel's glass: the same shader, look and photos as the figures',
  // in a second small canvas behind the card. Its shape is a rounded slab
  // baked at the card's tallest so far; any shorter height (the card
  // gliding to fit a new title) is drawn sliced from it, so a resize never
  // waits on a bake. It draws in the figures' frame loop, plus every frame
  // the card itself animates (its fade in and out, its height).
  const PANEL_PAD = 40;
  let panelEl = $state<HTMLCanvasElement | null>(null);
  let pd: GlassDigits | null = null;
  let panelBaked: {
    w: number;
    h: number;
    radius: number;
    look: typeof look;
  } | null = null;
  let panelSig = "";

  $effect(() => {
    const el = panelEl;
    const card = panel;
    if (!el || !card) return;
    const r = GlassDigits.create(el);
    if (!r) return;
    pd = r;
    // The photos as the glass sees them, uploaded to this context too.
    untrack(() => {
      prepSlot(0);
      prepSlot(1);
    });
    const lost = (e: Event): void => {
      e.preventDefault();
      pd = null;
    };
    const ro = new ResizeObserver(kick);
    ro.observe(card);
    card.addEventListener("glass:move", kick);
    el.addEventListener("webglcontextlost", lost);
    kick();
    return () => {
      ro.disconnect();
      card.removeEventListener("glass:move", kick);
      el.removeEventListener("webglcontextlost", lost);
      card.removeAttribute("data-live-glass");
      r.dispose();
      pd = null;
      panelBaked = null;
      panelSig = "";
    };
  });

  const panelMoving = (): boolean =>
    !!panel && panel.getAnimations().length > 0;

  function panelOff(): void {
    panel?.removeAttribute("data-live-glass");
    if (panelEl) panelEl.style.opacity = "0";
    panelSig = "";
  }

  function renderPanel(): void {
    const card = panel;
    const el = panelEl;
    if (!card || !el) return;
    if (!pd || !liveOn || !root || !liveSpec) return panelOff();
    const o = root.getBoundingClientRect();
    const r = card.getBoundingClientRect();
    const w = card.offsetWidth;
    // Its height mid-glide, and where it's gliding to: baked for the
    // taller, once, as the glide starts.
    const h = r.height;
    const goal = Math.max(h, parseFloat(card.style.height) || 0);
    const radius = parseFloat(getComputedStyle(card).borderTopLeftRadius) || 0;
    const b = panelBaked;
    if (
      !b ||
      b.look !== look ||
      Math.abs(b.w - w) > 0.5 ||
      Math.abs(b.radius - radius) > 0.5 ||
      goal > b.h + 0.5
    ) {
      const shape = bakePanel(w, goal, radius, radius * 0.5, PANEL_PAD, look);
      if (!shape) return panelOff();
      pd.setShape(el, shape);
      panelBaked = { w, h: goal, radius, look };
      el.style.width = `${shape.W / shape.dpr}px`;
      el.style.height = `${shape.H / shape.dpr}px`;
      panelSig = "";
    }
    const left = r.left - o.left - PANEL_PAD;
    const top = r.top - o.top - PANEL_PAD;
    const bh = h + PANEL_PAD * 2;
    const card$ = {
      left: left + PANEL_PAD,
      top: top + PANEL_PAD,
      width: w,
      height: h,
    };
    const views: [SlotView, SlotView] = [
      slotView(0, card$),
      slotView(1, card$),
    ];
    const fade = getComputedStyle(card).opacity;
    const sig = `${left}|${top}|${bh}|${fade}|${views
      .map(
        (v) => `${v.on}|${v.toUv.join(",")}|${v.tint}|${v.lightRgb}|${v.glare}`,
      )
      .join(";")}`;
    if (sig === panelSig) return;
    panelSig = sig;
    // The canvas hangs from the card's bottom edge; the slab fills its
    // lower `bh`, so a taller bake just reaches further up, blank.
    const canvasH = (panelBaked?.h ?? h) + PANEL_PAD * 2;
    el.style.left = `${left}px`;
    el.style.top = `${top + bh - canvasH}px`;
    el.style.opacity = fade;
    pd.draw(
      { left, top, width: w + PANEL_PAD * 2, height: bh },
      look,
      settings.opacity,
      views,
    );
    card.setAttribute("data-live-glass", "");
  }

  // Wide faces (Unbounded, Geist Mono) would run off the sides at these
  // sizes; shrink the figures to 92% of the width the frame leaves showing.
  let digitFit = $state(1);
  $effect(() => {
    void family;
    void settings.size;
    void settings.layout;
    void text;
    const box = root;
    if (!box || !width) return;
    let live = true;
    void document.fonts.ready.then(() => {
      const el = box.querySelector<HTMLElement>(".clock-layer .digits");
      if (!live || !el?.offsetWidth) return;
      const k = Math.min(1, ((width - 2 * fx) * 0.92) / el.offsetWidth);
      digitFit = k;
      fig = {
        w: el.offsetWidth * k,
        h: el.offsetHeight * k,
        top: el.offsetTop + (el.offsetHeight * (1 - k)) / 2,
      };
    });
    return () => {
      live = false;
    };
  });

  function hasCutout(i: number): boolean {
    return Boolean(subjects[i]) && Boolean(masks[i]);
  }

  function preload(i: number): void {
    const p = photos[i];
    if (!p) return;
    const displayUrl = client.photoDisplayUrl(p.name);
    void photoFor(displayUrl);
    if (p.has_subject) {
      void maskFor(client.photoSubjectUrl(p.name));
    }
  }

  let recent: string[] = [];
  /** The photo lined up to swipe in next (preloaded), and a new upload to
      show before anything else. */
  let upcoming = -1;
  let queued: string | null = null;

  function readRecent(): string[] {
    try {
      const v: unknown = JSON.parse(readLocal(RECENT_KEY) ?? "[]");
      return Array.isArray(v) ? v.filter((n) => typeof n === "string") : [];
    } catch {
      return [];
    }
  }

  function remember(name: string): void {
    recent = [...recent.filter((n) => n !== name), name].slice(
      -Math.max(1, recentLimit(photos.length)),
    );
    writeLocal(RECENT_KEY, JSON.stringify(recent));
    writeLocal(RESUME_KEY, name);
    if (share) photoShare.name = name;
  }

  /** Pick the photo after the current one, and start loading it. */
  function planNext(): void {
    const q = queued ? photos.findIndex((p) => p.name === queued) : -1;
    const today = weather?.forecast?.[0];
    upcoming =
      q >= 0 && q !== index
        ? q
        : pickNext(
            photos,
            index,
            recent,
            new Date(),
            parseClockTime(today?.sunrise),
            parseClockTime(today?.sunset),
          );
    preload(upcoming);
  }

  function begin(list: Photo[]): void {
    photos = list;
    if (list.length === 0) return;
    recent = readRecent();
    // Back from the cards: the Photo card's photo, so the handoff doesn't
    // cut to a different one. Otherwise a fresh pick after the last one.
    const shared = share
      ? list.findIndex((p) => p.name === photoShare.name)
      : -1;
    if (shared >= 0) index = shared;
    else {
      const resumeAt = readLocal(RESUME_KEY);
      index = resumeAt ? list.findIndex((p) => p.name === resumeAt) : -1;
      planNext();
      index = Math.max(0, upcoming);
    }
    const start = list[index];
    if (!start) return;

    const displayUrl = client.photoDisplayUrl(start.name);
    sources[top] = displayUrl;
    subjects[top] = start.has_subject ? client.photoSubjectUrl(start.name) : "";
    rots[top] = start.rotation ?? 0;
    tints[top] = start.tint ?? "";
    palettes[top] = start.colours ?? [];
    const first = top as 0 | 1;
    void loadMask(first, subjects[first] ?? "").then(() => readSlot(first));
    void photoFor(displayUrl).then((res) => {
      if (res?.img && sources[first] === displayUrl) {
        void loadFrost(first, displayUrl, res.img);
      }
    });
    playClip(start);
    remember(start.name);
    planNext();
    triggerWhisper();
  }

  $effect(() => {
    void client.listPhotos().then(begin);
  });

  // The clock can stay up all day, so read the library again now and then:
  // new uploads (and cutouts made since) join in, and a new photo is next up.
  async function relist(): Promise<void> {
    const list = await client.listPhotos().catch(() => null);
    if (!list || swapping) return;
    if (photos.length === 0) return begin(list);
    const known = new Set(photos.map((p) => p.name));
    const current = photos[index]?.name;
    const fresh = list.find((p) => !known.has(p.name));
    if (fresh) queued = fresh.name;
    photos = list;
    index = Math.max(
      0,
      list.findIndex((p) => p.name === current),
    );
    planNext();
  }

  $effect(() => {
    const id = setInterval(() => void relist(), RELIST_MS);
    return () => clearInterval(id);
  });

  /** Bumped as each photo's hold starts: restarts the date pill's ring. */
  let holdStart = $state(0);
  $effect(() => {
    if (photos.length < 2 || paused) return;
    untrack(() => holdStart++);
    const id = setInterval(() => {
      holdStart++;
      void step();
    }, holdMs);
    return () => clearInterval(id);
  });
  /** The date pill's countdown ring: off for now (asked 2026-10-19); kept
      so it can come back by flipping this. */
  const HOLD_RING = false;
  // A ring that fills while it's repainted twice a second, not every frame,
  // where every repaint costs (the Pi, lite tier).
  const ringSteps = $derived(
    platform.isPi || effectiveTier() === "lite"
      ? Math.max(1, Math.round(holdMs / 500))
      : 0,
  );

  /** Decode slot i's photo and cutout where they're shown, so their first
      frames on screen don't wait on it. */
  async function decodeSlot(i: number): Promise<void> {
    const imgs = root?.querySelectorAll<HTMLImageElement>(`[data-slot="${i}"]`);
    await Promise.all(
      [...(imgs ?? [])].map((img) => img.decode().catch(() => {})),
    );
  }

  async function step(): Promise<void> {
    if (photos.length < 2 || swapping) return;
    swapping = true;
    try {
      if (!photos[upcoming] || upcoming === index) planNext();
      const nextIndex = upcoming;
      const next = photos[nextIndex];
      if (!next) return;
      if (next.name === queued) queued = null;

      const nextTop = 1 - top;
      const nextDisplayUrl = client.photoDisplayUrl(next.name);
      const nextSubjectUrl = next.has_subject
        ? client.photoSubjectUrl(next.name)
        : "";

      sources[nextTop] = nextDisplayUrl;
      subjects[nextTop] = nextSubjectUrl;
      rots[nextTop] = next.rotation ?? 0;
      tints[nextTop] = next.tint ?? "";
      palettes[nextTop] = next.colours ?? [];

      // Photo and mask both in hand before the swipe, so the crop doesn't
      // jump once it's showing.
      const [photoObj, mask] = await Promise.all([
        photoFor(nextDisplayUrl),
        maskFor(nextSubjectUrl),
      ]);
      if (subjects[nextTop] === nextSubjectUrl) {
        masks[nextTop] = mask;
        await readSlot(nextTop as 0 | 1);
      }
      if (photoObj?.img && sources[nextTop] === nextDisplayUrl) {
        await loadFrost(nextTop, nextDisplayUrl, photoObj.img);
      }
      const relocate = spots[nextTop] !== spots[face];

      // Its glass baked (once, now its crop is known) and its pictures
      // decoded before anything moves: either one mid-swipe stalls it on
      // a Pi.
      pending = nextTop;
      await tick();
      await baked[nextTop];
      await shapeWork;
      await decodeSlot(nextTop);

      clip = "";
      moving = false;

      if (settings.transition === "fade") {
        landed = new Promise((r) => (land = r));
        swiping = true;
        relocating = relocate;
        entering = -1;
        leaving = top;
        index = nextIndex;
        top = nextTop;
        forget();
        kick();
        remember(next.name);
        planNext();
        await new Promise((r) => setTimeout(r, FADE_HANDOFF_MS));
        face = nextTop;
        pending = -1;
        relocating = false;
        await new Promise((r) => setTimeout(r, FADE_MS - FADE_HANDOFF_MS));
        swiping = false;
        leaving = -1;
        land();
        forget();
        kick();
        playClip(next);
        triggerWhisper();
      } else {
        // Park the next photo off the right edge, let that land, then swipe:
        // it slides in as the current one slides out to the left.
        entering = nextTop;
        await tick();
        await new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        );
        landed = new Promise((r) => (land = r));
        swiping = true;
        relocating = relocate;
        entering = -1;
        leaving = top;
        index = nextIndex;
        top = nextTop;
        forget();
        kick();
        remember(next.name);
        planNext();
        await new Promise((r) => setTimeout(r, HANDOFF_MS));
        face = nextTop;
        pending = -1;
        relocating = false;
        await new Promise((r) => setTimeout(r, SWIPE_MS - HANDOFF_MS));
        swiping = false;
        leaving = -1;
        land();
        forget();
        kick();
        playClip(next);
        triggerWhisper();
      }
    } finally {
      swapping = false;
      swiping = false;
      relocating = false;
      leaving = -1;
      pending = -1;
      land();
    }
  }
</script>

{#snippet clockLayer(forefront: boolean)}
  <div
    class="clock-layer"
    class:forefront
    class:relocating
    class:size-s={settings.size === "s"}
    class:size-m={settings.size === "m"}
    class:size-l={settings.size === "l"}
    class:size-xl={settings.size === "xl"}
  >
    <div
      class="digits {inkLook ? `ink ink-${inkLook}` : ''}"
      class:stack={settings.layout === "stack"}
      class:glass-liquid={settings.glass === "liquid" ||
        settings.glass === "crystal"}
      class:glass-frosted={settings.glass === "frosted"}
      class:glass-flat={settings.glass === "flat"}
      class:breathe={inkLook === "mesh" &&
        !motion.reduced &&
        !motion.batterySaver &&
        effectiveTier() !== "lite"}
      class:baked={liveOn || glassBoxes[face] != null}
      style:--ink-main={inks?.main}
      style:--ink-opposite={inks?.opposite}
      style:--ink-deep={inks?.deep}
      style:--mesh-0={inks?.mesh[0]}
      style:--mesh-1={inks?.mesh[1]}
      style:--mesh-2={inks?.mesh[2]}
      style:--mesh-3={inks?.mesh[3]}
      style:--frost-img={frosts[face] && !rots[face]
        ? `url(${frosts[face]})`
        : undefined}
      style:--frost-pos={position(face)}
      style:scale={digitFit}
      style:translate={shift ? `${shift}px 0` : undefined}
      style:--tint={glassTint}
    >
      {#if settings.layout === "stack"}
        <span class="line">{parts.hh}</span>
        <span class="line">{parts.mm}</span>
      {:else}
        {text}
      {/if}
    </div>
    <canvas class="glass ghost" bind:this={ghostEl} aria-hidden="true"></canvas>
    <canvas
      class="glass on"
      bind:this={liveEl}
      hidden={!liveOn}
      style:left="{liveBox?.left ?? 0}px"
      style:top="{liveBox?.top ?? 0}px"
      style:width="{liveBox?.width ?? 0}px"
      style:height="{liveBox?.height ?? 0}px"
      aria-hidden="true"
    ></canvas>
    {#each glassBoxes as box, i (i)}
      <canvas
        class="glass"
        class:on={i === face && !liveOn}
        bind:this={glassEls[i]}
        hidden={!box}
        style:left="{box?.left ?? 0}px"
        style:top="{box?.top ?? 0}px"
        style:width="{box?.width ?? 0}px"
        style:height="{box?.height ?? 0}px"
        aria-hidden="true"
      ></canvas>
    {/each}
  </div>
{/snippet}

<div
  class="photo-clock"
  class:mode-fade={settings.transition === "fade"}
  class:mode-drift={settings.drift &&
    !motion.reduced &&
    !motion.batterySaver &&
    effectiveTier() !== "lite"}
  bind:this={root}
  bind:clientWidth={width}
  bind:clientHeight={height}
  style:--font-family={family}
  style:--clock-opacity={settings.opacity}
  style:--swipe-ms="{SWIPE_MS}ms"
  style:--swipe-ease={SWIPE_EASE}
  style:--hold-ms="{holdMs}ms"
  style:--fx="{fx}px"
>
  {#if photos.length > 0}
    <!-- Layer 1: Base Photos -->
    {#each sources as src, i (i)}
      {#if src}
        <div
          class="slot-slide photo-slot"
          class:show={i === top}
          class:enter={i === entering}
        >
          <img
            class="photo-layer"
            data-slot={i}
            class:drifting={settings.drift &&
              (i === top || i === leaving) &&
              !motion.reduced &&
              !motion.batterySaver &&
              effectiveTier() !== "lite"}
            {src}
            alt=""
            decoding="async"
            fetchpriority={i === top ? "high" : "low"}
            style:--rot="{rots[i]}deg"
            style:object-position={position(i)}
          />
        </div>
      {/if}
    {/each}
    {#key clip}
      {#if clip}
        <div class="slot-slide photo-slot show">
          <video
            class="motion-layer"
            class:show={moving && started}
            src={clip}
            bind:this={clipEl}
            muted
            playsinline
            autoplay
            onplaying={() => (started = true)}
            onended={clipEnded}
            onerror={() => (moving = false)}
            style:--rot="{rots[top]}deg"
            style:object-position={position(top)}
          ></video>
        </div>
      {/if}
    {/key}

    {@const tucked =
      settings.depth &&
      !moving &&
      hasCutout(face) &&
      hidden.all < MAX_HIDDEN &&
      hidden.worst < MAX_HIDDEN_DIGIT}
    <!-- Layer 2: the glass time, behind the cutout when there is one and it
         wouldn't hide too much of the figures. -->
    {@render clockLayer(!tucked)}

    <!-- Layer 3: Foreground Subject Cutout (when depth enabled) -->
    {#if settings.depth}
      {#each subjects as subSrc, i (i)}
        {#if subSrc}
          <div
            class="slot-slide cutout-slot"
            class:show={i === top}
            class:enter={i === entering}
            class:away={moving && i === top}
          >
            <img
              class="cutout-layer"
              data-slot={i}
              class:drifting={settings.drift &&
                (i === top || i === leaving) &&
                !motion.reduced &&
                !motion.batterySaver &&
                effectiveTier() !== "lite"}
              src={subSrc}
              alt=""
              decoding="async"
              style:--rot="{rots[i]}deg"
              style:object-position={position(i)}
            />
          </div>
        {/if}
      {/each}
    {/if}
    {#if panel}
      <canvas class="panel-glass" bind:this={panelEl} aria-hidden="true"
      ></canvas>
    {/if}
    <!-- The date pill is for reading: always in front, in whichever corner
         the photo's subject leaves clearest. -->
    {#if settings.date}
      <div class="date-capsule corner {corner}" class:away={swiping}>
        {dateLabel}
        {#if HOLD_RING && photos.length > 1 && !paused}
          <!-- How long until the next photo: fills clockwise over the hold. -->
          {#key holdStart}
            <svg
              class="hold-ring"
              viewBox="0 0 20 20"
              aria-hidden="true"
              style:--ring-ease={ringSteps
                ? `steps(${ringSteps}, end)`
                : "linear"}
            >
              <circle class="track" cx="10" cy="10" r="8" pathLength="100" />
              <circle class="fill" cx="10" cy="10" r="8" pathLength="100" />
            </svg>
          {/key}
        {/if}
      </div>
    {/if}
    <!-- Memory whisper pill: soft, elegant fade in and dissolve -->
    {#if settings.whisper && whisperText}
      <div class="whisper-capsule" class:show={whisperActive && !swiping}>
        {whisperText}
      </div>
    {/if}
    <!-- Film grain overlay -->
    {#if settings.grain > 0}
      <div
        class="grain-overlay"
        style:opacity={settings.grain}
        aria-hidden="true"
      ></div>
    {/if}
  {:else}
    <!-- Empty state: no photos uploaded yet -->
    <div class="empty-backdrop">
      <div class="clock-layer forefront size-l">
        <div
          class="digits glass-liquid"
          class:stack={settings.layout === "stack"}
        >
          {#if settings.layout === "stack"}
            <span class="line">{parts.hh}</span>
            <span class="line">{parts.mm}</span>
          {:else}
            {text}
          {/if}
        </div>
        {#if settings.date}
          <div class="date-capsule">
            {dateLabel}
          </div>
        {/if}
        <p class="empty-hint">
          Add photos in Settings to activate the Photo Clock
        </p>
      </div>
    </div>
  {/if}
</div>

<style>
  .photo-clock {
    position: relative;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background: #000;
    container-type: size;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* Slot slide wrappers */
  .slot-slide {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    transform: translateX(-100%);
    transition:
      transform var(--swipe-ms) var(--swipe-ease),
      opacity 0.6s ease;
    pointer-events: none;
  }
  .slot-slide.photo-slot {
    z-index: 1;
  }
  .slot-slide.cutout-slot {
    z-index: 3; /* above the time when it's tucked */
  }
  .slot-slide.show,
  .slot-slide.enter {
    will-change: transform;
  }
  .slot-slide.show {
    transform: translateX(0);
  }
  .slot-slide.enter {
    transform: translateX(100%);
    transition: none;
  }
  .slot-slide.cutout-slot.away {
    opacity: 0;
  }

  /* Fade transition mode */
  .mode-fade .slot-slide {
    transform: none;
    opacity: 0;
    transition: opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .mode-fade .slot-slide.show {
    transform: none;
    opacity: 1;
  }
  .mode-fade .slot-slide.enter {
    transform: none;
    opacity: 0;
    transition: none;
  }

  /* Inner photo and cutout layers */
  .photo-layer,
  .cutout-layer {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    transform: rotate(var(--rot, 0deg));
    pointer-events: none;
  }

  /* Ken Burns drift. The cutout moves exactly with its photo: it's the
     photo's own subject, still there underneath, so drifting it any less
     (a parallax) shows the person twice, slipping apart over the hold. */
  .photo-layer.drifting,
  .cutout-layer.drifting {
    will-change: transform;
    animation: photo-drift var(--hold-ms, 30s) ease-out forwards;
  }
  @keyframes photo-drift {
    0% {
      transform: rotate(var(--rot, 0deg)) scale(1) translate3d(0, 0, 0);
    }
    100% {
      transform: rotate(var(--rot, 0deg)) scale(1.04)
        translate3d(-0.6%, -0.6%, 0);
    }
  }

  /* Over its still, under the time. Not a transform layer like the photos:
     it only ever plays once a photo has landed. */
  .motion-layer {
    position: absolute;
    inset: 0;
    z-index: 1;
    width: 100%;
    height: 100%;
    object-fit: cover;
    transform: rotate(var(--rot, 0deg));
    opacity: 0;
    transition: opacity 0.6s ease;
    pointer-events: none;
  }
  .motion-layer.show {
    opacity: 1;
  }

  @media (prefers-reduced-motion: reduce) {
    .slot-slide {
      transition: none !important;
    }
    .photo-layer.drifting,
    .cutout-layer.drifting {
      animation: none !important;
    }
  }

  /* Clock Layer */
  .clock-layer {
    position: absolute;
    inset: 0;
    z-index: 2; /* Below cutout in depth mode */
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    padding-top: min(8cqh, 48px);
    pointer-events: none;
    transition:
      z-index 0.2s ease,
      opacity 0.5s ease;
  }
  /* Moving to the next photo's spot: out before the handoff, back in at
     the new spot once it's there. */
  .clock-layer.relocating {
    opacity: 0;
    transition:
      z-index 0.2s ease,
      opacity 0.18s ease;
  }
  .clock-layer.forefront {
    z-index: 4; /* In front of cutout */
  }

  /* Digits Typography & Sizing */
  .digits {
    font-family: var(--font-family);
    font-weight: 800;
    line-height: 0.85;
    letter-spacing: -0.04em;
    font-variant-numeric: tabular-nums lining-nums;
  }
  .digits.stack {
    display: flex;
    flex-direction: column;
    align-items: center;
    line-height: 0.82;
  }
  .digits.stack .line {
    display: block;
  }

  .size-s .digits {
    font-size: min(20cqh, 24cqi);
  }
  .size-s .digits.stack {
    font-size: min(15cqh, 24cqi);
  }
  .size-m .digits {
    font-size: min(26cqh, 30cqi);
  }
  .size-m .digits.stack {
    font-size: min(20cqh, 28cqi);
  }
  .size-l .digits {
    font-size: min(32cqh, 36cqi);
  }
  .size-l .digits.stack {
    font-size: min(25cqh, 34cqi);
  }
  .size-xl .digits {
    font-size: min(38cqh, 42cqi);
  }
  .size-xl .digits.stack {
    font-size: min(30cqh, 40cqi);
  }

  /* Glass: each figure is filled with a frosted copy of the photo behind
     it — the tiny frost image, pinned to the screen (fixed) and cropped
     like the photo so it lines up — washed toward white, with a sheen
     from the top left. No text-stroke: on variable fonts it traces every
     overlapping contour, drawing lines inside the figures. The rim is a
     drop-shadow, which only follows the outside edge. */
  .digits.glass-liquid,
  .digits.glass-frosted {
    color: transparent;
    background-image:
      linear-gradient(
        170deg,
        rgb(255 255 255 / 0.75) 0%,
        rgb(255 255 255 / 0.15) 32%,
        rgb(255 255 255 / 0) 55%,
        rgb(255 255 255 / 0.2) 100%
      ),
      linear-gradient(
        rgb(from var(--tint, #ecf6ff) r g b / var(--frost)),
        rgb(from var(--tint, #ecf6ff) r g b / var(--frost))
      ),
      var(--frost-img, linear-gradient(#9aa4ad, #9aa4ad));
    background-attachment: scroll, scroll, fixed;
    background-size:
      100% 100%,
      100% 100%,
      cover;
    background-position:
      0 0,
      0 0,
      var(--frost-pos, 50% 50%);
    -webkit-background-clip: text;
    background-clip: text;
    /* Edges: a bright lip on top, a faint dark one below for thickness,
       then a cool halo and a soft lift off the photo. */
    filter: saturate(1.4) brightness(1.08)
      drop-shadow(0 -1px 0 rgb(255 255 255 / 0.9))
      drop-shadow(0 1.5px 0 rgb(0 0 0 / 0.14))
      drop-shadow(0 0 14px rgb(from var(--tint, #dcf0ff) r g b / 0.35))
      drop-shadow(0 14px 30px rgb(0 0 0 / 0.28));
  }
  .digits.glass-liquid {
    --frost: var(--clock-opacity, 0.45);
  }
  .digits.glass-frosted {
    --frost: calc(var(--clock-opacity, 0.45) + 0.2);
  }

  /* Baked: the canvas is the glass; the figures stay for layout, the
     cutout's coverage check and screen readers. */
  .digits.baked {
    background: none;
    color: transparent;
    filter: none;
  }
  /* Its shadow is baked in with it: a CSS filter here would be redrawn
     on every frame of a swipe, and a Pi's GPU can't spare it. */
  .glass {
    position: absolute;
    opacity: 0;
  }
  .glass.on {
    opacity: 1;
  }
  /* Over the live glass while the minute turns (ghost()). */
  .glass.ghost {
    z-index: 1;
    pointer-events: none;
  }

  .digits.glass-flat {
    color: rgb(
      from var(--tint, #fff) r g b / calc(var(--clock-opacity, 0.45) + 0.25)
    );
    text-shadow: 0 4px 20px rgb(0 0 0 / 0.5);
  }

  /* The colour looks: inks from the photo (lib/clockInk). Plain CSS, no
     canvas: the cheapest to draw on a Pi. Each has a dark edge or glow so
     it still reads where the photo is the same colour. */
  .digits.ink {
    transition:
      color 1.2s ease,
      text-shadow 1.2s ease;
  }
  .digits.ink-match {
    color: var(--ink-main);
    text-shadow:
      0 2px 0 rgb(from var(--ink-deep) r g b / 0.65),
      0 10px 40px rgb(0 0 0 / 0.35);
  }
  .digits.ink-opposite {
    color: var(--ink-opposite);
    text-shadow:
      0 2px 0 rgb(from var(--ink-deep) r g b / 0.65),
      0 10px 40px rgb(0 0 0 / 0.35);
  }
  /* A soft blend of the photo's colours that drifts; on fuller screens
     the figures breathe too (weight, on fonts that have the axis). */
  .digits.ink-mesh {
    color: transparent;
    background-image:
      radial-gradient(at 15% 25%, var(--mesh-0) 0, transparent 50%),
      radial-gradient(at 85% 15%, var(--mesh-1) 0, transparent 50%),
      radial-gradient(at 60% 85%, var(--mesh-2) 0, transparent 55%),
      radial-gradient(at 25% 90%, var(--mesh-3) 0, transparent 55%),
      linear-gradient(135deg, var(--mesh-0), var(--mesh-3));
    background-size: 220% 220%;
    -webkit-background-clip: text;
    background-clip: text;
    filter: drop-shadow(0 1px 1px rgb(0 0 0 / 0.25))
      drop-shadow(0 6px 22px rgb(0 0 0 / 0.35));
    /* Stepped: a few repaints a second, not sixty (the Pi). */
    animation: ink-flow 40s steps(160) infinite alternate;
  }
  .digits.ink-mesh.breathe {
    animation:
      ink-flow 40s steps(160) infinite alternate,
      ink-breathe 10s ease-in-out infinite;
  }
  @keyframes ink-flow {
    0% {
      background-position: 0% 0%;
    }
    50% {
      background-position: 100% 60%;
    }
    100% {
      background-position: 30% 100%;
    }
  }
  @keyframes ink-breathe {
    0%,
    100% {
      font-weight: 720;
    }
    50% {
      font-weight: 880;
    }
  }
  /* Polished metal: bands of white and steel, the photo's colour in the
     upper reflection and the opposite in the lower, a slow sheen. */
  .digits.ink-chrome {
    color: transparent;
    background-image: linear-gradient(
      180deg,
      #fff 0%,
      #e6ebf0 14%,
      var(--ink-main) 30%,
      #f4f7fa 40%,
      #10141a 47%,
      #3a4350 52%,
      #c9d1da 60%,
      var(--ink-opposite) 74%,
      #fff 84%,
      #9aa5b1 92%,
      #fff 100%
    );
    background-size: 100% 180%;
    -webkit-background-clip: text;
    background-clip: text;
    filter: drop-shadow(0 -1px 0 rgb(255 255 255 / 0.9))
      drop-shadow(0 2px 0 rgb(0 0 0 / 0.55))
      drop-shadow(0 12px 28px rgb(0 0 0 / 0.45));
    animation: ink-sheen 32s steps(120) infinite alternate;
  }
  @keyframes ink-sheen {
    from {
      background-position: 0 0;
    }
    to {
      background-position: 0 100%;
    }
  }
  /* Two-ink print: a solid opposite-colour layer just off register, under
     a halftone of the deep ink, tilted a touch. */
  .digits.ink-print {
    color: transparent;
    background-image: radial-gradient(var(--ink-deep) 42%, transparent 46%);
    background-size: 0.03em 0.03em;
    -webkit-background-clip: text;
    background-clip: text;
    text-shadow: -0.04em -0.03em 0 var(--ink-opposite);
    rotate: -2deg;
    filter: drop-shadow(0 8px 24px rgb(0 0 0 / 0.3));
  }
  /* Neon: thin tubes glowing in the opposite colour, with a faint hum. */
  .digits.ink-neon {
    font-weight: 300;
    color: rgb(
      from var(--ink-opposite) calc(r + (255 - r) * 0.85)
        calc(g + (255 - g) * 0.85) calc(b + (255 - b) * 0.85)
    );
    text-shadow:
      0 0 2px #fff,
      0 0 0.04em var(--ink-opposite),
      0 0 0.1em var(--ink-opposite),
      0 0 0.22em var(--ink-opposite),
      0 0 0.4em var(--ink-opposite);
    animation: ink-hum 7s linear infinite;
  }
  @keyframes ink-hum {
    0%,
    48%,
    52%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.86;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .digits.ink {
      animation: none !important;
    }
  }

  /* Date Capsule */
  .date-capsule {
    margin-top: min(2.5cqh, 16px);
    font-family: var(--font-body, -apple-system, sans-serif);
    font-size: min(4cqh, 3.8cqi, 1.25rem);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.9);
    background: rgba(0, 0, 0, 0.28);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    padding: min(1.2cqh, 8px) min(3cqh, 22px);
    border-radius: 40px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  }
  /* The time left on this photo: a ring the height of the pill's capitals,
     right after the text. */
  .date-capsule {
    display: inline-flex;
    align-items: center;
    gap: 0.55em;
  }
  .hold-ring {
    width: 0.8em;
    height: 0.8em;
    flex: none;
    /* From twelve o'clock, clockwise. */
    transform: rotate(-90deg);
    fill: none;
    stroke-width: 2.6;
  }
  .hold-ring .track {
    stroke: rgba(255, 255, 255, 0.22);
  }
  .hold-ring .fill {
    stroke: rgba(255, 255, 255, 0.85);
    stroke-linecap: round;
    stroke-dasharray: 100;
    stroke-dashoffset: 100;
    animation: hold-fill var(--hold-ms) var(--ring-ease) forwards;
  }
  @keyframes hold-fill {
    to {
      stroke-dashoffset: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .hold-ring {
      display: none;
    }
  }
  /* Out of the way while a photo swipes in, back in the new photo's
     clearest corner once it lands. Hidden, its backdrop blur isn't redrawn
     over the moving photos on every frame. */
  .date-capsule.corner {
    transition: opacity 0.35s ease;
  }
  /* Under the card it's behind (drawn by renderPanel); opacity follows the
     card's own fade. */
  .panel-glass {
    position: absolute;
    z-index: 4;
    opacity: 0;
    pointer-events: none;
  }
  .date-capsule.corner.away {
    opacity: 0;
    visibility: hidden;
    transition:
      opacity 0.15s ease,
      visibility 0s 0.15s;
  }

  .corner {
    position: absolute;
    z-index: 4;
    margin: 0;
    --edge: min(5cqh, 40px);
  }
  .corner.tl,
  .corner.tr {
    top: var(--edge);
  }
  .corner.bl,
  .corner.br {
    bottom: var(--edge);
  }
  .corner.tl,
  .corner.bl {
    left: calc(var(--edge) + var(--fx, 0px));
  }
  .corner.tr,
  .corner.br {
    right: calc(var(--edge) + var(--fx, 0px));
  }

  /* Empty state fallback */
  .empty-backdrop {
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at center, #2c3e50 0%, #000 100%);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .empty-hint {
    margin-top: 16px;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
  }

  /* Memory Whisper Capsule */
  .whisper-capsule {
    position: absolute;
    bottom: min(4cqh, 32px);
    left: 50%;
    transform: translateX(-50%) translateY(4px);
    z-index: 4;
    pointer-events: none;
    font-family: var(--font-body, -apple-system, sans-serif);
    font-size: min(2.8cqh, 2.5cqi, 0.95rem);
    font-weight: 500;
    letter-spacing: 0.04em;
    color: rgba(255, 255, 255, 0.88);
    background: rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    padding: min(1cqh, 6px) min(2.5cqh, 18px);
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    opacity: 0;
    transition:
      opacity 1.2s cubic-bezier(0.16, 1, 0.3, 1),
      transform 1.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .whisper-capsule.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }

  /* Analog Film Grain Overlay */
  .grain-overlay {
    position: absolute;
    inset: 0;
    z-index: 5;
    pointer-events: none;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
    background-repeat: repeat;
    background-size: 140px 140px;
    mix-blend-mode: overlay;
    transition: opacity 0.3s ease;
  }
</style>
