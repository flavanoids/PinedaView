<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Snippet } from "svelte";

  import { motion } from "../lib/tier.svelte";

  interface Props {
    flipped: boolean;
    front: Snippet;
    back: Snippet;
  }
  let { flipped, front, back }: Props = $props();
  const rotate = $derived(motion.tier !== "lite");
</script>

<div class="scene">
  <div class="flip" class:flipped class:rotate>
    <div class="face front">{@render front()}</div>
    <div class="face back">{@render back()}</div>
  </div>
</div>

<style>
  /* Both faces share one grid cell, so the box grows to the taller of the two
     rather than collapsing (absolute-positioned faces used to contribute no
     height, which starved the card's row). */
  .scene {
    perspective: 1200px;
    width: 100%;
  }
  .flip {
    display: grid;
    width: 100%;
    transform-style: preserve-3d;
  }
  .flip.rotate {
    transition: transform var(--dur-mid) var(--ease-spring);
  }
  .flip.rotate.flipped {
    transform: rotateY(180deg);
  }
  .face {
    grid-area: 1 / 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    backface-visibility: hidden;
  }
  .back {
    transform: rotateY(180deg);
  }
  /* Lite: no 3D, just show the current face */
  .flip:not(.rotate) .back {
    display: none;
    transform: none;
  }
  .flip:not(.rotate).flipped .front {
    display: none;
  }
  .flip:not(.rotate).flipped .back {
    display: flex;
  }
</style>
