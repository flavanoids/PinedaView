// SPDX-License-Identifier: Apache-2.0
/**
 * Alternate mode's handoff (components/Alternate): the Photo Clock gives way
 * to the cards, and later the cards give way back, in about 2 s. Going to the
 * cards, the photo slides off to the left, the cards slide in from the right
 * in a staggered wave formation, and each glass figure flies along a gentle
 * parabolic arc into the clock card, crossfading into that card's own Fraunces
 * figure as it docks. Going back runs the mirrored expansion, blooming the figures
 * out into the full-screen photo clock. Only transform and opacity move, so the
 * Pi's GPU composites every frame at 60 fps.
 */

export const HANDOFF_MS = 2000;
export const SETTLE = "cubic-bezier(0.16, 1, 0.3, 1)";
export const DEPART = "cubic-bezier(0.4, 0, 0.2, 1)";
export const FLIGHT = "cubic-bezier(0.22, 1, 0.36, 1)";

/** [start, length] as fractions of the handoff. */
export type Span = [number, number];

/** When each part moves on the way to the cards: the photo, the glass
 *  swapping for its stand-ins, each card cell (left to right) and each
 *  figure (left to right). Everything lands by the end. */
export function schedule(
  cells: number,
  figures: number,
): { photo: Span; swap: Span; cells: Span[]; figures: Span[] } {
  const stagger = cells > 1 ? Math.min(0.035, 0.33 / (cells - 1)) : 0;
  const lag = figures > 1 ? Math.min(0.03, 0.12 / (figures - 1)) : 0;
  return {
    photo: [0, 0.55],
    swap: [0, 0.06],
    cells: Array.from({ length: cells }, (_, i): Span => [
      0.12 + i * stagger,
      0.5,
    ]),
    figures: Array.from({ length: figures }, (_, i): Span => [
      0.1 + i * lag,
      0.75,
    ]),
  };
}

/** The same span run backwards in time, for the way back to the clock. */
export const mirror = ([start, length]: Span): Span => [
  1 - start - length,
  length,
];

/** Keyframes run backwards (each offset mirrored, the order reversed). */
export function reverse(frames: Keyframe[]): Keyframe[] {
  return frames
    .map((k) => ({ ...k, offset: 1 - (k.offset as number) }))
    .reverse();
}

export interface Handoff {
  /** Resolves when everything has landed. */
  done: Promise<void>;
  /** Drop the animations and the stand-ins. Call once the outgoing view is
   *  unmounted, so its resting place never shows for a frame. */
  settle: () => void;
}

interface Layers {
  /** The Photo Clock's layer (it slides). */
  clock: HTMLElement;
  /** The card grid's layer (its `[data-cell]`s slide). */
  cards: HTMLElement;
  /** An empty full-screen layer above both, for the flying figures. */
  flight: HTMLElement;
}

export function handoff(
  to: "cards" | "clock",
  { clock, cards, flight }: Layers,
  { ms = HANDOFF_MS, reduced = false }: { ms?: number; reduced?: boolean } = {},
): Handoff {
  const forward = to === "cards";
  const anims: Animation[] = [];
  const restore: (() => void)[] = [];

  const play = (
    el: Element,
    frames: Keyframe[],
    span: Span,
    easing: string = FLIGHT,
    reverseEasing: string = easing,
  ): void => {
    const [start, length] = forward ? span : mirror(span);
    const chosenEasing = forward ? easing : reverseEasing;
    anims.push(
      el.animate(forward ? frames : reverse(frames), {
        duration: length * ms,
        delay: start * ms,
        easing: chosenEasing,
        fill: "both",
      }),
    );
  };

  if (reduced) {
    // Reduced motion: gentle cross-dissolve with no physical travel.
    play(
      clock,
      [
        { offset: 0, opacity: 1 },
        { offset: 1, opacity: 0 },
      ],
      [0, 1],
      "linear",
    );
  } else {
    const width = window.innerWidth;
    const rawCells = [...cards.querySelectorAll<HTMLElement>("[data-cell]")];

    // Cancel any in-flight transitions on card cells (e.g. initial Stage cellMotion)
    // and promote them to GPU compositor layers for the duration of the handoff.
    for (const el of rawCells) {
      for (const a of el.getAnimations()) a.cancel();
      el.style.willChange = "transform, opacity";
      restore.push(() => {
        el.style.willChange = "";
      });
    }

    const cells = rawCells
      .map((el) => ({ el, box: el.getBoundingClientRect() }))
      .sort((a, b) => a.box.left - b.box.left || a.box.top - b.box.top);

    const pairs = figurePairs(clock, cards, flight);
    const plan = schedule(cells.length, pairs.length);

    // Photo Clock background transition:
    // Outgoing photo drifts left with subtle scale and soft opacity falloff.
    // Incoming photo settles with fluid deceleration (SETTLE) instead of slamming to a halt.
    const photoLeaveX = -Math.min(width * 0.5, 640);
    play(
      clock,
      [
        { offset: 0, transform: "none", opacity: 1 },
        { offset: 0.75, opacity: 0.8 },
        {
          offset: 1,
          transform: `translateX(${photoLeaveX}px) scale(0.985)`,
          opacity: 0,
        },
      ],
      plan.photo,
      DEPART,
      SETTLE,
    );

    // Cards assembly/disassembly:
    // Cards enter from the right as a cohesive, staggered wave. Each card travels
    // a proportional distance with tactile vertical settle and subtle scale,
    // avoiding chaotic cross-screen overlaps.
    cells.forEach(({ el, box }, i) => {
      const distFromRight = width - (box.left + box.width);
      const travelX = Math.min(
        width - box.left + 24,
        260 + Math.min(distFromRight * 0.15, 140),
      );
      play(
        el,
        [
          {
            offset: 0,
            transform: `translate(${travelX}px, 12px) scale(0.965)`,
            opacity: 0,
          },
          { offset: 0.28, opacity: 0.85 },
          { offset: 1, transform: "none", opacity: 1 },
        ],
        plan.cells[i]!,
        SETTLE,
        DEPART,
      );
    });

    if (pairs.length) {
      // Fade out the photo clock's glass digits and date capsule during swap
      clock
        .querySelectorAll(
          ".photo-clock .clock-layer, .photo-clock .date-capsule",
        )
        .forEach((layer) =>
          play(
            layer,
            [
              { offset: 0, opacity: 1 },
              { offset: 1, opacity: 0 },
            ],
            plan.swap,
            "linear",
          ),
        );

      // Hide the resting clock card figures until the flying figures dock
      const figs = cards.querySelector<HTMLElement>(
        '[data-cell="clock"] .figs',
      );
      if (figs) {
        figs.style.visibility = "hidden";
        restore.push(() => (figs.style.visibility = ""));
      }

      // Parabolic arc flight:
      // - `big` (crisp, high-res liquid glass) carries the flight through an upward arc.
      // - `small` crossfades in near the destination at ~1:1 scale (zero font upscaling blur).
      // - Reversed: `small` lifts off, blooms into `big`, which ascends the arc and expands full size.
      pairs.forEach(({ big, small, dx, dy, k, midX, midY, midK }, i) => {
        const span = plan.figures[i]!;
        const mid = `translate(${midX}px, ${midY}px) scale(${midK})`;
        const there = `translate(${dx}px, ${dy}px) scale(${k})`;

        play(
          big,
          [
            { offset: 0, transform: "none", opacity: 1 },
            { offset: 0.48, transform: mid, opacity: 1 },
            { offset: small ? 0.82 : 0.65, opacity: small ? 0.35 : 0 },
            { offset: 1, transform: there, opacity: 0 },
          ],
          span,
          FLIGHT,
        );

        if (small) {
          const smallMid = `translate(${midX - dx}px, ${midY - dy}px) scale(${midK / k})`;
          play(
            small,
            [
              { offset: 0, transform: smallMid, opacity: 0 },
              { offset: 0.52, opacity: 0 },
              { offset: 0.82, opacity: 0.85 },
              { offset: 1, transform: "none", opacity: 1 },
            ],
            span,
            FLIGHT,
          );
        }
      });
    }
  }

  return {
    done: Promise.all(anims.map((a) => a.finished)).then(() => undefined),
    settle: () => {
      anims.forEach((a) => a.cancel());
      restore.forEach((r) => r());
      flight.replaceChildren();
    },
  };
}

interface Pair {
  /** The glass figure's stand-in, where the Photo Clock draws it. */
  big: HTMLElement;
  /** The card figure's stand-in, where the card draws it; none for the
   *  colon, which the card leaves out. */
  small: HTMLElement | null;
  /** How far `big` travels, and how much it shrinks, to land on `small`. */
  dx: number;
  dy: number;
  k: number;
  /** Parabolic arc apex parameters for fluid, buoyant 3D trajectory. */
  midX: number;
  midY: number;
  midK: number;
}

/**
 * Stand-ins for each figure of the Photo Clock's time (`9:15`) and of the
 * clock card's stacked hour and minutes (`9` over `15`), laid exactly over
 * the real ones in `flight`. Empty when either isn't on screen (a round
 * Photo Clock, the clock card switched off or showing another face), and
 * then only the photo and the cards move.
 */
function figurePairs(
  clock: HTMLElement,
  cards: HTMLElement,
  flight: HTMLElement,
): Pair[] {
  const glass = clock.querySelector<HTMLElement>(".photo-clock .digits");
  const hh = cards.querySelector<HTMLElement>('[data-cell="clock"] .figs .hh');
  const mm = cards.querySelector<HTMLElement>('[data-cell="clock"] .figs .mm');
  if (!glass || !hh || !mm) return [];
  const from = glyphs(glass);
  const to = [...glyphs(hh), ...glyphs(mm)];
  if (from.filter((g) => g.char !== ":").length !== to.length) return [];

  // Batch DOM measurements first (zero layout thrashing)
  const glassFont = { ...font(glass), color: "" };
  const cardFont = font(hh);

  const hhBox = hh.getBoundingClientRect();
  const mmBox = mm.getBoundingClientRect();
  const gap = new DOMRect(
    (hhBox.left + hhBox.right) / 2 - 2,
    (hhBox.bottom + mmBox.top) / 2 - 2,
    4,
    4,
  );

  let next = 0;
  const frag = document.createDocumentFragment();

  const pairs: Pair[] = from.map(({ char, box }) => {
    const target = char === ":" ? null : to[next++]!;
    const big = standIn(char, box, glassFont, "glass");
    frag.appendChild(big);

    const small = target
      ? standIn(target.char, target.box, cardFont, "card")
      : null;
    if (small) frag.appendChild(small);

    const land = target?.box ?? gap;
    const dx = land.left + land.width / 2 - (box.left + box.width / 2);
    const dy = land.top + land.height / 2 - (box.top + box.height / 2);
    const k = target ? land.height / box.height : 0.2;

    // Organic parabolic arc calculation:
    // Figures lift slightly along the Y axis against gravity during transit.
    const dist = Math.hypot(dx, dy);
    const arcLift = Math.min(48, Math.max(16, dist * 0.035));
    const midX = dx * 0.48;
    const midY = dy * 0.44 - arcLift;
    const midK = 1 - (1 - k) * 0.45;

    return { big, small, dx, dy, k, midX, midY, midK };
  });

  // Single DOM insertion for all stand-ins
  flight.appendChild(frag);
  return pairs;
}

/** Each visible character of an element's text, with where it's drawn. */
function glyphs(el: HTMLElement): { char: string; box: DOMRect }[] {
  const out: { char: string; box: DOMRect }[] = [];
  const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  for (let node = walk.nextNode(); node; node = walk.nextNode()) {
    const text = node.textContent ?? "";
    for (let i = 0; i < text.length; i++) {
      if (!text[i]!.trim()) continue;
      range.setStart(node, i);
      range.setEnd(node, i + 1);
      out.push({ char: text[i]!, box: range.getBoundingClientRect() });
    }
  }
  return out;
}

/** The type an element is drawn in, at the size it's drawn (its CSS
 *  `scale` folded in, as the Photo Clock fits its figures with one). */
function font(el: HTMLElement): Partial<CSSStyleDeclaration> {
  const cs = getComputedStyle(el);
  const scale = Number.parseFloat(cs.scale) || 1;
  return {
    fontFamily: cs.fontFamily,
    fontWeight: cs.fontWeight,
    fontStyle: cs.fontStyle,
    fontSize: `${Number.parseFloat(cs.fontSize) * scale}px`,
    fontVariationSettings: cs.fontVariationSettings,
    fontOpticalSizing: cs.fontOpticalSizing,
    fontVariantNumeric: cs.fontVariantNumeric,
    color: cs.color,
  };
}

function standIn(
  char: string,
  box: DOMRect,
  type: Partial<CSSStyleDeclaration>,
  kind: "glass" | "card",
): HTMLElement {
  const el = document.createElement("span");
  el.className = `handoff-fig ${kind}`;
  el.textContent = char;
  Object.assign(el.style, type, {
    left: `${box.left}px`,
    top: `${box.top}px`,
    width: `${box.width}px`,
    height: `${box.height}px`,
    lineHeight: `${box.height}px`,
    transformOrigin: "center center",
  });
  return el;
}
