<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The traffic deck. Inside a commute window (server-side, see
  providers/traffic_cams.py) it loops the freeway speed map (held 40s — it's
  the deck's main card) → Cam 1 → … → Cam N (8s each), one at a time, edge to
  edge like the Photo card (cropped, never stretched). Outside a window it says
  so quietly. It never grows past its own cell.

  Its own two-layer loop rather than Cycler: a camera frame must be decoded
  before it's faded in (same reason as Photo).
-->
<script lang="ts" module>
  /** Where the deck was, and how long that slide had left, when it last
      came off screen: Alternate remounts the cards every 30 s, shorter than
      the map's hold, so starting over each time never got past the map. */
  let resume: { key: string; remaining: number } | null = null;

  /** Forget it (tests). */
  export function forgetTrafficResume(): void {
    resume = null;
  }
</script>

<script lang="ts">
  import { tick, untrack } from "svelte";

  import Card from "../components/Card.svelte";
  import TrafficMap from "./TrafficMap.svelte";
  import { timeOfDay } from "../lib/format";
  import { platform } from "../lib/platform.svelte";
  import { effectiveTier, motion } from "../lib/tier.svelte";
  import type { CardProps, TrafficData } from "./types";
  import { pick } from "./types";
  import { paced } from "../lib/prefs.svelte";

  let { view, stale, hero }: CardProps = $props();

  const MAP_MS = 40_000;
  const CAM_MS = 8_000;

  type Slot = { kind: "cam"; id: string } | { kind: "map" };

  const traffic = $derived(pick<TrafficData>(view, "traffic"));
  const cams = $derived(traffic?.active ? (traffic.cams ?? []) : []);
  const map = $derived(traffic?.active ? (traffic.map ?? null) : null);
  // The Pi shows a flipbook camera as its still — a 300ms frame loop is the
  // same constant-repaint load that made the radar loop ~70% of its CPU.
  const still = $derived(
    platform.isPi || motion.reduced || effectiveTier() === "lite",
  );

  // Primitives only: the view is rebuilt on every store update, so depending
  // on `cams` itself would restart the dwell timer every time anything
  // anywhere changed.
  const slotKeys = $derived(
    [...(map ? ["map"] : []), ...cams.map((c) => c.id)].join(","),
  );
  const srcKey = $derived(cams.map((c) => c.src).join(" "));

  let layers = $state<[Slot | null, Slot | null]>([null, null]);
  let top = $state(0);
  let imgs = $state<(HTMLImageElement | undefined)[]>([]);
  let frame = $state(0);
  let pos = 0;
  let busy = false;

  // The map leads the loop when there is one.
  function slotAt(p: number): Slot | null {
    if (map) {
      if (p === 0) return { kind: "map" };
      p -= 1;
    }
    const cam = cams[p];
    return cam ? { kind: "cam", id: cam.id } : null;
  }

  function camFor(slot: Slot | null | undefined) {
    return slot?.kind === "cam"
      ? cams.find((c) => c.id === slot.id)
      : undefined;
  }

  function live(slot: Slot | null | undefined): boolean {
    return slot?.kind === "map" ? !!map : !!camFor(slot);
  }

  function srcFor(slot: Slot | null, showing: boolean): string {
    const cam = camFor(slot);
    if (!cam) return "";
    if (still || cam.frames.length < 2) return cam.src;
    return cam.frames[(showing ? frame : 0) % cam.frames.length] ?? cam.src;
  }

  function preload(urls: string[]): void {
    for (const url of urls) new Image().src = url;
  }

  async function advance(): Promise<void> {
    const n = cams.length + (map ? 1 : 0);
    if (n === 0 || busy) return;
    busy = true;
    try {
      pos = (pos + 1) % n;
      const next = slotAt(pos);
      const back = (1 - top) as 0 | 1;
      layers[back] = next;
      await tick();
      try {
        await imgs[back]?.decode();
      } catch {
        /* show it regardless */
      }
      frame = 0;
      top = back;
    } finally {
      busy = false;
    }
  }

  function keyOf(slot: Slot | null | undefined): string {
    return slot ? (slot.kind === "cam" ? slot.id : "map") : "";
  }

  // (Re)start the loop when the set of slides changes — a window opening or
  // closing, a camera going stale, the map dropping out — picking up where
  // the deck last was.
  $effect(() => {
    void slotKeys;
    let first: number | undefined;
    const n = untrack(() => {
      const at = resume ? slotKeys.split(",").indexOf(resume.key) : -1;
      if (at >= 0 && keyOf(layers[top]) !== resume?.key) {
        pos = at;
        frame = 0;
        layers[top] = slotAt(at);
        first = resume?.remaining;
      } else if (!live(layers[top])) {
        pos = 0;
        frame = 0;
        layers[top] = slotAt(0);
      }
      return cams.length + (map ? 1 : 0);
    });
    if (n < 2) return;
    // A timeout per card rather than one interval: the map holds longer.
    let running = true;
    let id: ReturnType<typeof setTimeout> | undefined;
    let due = 0;
    const next = (ms?: number): void => {
      ms ??= paced(layers[top]?.kind === "map" ? MAP_MS : CAM_MS);
      due = Date.now() + ms;
      id = setTimeout(async () => {
        if (!document.hidden) await advance();
        if (running) next();
      }, ms);
    };
    untrack(() => next(first));
    return () => {
      running = false;
      clearTimeout(id);
      resume = {
        key: keyOf(layers[top]),
        remaining: Math.max(1_000, due - Date.now()),
      };
    };
  });

  // Keep every camera's current capture (and flipbook frames) in the browser
  // cache, so a slot change never waits on the network.
  $effect(() => {
    void srcKey;
    untrack(() =>
      preload(cams.flatMap((c) => (still ? [c.src] : [c.src, ...c.frames]))),
    );
  });

  // Play the showing camera's flipbook, if it has one.
  const flip = $derived.by(() => {
    const cam = camFor(layers[top]);
    return !still && cam && cam.frames.length > 1
      ? `${cam.id}:${cam.frames.length}:${cam.frameMs}`
      : "";
  });
  $effect(() => {
    if (!flip) return;
    const ms = Number(flip.split(":")[2]) || 300;
    const id = setInterval(() => frame++, ms);
    return () => clearInterval(id);
  });

  let alertIndex = $state(0);

  // "1:51 PM", the same as the radar card's stamp beside it.
  function clock(iso: string): string {
    return timeOfDay(new Date(iso));
  }

  const alerts = $derived.by(() => {
    if (!map) return [];
    if (map.alerts && map.alerts.length > 0) return map.alerts;
    if (map.slowest) {
      const delay = map.slowest.delay ? ` (+${map.slowest.delay}m)` : "";
      return [
        {
          type: "slow" as const,
          text: `${map.slowest.mph} mph${delay} · ${map.slowest.label}`,
        },
      ];
    }
    return [{ type: "ok" as const, text: "Freeways flowing" }];
  });

  const activeAlert = $derived(
    alerts[alertIndex % Math.max(1, alerts.length)] ?? alerts[0],
  );

  const mapLabel = $derived(
    activeAlert?.text ??
      (map?.slowest
        ? `${map.slowest.mph} mph${map.slowest.delay ? ` (+${map.slowest.delay}m)` : ""} · ${map.slowest.label}`
        : "Freeways flowing"),
  );

  // Rotate through alerts if multiple are present during the 40s map hold.
  $effect(() => {
    if (layers[top]?.kind !== "map" || alerts.length <= 1 || motion.reduced) {
      alertIndex = 0;
      return;
    }
    const id = setInterval(() => {
      alertIndex = (alertIndex + 1) % alerts.length;
    }, 9_000);
    return () => clearInterval(id);
  });
</script>

<Card accent="affirmation" {stale} {hero} bleed>
  <div class="stack">
    {#each layers as slot, i (i)}
      {@const cam = camFor(slot)}
      <div
        class="layer"
        class:show={i === top}
        class:cam={!!cam || (slot?.kind === "map" && !!map)}
        aria-hidden={i === top ? undefined : "true"}
      >
        {#if slot?.kind === "map" && map}
          <TrafficMap {map} />
          <span class="attribution">Esri · Houston TranStar</span>
          <span class="chips">
            <span
              class="chip where"
              class:slow={activeAlert?.type === "slow" ||
                (!activeAlert && !!map.slowest)}
              class:crash={activeAlert?.type === "crash" ||
                activeAlert?.type === "closure"}
              class:flood={activeAlert?.type === "flood"}>{mapLabel}</span
            >
            {#if map.updatedAt}
              <span class="chip when" class:late={map.stale}
                >{clock(map.updatedAt)}</span
              >
            {/if}
          </span>
        {:else if cam}
          <img
            bind:this={imgs[i]}
            src={srcFor(slot, i === top)}
            alt="Traffic camera: {cam.label}"
            decoding="async"
          />
          <!-- Chips and attribution as on the radar card. -->
          <span class="attribution">Houston TranStar</span>
          <span class="chips">
            <span class="chip where">{cam.label}</span>
            <span class="chip when" class:late={cam.stale}
              >{clock(cam.capturedAt)}</span
            >
          </span>
        {:else if i === top}
          <span class="waiting"
            >{traffic?.active ? "…" : "Traffic cams are off for now"}</span
          >
        {/if}
      </div>
    {/each}
  </div>
</Card>

<style>
  .stack {
    flex: 1;
    display: grid;
    grid-template-rows: minmax(0, 1fr);
    /* The Quote card's floor, so a content-sized row (tablets, phones) keeps
       its height between cameras. */
    min-height: 50cqi;
    border-radius: inherit;
  }
  /* A panel that fills its screen sets the row's height, which on a tall
     screen is less than this floor: fit the row instead. */
  :global(.stage.fills) .stack {
    min-height: 0;
  }
  .layer {
    grid-area: 1 / 1;
    position: relative;
    display: flex;
    min-width: 0;
    min-height: 0;
    padding: var(--space-4);
    opacity: 0;
    /* Own compositor layer: the swap is a GPU opacity blend, cheap on the Pi
       once the frame is decoded (see Photo.svelte). */
    transform: translateZ(0);
    will-change: opacity;
    transition: opacity 600ms ease;
  }
  @media (max-width: 640px) {
    .layer {
      padding: var(--space-3);
    }
  }
  .layer.show {
    opacity: 1;
  }
  .layer:not(.show) {
    pointer-events: none;
  }
  @media (prefers-reduced-motion: reduce) {
    .layer {
      transition: none;
    }
  }
  .layer.cam {
    padding: 0;
    overflow: hidden;
    /* Photographic bed behind the frame, as on the Photo card. */
    background: #000;
  }
  .layer.cam img {
    position: absolute;
    left: 0;
    width: 100%;
    /* TranStar burns a camera name into the top ~10% of every frame and a
       timestamp + copyright strip into the bottom ~11%; the chips below say
       the same things legibly. Oversize the box 15% past both edges (hides
       15/130 ≈ 11.5% of the image each side) so the layer's overflow:hidden
       trims them — `cover` keeps the aspect, so this only ever crops, never
       stretches. */
    top: -15%;
    height: 130%;
    object-fit: cover;
    object-position: center;
  }
  /* A soft inset border in the stage colour, as on the radar card, so the
     camera doesn't read as a hard-edged photo dropped into the layout. */
  .layer.cam::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    box-shadow: inset 0 0 0 2px
      color-mix(in srgb, var(--stage) 45%, transparent);
    pointer-events: none;
  }
  .chips {
    position: absolute;
    left: var(--space-2);
    right: var(--space-2);
    bottom: var(--space-2);
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .chip {
    padding: calc(0.2rem * var(--ui-scale)) calc(0.55rem * var(--ui-scale));
    border-radius: var(--radius-pill);
    background: rgba(15, 13, 19, 0.62);
    color: #e8e4ec;
    font-size: var(--type-caption);
    font-weight: var(--weight-label);
    white-space: nowrap;
  }
  .where {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .where.slow {
    color: #ffb47a;
  }
  .where.crash {
    color: #ff858d;
  }
  .where.flood {
    color: #7dd3fc;
  }
  .when {
    flex: none;
    font-variant-numeric: tabular-nums;
  }
  .when.late {
    color: var(--accent);
  }
  .attribution {
    position: absolute;
    left: var(--space-2);
    top: var(--space-2);
    font-size: max(9px, calc(var(--type-caption) * 0.66));
    color: rgba(255, 255, 255, 0.5);
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
    white-space: nowrap;
    pointer-events: none;
  }
  .waiting {
    margin: auto;
    color: var(--on-card-faint);
  }
  :global(.card.hero) .chips {
    left: var(--space-4);
    right: var(--space-4);
    bottom: var(--space-4);
  }
  :global(.card.hero) .chip {
    padding: 6px 16px;
    font-size: var(--type-sm);
  }
  :global(.card.hero) .attribution {
    left: var(--space-4);
    top: var(--space-4);
    font-size: var(--type-caption);
  }
</style>
