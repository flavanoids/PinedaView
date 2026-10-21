<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { motion } from "../lib/tier.svelte";

  // One trip corner to corner and back. Stepped from JS rather than a CSS
  // animation/transition: a full-viewport gradient repainting every frame is
  // the Pi cost this project keeps refusing, while a repaint every STEP_MS
  // moves each pixel's colour well under 1% — it reads as continuous drift.
  // Phase comes from the wall clock, so every screen drifts in step and a
  // reload picks up where it was.
  const CYCLE_MS = 8 * 60_000;
  const STEP_MS = 2_000;

  let el = $state<HTMLDivElement>();

  $effect(() => {
    const node = el;
    if (!node) return;
    if (motion.reduced) {
      node.style.backgroundPosition = "";
      return;
    }
    const tick = () => {
      const phase = (Date.now() % CYCLE_MS) / CYCLE_MS;
      const p = 50 - 50 * Math.cos(phase * 2 * Math.PI); // eases at both ends
      node.style.backgroundPosition = `${p.toFixed(2)}% ${p.toFixed(2)}%`;
    };
    tick();
    const id = setInterval(tick, STEP_MS);
    return () => clearInterval(id);
  });
</script>

<div class="drift" bind:this={el} aria-hidden="true"></div>

<style>
  /* Same slot as the day tint (above the canvas, below all chrome); App
     renders it first so the tint still washes over it. Colours come from
     the theme's own variables, so a theme change or the sundown night twin
     re-dyes it with no extra wiring. */
  .drift {
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background: linear-gradient(
      135deg,
      var(--stage) 0%,
      color-mix(in oklab, var(--stage) 80%, var(--accent)) 25%,
      var(--stage) 50%,
      color-mix(in oklab, var(--stage) 80%, var(--card-phrase)) 75%,
      var(--stage) 100%
    );
    background-size: 300% 300%;
    background-position: 50% 50%;
  }
</style>
