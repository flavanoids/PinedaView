// SPDX-License-Identifier: Apache-2.0
/**
 * Size text to its box: the largest font-size, between a floor and a ceiling,
 * at which the node's content still fits its own height and width. For cards
 * whose text length varies a lot from item to item (a one-line phrase vs. a
 * three-sentence quote), where any fixed size is either lost in empty space
 * or spills out of the tile.
 *
 * The node needs a definite size to fit into (a flex/grid child with
 * `min-height: 0`), and its children size themselves in `em` off the
 * font-size set here. Bounds are in rem and scale with --ui-scale; the ceiling
 * is also capped by width so a phone's content-height card (where every size
 * "fits") still gets a sensible size rather than the maximum.
 */
export interface FitOptions {
  /** Smallest font-size, rem (before --ui-scale). */
  min: number;
  /** Largest font-size, rem (before --ui-scale). */
  max: number;
  /** Ceiling as a fraction of the box's width, px per px. */
  maxOfWidth: number;
  /** Anything that changes the content (the text itself), to re-fit on. */
  key?: unknown;
}

export function fitText(node: HTMLElement, options: FitOptions) {
  let opts = options;
  let frame = 0;

  function fits(): boolean {
    return (
      node.scrollHeight <= node.clientHeight + 1 &&
      node.scrollWidth <= node.clientWidth + 1
    );
  }

  function fit(): void {
    frame = 0;
    const width = node.clientWidth;
    if (!width) return;
    const root = getComputedStyle(document.documentElement);
    const rem = parseFloat(root.fontSize) || 16;
    const scale = parseFloat(root.getPropertyValue("--ui-scale")) || 1;
    const lo0 = opts.min * rem * scale;
    const hi0 = Math.max(
      lo0,
      Math.min(opts.max * rem * scale, width * opts.maxOfWidth),
    );
    // Binary search to half a pixel — ~6 layouts, only when the text or the
    // box changes, not per frame.
    let lo = lo0;
    let hi = hi0;
    node.style.fontSize = `${hi}px`;
    if (!fits()) {
      while (hi - lo > 0.5) {
        const mid = (lo + hi) / 2;
        node.style.fontSize = `${mid}px`;
        if (fits()) lo = mid;
        else hi = mid;
      }
      node.style.fontSize = `${lo}px`;
    }
  }

  function schedule(): void {
    if (!frame) frame = requestAnimationFrame(fit);
  }

  // Our own font-size change never resizes the node's box (its size comes
  // from its parent), so observing it doesn't loop.
  const observer = new ResizeObserver(schedule);
  observer.observe(node);
  // A webfont swapping in changes every line's width.
  void document.fonts?.ready.then(schedule);
  schedule();

  return {
    update(next: FitOptions) {
      opts = next;
      schedule();
    },
    destroy() {
      observer.disconnect();
      if (frame) cancelAnimationFrame(frame);
    },
  };
}
