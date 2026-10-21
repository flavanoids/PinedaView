// SPDX-License-Identifier: Apache-2.0
/**
 * The recipe takeover's step ladder: the step being read as large as it fits,
 * the one before it above and the one after it below, smaller and dimmed.
 * Moving one step slides the ladder (top, font-size and opacity transition
 * together); a jump crossfades.
 *
 * Heights are measured on a hidden copy of a step (`[data-measure]`), which
 * must never transition: a copy mid-animation reports the wrong height and
 * the steps overlap.
 */

/** Share of the ladder's height the current step may fill. */
const CURRENT_SHARE = 0.55;
/** Where the current step's top sits, as a share of the height — it stays
 * put from step to step, so the eye doesn't have to hunt for it. */
const ANCHOR = 0.25;
/** The steps either side, relative to the current one. */
const SIDE_SCALE = 0.52;
const PREV_OPACITY = 0.45;
const NEXT_OPACITY = 0.6;
/** Space between steps, relative to the current one's size. */
const GAP = 0.55;

export interface Place {
  top: number;
  size: number;
  opacity: number;
  /** "current" for the step being read; the rest are "side". */
  role: "current" | "side";
}

export interface Ladder {
  steps: Place[];
  /** "Last step", where the next step would be. */
  end: { top: number; size: number; opacity: number };
}

/**
 * Where each of `count` steps goes with `current` being read, in a ladder
 * `height` px tall. `size`/`side` are the current and side font sizes;
 * `currentHeight`/`prevHeight` those steps' measured heights at them.
 */
export function placeSteps(
  count: number,
  current: number,
  height: number,
  size: number,
  side: number,
  currentHeight: number,
  prevHeight: number,
): Ladder {
  const gap = Math.round(size * GAP);
  const curTop = Math.round(height * ANCHOR);
  const prevTop = curTop - gap - prevHeight;
  const nextTop = curTop + currentHeight + gap;
  // Steps off the ladder wait just past either end, so the next move slides
  // them in from the right side.
  const above = prevTop - gap - side * 4;
  const below = height + gap;
  const steps = Array.from({ length: count }, (_, i): Place => {
    const d = i - current;
    if (d === 0) return { top: curTop, size, opacity: 1, role: "current" };
    if (d === -1)
      return { top: prevTop, size: side, opacity: PREV_OPACITY, role: "side" };
    if (d === 1)
      return { top: nextTop, size: side, opacity: NEXT_OPACITY, role: "side" };
    return { top: d < 0 ? above : below, size: side, opacity: 0, role: "side" };
  });
  const last = current === count - 1;
  return {
    steps,
    end: {
      top: last ? nextTop : below,
      size: side,
      opacity: last ? NEXT_OPACITY * 0.8 : 0,
    },
  };
}

export interface LadderOptions {
  /** The step being read (0-based). */
  current: number;
  /** Anything that changes the steps' text, to re-measure on. */
  key?: unknown;
}

export function stepLadder(node: HTMLElement, options: LadderOptions) {
  let opts = options;
  let shown: LadderOptions | null = null;
  let frame = 0;

  function rem(): { rem: number; scale: number } {
    const root = getComputedStyle(document.documentElement);
    return {
      rem: parseFloat(root.fontSize) || 16,
      scale: parseFloat(root.getPropertyValue("--ui-scale")) || 1,
    };
  }

  function layout(animate: boolean): void {
    const height = node.clientHeight;
    const width = node.clientWidth;
    const measure = node.querySelector<HTMLElement>("[data-measure]");
    const els = [...node.querySelectorAll<HTMLElement>("[data-step]")];
    const end = node.querySelector<HTMLElement>("[data-end]");
    if (!height || !width || !measure || !els.length) return;
    const current = Math.min(Math.max(opts.current, 0), els.length - 1);
    const text = (i: number) => els[i]?.querySelector("p")?.textContent ?? "";

    function heightAt(i: number, size: number, role: Place["role"]): number {
      measure!.dataset.role = role;
      measure!.style.fontSize = `${size}px`;
      measure!.querySelector(".n")!.textContent = String(i + 1);
      measure!.querySelector("p")!.textContent = text(i);
      return measure!.offsetHeight;
    }

    // The current step: the largest size, to half a pixel, at which it fits
    // its share of the height.
    const { rem: r, scale } = rem();
    let lo = 1.8 * r * scale;
    let hi = Math.max(lo, Math.min(4.5 * r * scale, width * 0.09));
    if (heightAt(current, hi, "current") <= height * CURRENT_SHARE) lo = hi;
    while (hi - lo > 0.5) {
      const mid = (lo + hi) / 2;
      if (heightAt(current, mid, "current") <= height * CURRENT_SHARE) lo = mid;
      else hi = mid;
    }
    const size = lo;
    const side = Math.min(size, Math.max(1.45 * r * scale, size * SIDE_SCALE));
    const places = placeSteps(
      els.length,
      current,
      height,
      size,
      side,
      heightAt(current, size, "current"),
      current > 0 ? heightAt(current - 1, side, "side") : 0,
    );

    if (!animate) node.dataset.instant = "";
    els.forEach((el, i) => {
      const p = places.steps[i];
      if (!p) return;
      el.dataset.role = p.role;
      el.style.top = `${p.top}px`;
      el.style.fontSize = `${p.size}px`;
      el.style.opacity = String(p.opacity);
      el.setAttribute("aria-hidden", String(Math.abs(i - current) > 1));
    });
    if (end) {
      end.style.top = `${places.end.top}px`;
      end.style.fontSize = `${places.end.size}px`;
      end.style.opacity = String(places.end.opacity);
    }
    if (!animate) {
      void node.offsetHeight; // commit the jump before transitions come back
      delete node.dataset.instant;
    }
  }

  function run(): void {
    frame = 0;
    const prev = shown;
    shown = opts;
    const moved =
      prev !== null && prev.key === opts.key
        ? Math.abs(opts.current - prev.current)
        : 0;
    layout(moved === 1);
    // A jump (or new text) fades in rather than sliding through every step.
    if (moved > 1 || (prev !== null && prev.key !== opts.key)) {
      node.animate([{ opacity: 0 }, { opacity: 1 }], {
        duration: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? 0
          : 320,
        easing: "ease-out",
      });
    }
  }

  function schedule(): void {
    if (!frame) frame = requestAnimationFrame(run);
  }

  // A resize or a webfont arriving re-measures in place, without the slide.
  function refit(): void {
    if (shown) layout(false);
  }
  const observer = new ResizeObserver(refit);
  observer.observe(node);
  document.fonts?.addEventListener("loadingdone", refit);
  schedule();

  return {
    update(next: LadderOptions) {
      opts = next;
      schedule();
    },
    destroy() {
      observer.disconnect();
      document.fonts?.removeEventListener("loadingdone", refit);
      if (frame) cancelAnimationFrame(frame);
    },
  };
}
