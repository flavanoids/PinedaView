<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The clock view's running timers: a small slab of glass in the bottom-left
  corner (the music card has the bottom-right), only while a timer, alarm or
  reminder is set. One row each, soonest first: a name if it was given one,
  then a countdown for a timer, or when it goes off for an alarm. A new one
  grows the slab, then fades in; one that rings fades out as the slab
  shrinks, and the rows it held apart slide together. It leaves when the
  last one rings or is cancelled.
-->
<script lang="ts">
  import { cubicOut } from "svelte/easing";
  import { fade } from "svelte/transition";
  import type { TimerEntry } from "../cards/types";
  import { alarmTime, formatCountdown } from "../lib/format";
  import { remaining } from "../lib/time.svelte";
  import { motion } from "../lib/tier.svelte";

  let {
    timers,
    el = $bindable(null),
  }: {
    timers: TimerEntry[];
    /** The slab, for the Photo Clock to put its live glass behind (as
        MiniNowPlaying). */
    el?: HTMLElement | null;
  } = $props();

  /** The slab's glide to a new size (its CSS transition, below), which
      the rows' slides share. */
  const GROW_MS = 560;
  const GROW_EASE = "cubic-bezier(0.32, 0.72, 0, 1)";
  const ms = (n: number) => (motion.reduced ? 0 : n);

  const running = $derived(
    timers
      .map((t) => {
        const left = remaining(t.fires_at);
        const at =
          t.kind === "alarm" || t.kind === "reminder"
            ? alarmTime(t.fires_at)
            : null;
        return {
          id: t.id,
          name: t.name?.trim() ?? "",
          left,
          at,
          text: at ?? formatCountdown(left.totalSeconds),
        };
      })
      .filter((t) => !t.left.done)
      .sort((a, b) => a.left.totalSeconds - b.left.totalSeconds),
  );
  // The slab fades out on the last list it showed, not on an empty one.
  let last: typeof running = [];
  const shown = $derived.by(() => {
    if (running.length) last = running;
    return last;
  });

  /** A countdown a character a slot, keyed from the right so the seconds
      keep their slot as the minutes lose a digit: only what changed fades. */
  const slots = (text: string) =>
    [...text]
      .reverse()
      .map((c, i) => ({ c, i }))
      .reverse();

  // Every alarm's colon breathes in step, whenever its row arrived.
  const inStep = () => `${-(performance.now() % 2000)}ms`;

  // The slab's size follows the list's, gliding there; not on the first
  // paint, where it arrives at its size.
  let listW = $state(0);
  let listH = $state(0);
  let settled = $state(false);
  $effect(() => {
    const id = requestAnimationFrame(() =>
      requestAnimationFrame(() => (settled = true)),
    );
    return () => cancelAnimationFrame(id);
  });

  // The glass behind is baked once with room for about four rows and a
  // long name, as the slab first fades in, so growing never waits on a
  // bake (PhotoClock reads data-glass-room).
  let em = $state(16);
  $effect(() => {
    if (el) em = parseFloat(getComputedStyle(el).fontSize) || 16;
  });

  // Each cell slides from where it sat to where it sits now, on the slab's
  // own curve: rows moving for one that came or went, a time making way
  // for a new name. Only moves, never scales (svelte's flip would squash a
  // row whose width changed).
  let listEl = $state<HTMLElement | null>(null);
  let snap = new Map<string, [number, number]>();
  let snapOf: HTMLElement | null = null;

  /** Each cell's place from the list's bottom left (the corner the slab
      grows from), untouched by any slide under way. */
  function layout(list: HTMLElement): Map<string, [number, number]> {
    const at = new Map<string, [number, number]>();
    for (const c of list.querySelectorAll<HTMLElement>("[data-cell]"))
      at.set(c.dataset.cell!, [c.offsetLeft, c.offsetTop - list.offsetHeight]);
    return at;
  }

  function slide(): void {
    const list = listEl;
    if (!list) return;
    const now = layout(list);
    if (snapOf === list && !motion.reduced) {
      for (const c of list.querySelectorAll<HTMLElement>("[data-cell]")) {
        const was = snap.get(c.dataset.cell!);
        const [x, y] = now.get(c.dataset.cell!)!;
        if (!was) continue;
        const dx = was[0] - x;
        const dy = was[1] - y;
        if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
        c.animate(
          [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
          { duration: GROW_MS, easing: GROW_EASE },
        );
      }
    }
    snap = now;
    snapOf = list;
  }
  // After each change to the list; and once a row that rang has faded out
  // and left, for the rows it held apart.
  $effect(() => {
    void shown;
    slide();
  });
  const gone = () => requestAnimationFrame(slide);

  // As MiniNowPlaying: no scale, and the glass follows frame by frame.
  function leave(node: HTMLElement, { duration }: { duration: number }) {
    node.dispatchEvent(new Event("glass:move"));
    return { duration, css: (t: number) => `opacity: ${t}` };
  }
  function arrive(node: HTMLElement, { duration }: { duration: number }) {
    node.dispatchEvent(new Event("glass:move"));
    return {
      duration,
      easing: cubicOut,
      css: (t: number) =>
        `opacity: ${t}; transform: translateY(${(1 - t) * 12}px)`,
    };
  }

  /** A new row waits for most of the slab's growing, then fades in. */
  function grown(_node: HTMLElement) {
    const wait = ms(GROW_MS * 0.6);
    const show = ms(420);
    return {
      duration: wait + show,
      css: (t: number) => {
        const k = Math.max(0, (t * (wait + show) - wait) / (show || 1));
        return `opacity: ${k * k * (3 - 2 * k)}`;
      },
    };
  }
</script>

{#if running.length}
  <div
    class="mini"
    class:settled
    bind:this={el}
    style:width={listW ? `${listW}px` : undefined}
    style:height={listH ? `${listH}px` : undefined}
    data-glass-room="{Math.round(18 * em)},{Math.round(6.75 * em)}"
    role="timer"
    aria-label={shown
      .map((t) => (t.name ? `${t.name}: ${t.text}` : t.text))
      .join(", ")}
    in:arrive={{ duration: ms(520) }}
    out:leave={{ duration: ms(360) }}
  >
    <div
      class="list"
      aria-hidden="true"
      bind:this={listEl}
      bind:offsetWidth={listW}
      bind:offsetHeight={listH}
    >
      {#each shown as t (t.id)}
        <div
          class="row"
          in:grown
          out:fade={{ duration: ms(260) }}
          onoutroend={gone}
        >
          <span class="icon" data-cell="{t.id}:icon"
            ><svg viewBox="0 0 24 24">
              {#if t.at}
                <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
                <path d="M10 20.5a2 2 0 0 0 4 0" />
              {:else}
                <circle cx="12" cy="13.5" r="7.5" />
                <path d="M12 13.5V9.5M10 3h4" />
              {/if}
            </svg></span
          >
          <span class="name" class:named={t.name} data-cell="{t.id}:name"
            >{t.name}</span
          >
          <b data-cell="{t.id}:time">
            {#if t.at}
              {@const [hh, mm] = t.at.split(/:(.*)/s)}
              {hh}<span class="colon" style:animation-delay={inStep()}>:</span
              >{mm}
            {:else}
              {#each slots(t.text) as d (d.i)}
                <span class="slot">
                  {#key d.c}
                    <span
                      in:fade={{ duration: ms(420) }}
                      out:fade={{ duration: ms(320) }}>{d.c}</span
                    >
                  {/key}
                </span>
              {/each}
            {/if}
          </b>
        </div>
      {/each}
    </div>
  </div>
{/if}

<style>
  /* The music card's glass: the photo bends through it. One row is a pill;
     more stretch it taller, its ends keeping the pill's rounding. */
  .mini {
    --edge: min(5vh, 40px);
    --pad: 0.4em;
    --line: 1.3em;
    --radius: calc(var(--pad) + var(--line) / 2);
    position: fixed;
    left: calc(var(--edge) + var(--frame-x, 0px));
    bottom: calc(var(--edge) + var(--frame-y, 0px));
    z-index: 12;
    overflow: hidden;
    pointer-events: none;
    border-radius: var(--radius);
    font-family: var(--font-body, -apple-system, sans-serif);
    font-size: clamp(0.95rem, 1.85vmin, 1.9rem);
    color: #fff;
    text-shadow: 0 1px 6px rgb(0 0 0 / 0.25);
    background:
      linear-gradient(
        160deg,
        rgb(255 255 255 / 0.2),
        rgb(255 255 255 / 0.04) 45%,
        rgb(255 255 255 / 0.08)
      ),
      rgb(32 36 44 / 0.3);
    backdrop-filter: blur(22px) saturate(1.7) brightness(0.92);
    -webkit-backdrop-filter: blur(22px) saturate(1.7) brightness(0.92);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.42),
      inset 0 0 0 1px rgb(255 255 255 / 0.16),
      inset 0 -1px 0 rgb(0 0 0 / 0.14),
      0 1vmin 3.5vmin rgb(0 0 0 / 0.32);
  }
  /* iOS's sheet curve, as the music card: quick to start, a long soft
     landing. */
  .mini.settled {
    transition:
      width 560ms cubic-bezier(0.32, 0.72, 0, 1),
      height 560ms cubic-bezier(0.32, 0.72, 0, 1);
  }
  /* The Photo Clock's live glass is behind it, as behind the music card:
     only a light scrim inside the rim for the text. The rim is half the
     rounding, as PhotoClock bakes it. */
  .mini:global([data-live-glass]) {
    background: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    box-shadow: none;
  }
  .mini:global([data-live-glass])::before {
    --rim: calc(var(--radius) * 0.5);
    inset: calc(var(--rim) * 0.7);
    border-radius: calc(var(--radius) - var(--rim) * 0.7);
    background: rgb(0 0 0 / 0.24);
    box-shadow: 0 0 calc(var(--rim) * 0.8) calc(var(--rim) * 0.25)
      rgb(0 0 0 / 0.24);
  }
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

  /* Laid out at its own size, from the slab's bottom left, so the slab can
     glide to it. Icon, name, time: a name column as wide as the longest
     name, blank on the rows without one. */
  .list {
    position: absolute;
    left: 0;
    bottom: 0;
    width: max-content;
    display: grid;
    grid-template-columns: auto auto auto;
    row-gap: 0.25em;
    padding: var(--pad) 0.85em var(--pad) 0.7em;
  }
  .row {
    display: grid;
    grid-column: 1 / -1;
    grid-template-columns: subgrid;
    align-items: center;
    height: var(--line);
  }
  .icon {
    display: flex;
    margin-right: 0.45em;
  }
  svg {
    width: 1.05em;
    height: 1.05em;
    fill: none;
    stroke: rgb(255 255 255 / 0.85);
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .name {
    max-width: 12em;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    color: rgb(255 255 255 / 0.78);
  }
  /* Antigua sends names as said ("pasta"). */
  .name::first-letter {
    text-transform: uppercase;
  }
  .name.named {
    margin-right: 0.6em;
  }
  b {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  /* The old and new character share the slot while they cross-fade. */
  .slot {
    display: inline-grid;
  }
  .slot > span {
    grid-area: 1 / 1;
  }
  /* An alarm's time breathes at its colon, slowly. */
  .colon {
    animation: breathe 2s ease-in-out infinite;
  }
  @keyframes breathe {
    50% {
      opacity: 0.4;
    }
  }
  :global(:root[data-reduce-motion="true"]) .colon {
    animation: none;
  }
</style>
