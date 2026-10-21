// SPDX-License-Identifier: Apache-2.0
/**
 * FLIP motion for the stage grid: when a settings change (or a drag in edit
 * mode) adds, removes, reorders or re-spans cards, each cell glides from where
 * it was to where it now sits, new cells fade up in place, and removed cells
 * fade out while the others close the gap. The first render staggers every
 * cell in, in reading order.
 *
 * Transform and opacity only, so every frame is a compositor blend. It runs
 * on the Lite tier too (the Pi kiosk is Lite by detection): these are
 * one-shot moves that answer a change, not ambient motion, and they cost a
 * fraction of a second each time. Reduced motion, battery saver and an
 * explicit Lite choice turn them off.
 */
import type { TransitionConfig } from "svelte/transition";
import { motion } from "./tier.svelte";

export type Rects = Map<string, DOMRect>;

const ID = "cell-motion";
const SWIFT = "cubic-bezier(0.22, 1, 0.36, 1)";
const CELLS = ":scope > [data-cell]:not([data-leaving])";

export function cellMotionOn(): boolean {
  return !motion.reduced && !motion.batterySaver && motion.choice !== "lite";
}

function cells(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(CELLS)];
}

/** Where every cell is on screen right now, mid-animation included. */
export function measure(root: HTMLElement): Rects {
  const out: Rects = new Map();
  for (const el of cells(root)) {
    out.set(el.dataset.cell ?? "", el.getBoundingClientRect());
  }
  return out;
}

interface PlayOptions {
  /** First render: stagger everything in rather than diffing. */
  first: boolean;
  /** Shorter moves while a card is being dragged around in edit mode. */
  quick: boolean;
  /** The cell under the pointer — its own drag styling owns its transform. */
  skip?: string | null;
  /** Grow and shrink resized cells from their old box instead of sliding
   *  them at the new size. Only for cells with a line of text at most (the
   *  Settings miniature): the text inside is hidden until the cell lands. */
  morph?: boolean;
}

export function play(
  root: HTMLElement,
  before: Rects | null,
  { first, quick, skip, morph = false }: PlayOptions,
): void {
  if (typeof root.animate !== "function") return; // no Web Animations (jsdom)
  const els = cells(root);
  // Drop any move still in flight so the measurement below is the resting
  // spot; `before` already holds the in-flight position to start from.
  for (const el of els) {
    for (const a of el.getAnimations({ subtree: true }))
      if (a.id === ID) a.cancel();
  }
  const after = els.map((el) => [el, el.getBoundingClientRect()] as const);

  if (first) {
    const minTop = Math.min(...after.map(([, a]) => a.top));
    const minLeft = Math.min(...after.map(([, a]) => a.left));
    const withDist = after.map(([el, a]) => {
      const dist = Math.hypot(a.left - minLeft, a.top - minTop);
      return { el, dist };
    });
    withDist.sort((a, b) => a.dist - b.dist);

    withDist.forEach(({ el, dist }) => {
      const delay = Math.min(dist * 0.22, 520);
      el.animate(
        [
          { opacity: 0, transform: "translateY(16px) scale(0.96)" },
          { opacity: 1, transform: "none" },
        ],
        {
          id: ID,
          duration: 480,
          delay,
          easing: "cubic-bezier(0.16, 1, 0.3, 1)",
          fill: "backwards",
        },
      );
    });
    return;
  }

  const duration = quick ? 220 : 380;
  for (const [el, to] of after) {
    const id = el.dataset.cell ?? "";
    if (id === skip) continue;
    const from = before?.get(id);
    if (!from) {
      // New card: arrives just after its neighbours start making room.
      el.animate(
        [
          { opacity: 0, transform: "scale(0.94)" },
          { opacity: 1, transform: "none" },
        ],
        {
          id: ID,
          duration: 340,
          delay: quick ? 0 : 120,
          easing: SWIFT,
          fill: "backwards",
        },
      );
      continue;
    }
    const dx = from.left - to.left;
    const dy = from.top - to.top;
    // A width or height change can't be scaled without squashing the text,
    // so the cell slides at its new size and its contents settle in.
    const resized =
      Math.abs(from.width - to.width) > to.width * 0.08 ||
      Math.abs(from.height - to.height) > to.height * 0.08;
    if (Math.abs(dx) < 1 && Math.abs(dy) < 1 && !resized) continue;
    if (morph && resized) {
      const sx = from.width / Math.max(1, to.width);
      const sy = from.height / Math.max(1, to.height);
      el.animate(
        [
          {
            transformOrigin: "0 0",
            transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
          },
          { transformOrigin: "0 0", transform: "none" },
        ],
        { id: ID, duration: duration + 80, easing: SWIFT },
      );
      for (const child of el.children) {
        child.animate(
          [{ opacity: 0 }, { opacity: 0, offset: 0.55 }, { opacity: 1 }],
          {
            id: ID,
            duration: duration + 80,
          },
        );
      }
      continue;
    }
    el.animate(
      [
        {
          transform: `translate(${dx}px, ${dy}px)`,
          opacity: resized ? 0.5 : 1,
        },
        { transform: "none", opacity: 1 },
      ],
      { id: ID, duration, easing: SWIFT },
    );
  }
}

/**
 * Outro for a removed cell. Lifts it out of the grid at its current spot so
 * the remaining cells can flow into the space while it fades.
 */
export function leave(node: HTMLElement): TransitionConfig {
  if (!cellMotionOn()) return { duration: 0 };
  const { offsetLeft, offsetTop, offsetWidth, offsetHeight } = node;
  node.dataset.leaving = "";
  Object.assign(node.style, {
    position: "absolute",
    gridArea: "auto",
    left: `${offsetLeft}px`,
    top: `${offsetTop}px`,
    width: `${offsetWidth}px`,
    height: `${offsetHeight}px`,
    margin: "0",
    pointerEvents: "none",
  });
  return {
    duration: 240,
    css: (t) => `opacity: ${t}; transform: scale(${0.95 + 0.05 * t})`,
  };
}

/**
 * 60fps FLIP animation to expand a card from its grid tile into the hero spotlight.
 */
export function animateHeroExpand(
  heroEl: HTMLElement,
  sourceEl: HTMLElement,
): Animation | null {
  if (typeof heroEl.animate !== "function") return null;
  if (!cellMotionOn()) {
    return heroEl.animate([{ opacity: 0 }, { opacity: 1 }], {
      duration: 250,
      easing: "ease-out",
      fill: "both",
    });
  }
  const from = sourceEl.getBoundingClientRect();
  const to = heroEl.getBoundingClientRect();
  const dx = from.left - to.left;
  const dy = from.top - to.top;
  const sx = from.width / Math.max(1, to.width);
  const sy = from.height / Math.max(1, to.height);

  return heroEl.animate(
    [
      {
        transformOrigin: "0 0",
        transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
        opacity: 0.85,
      },
      {
        transformOrigin: "0 0",
        transform: "none",
        opacity: 1,
      },
    ],
    {
      id: ID,
      duration: 440,
      easing: "cubic-bezier(0.16, 1, 0.3, 1)",
      fill: "both",
    },
  );
}

/**
 * 60fps FLIP animation to contract an expanded hero card back into its home grid tile.
 */
export function animateHeroContract(
  heroEl: HTMLElement,
  sourceEl: HTMLElement,
): Animation | null {
  if (typeof heroEl.animate !== "function") return null;
  if (!cellMotionOn()) {
    return heroEl.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: 250,
      easing: "ease-in",
      fill: "both",
    });
  }
  const to = sourceEl.getBoundingClientRect();
  const from = heroEl.getBoundingClientRect();
  const dx = to.left - from.left;
  const dy = to.top - from.top;
  const sx = to.width / Math.max(1, from.width);
  const sy = to.height / Math.max(1, from.height);

  return heroEl.animate(
    [
      {
        transformOrigin: "0 0",
        transform: "none",
        opacity: 1,
      },
      {
        transformOrigin: "0 0",
        transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
        opacity: 0.2,
      },
    ],
    {
      id: ID,
      duration: 380,
      easing: "cubic-bezier(0.16, 1, 0.3, 1)",
      fill: "both",
    },
  );
}
