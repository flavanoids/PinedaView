// SPDX-License-Identifier: Apache-2.0
// use:settle={value} — when a displayed value changes, the new figure eases up
// into place once instead of snapping. A transition, not an animation, so it
// still plays on an idle screen and can't be frozen mid-flight there.
import { effectiveTier, motion } from "./tier.svelte";

const DUR = 260;

export function settle(node: HTMLElement, value: string) {
  // Compare against the last value rather than trusting when update() fires:
  // skips same-value re-renders (the Cycler renders both layers continuously).
  let prev = value;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function play() {
    if (motion.reduced || effectiveTier() === "lite") return;
    clearTimeout(timer);
    // Park at the pre-state with no transition, commit it, then let a
    // transition ease back to the element's natural state.
    node.style.transition = "none";
    node.style.opacity = "0";
    node.style.transform = "translateY(0.35em)";
    node.getBoundingClientRect();
    node.style.transition = `opacity ${DUR}ms ease, transform ${DUR}ms cubic-bezier(0.2, 0.9, 0.3, 1.2)`;
    node.style.opacity = "";
    node.style.transform = "";
    timer = setTimeout(() => (node.style.transition = ""), DUR);
  }

  return {
    update(next: string) {
      if (next === prev) return;
      prev = next;
      play();
    },
    destroy() {
      clearTimeout(timer);
    },
  };
}
