<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  A photo the household took on this same month/day in a past year. The
  server only puts this card in the stack when there's an actual match (see
  view.py's _has_memory_today) — most days won't have one in a few hundred
  photos, so there's no "no memory yet" placeholder state to design for here.
-->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import type { CardProps } from "./types";
  import { pick } from "./types";

  interface OnThisDayData {
    name?: string;
    yearsAgo?: number;
  }

  let { view, stale, hero }: CardProps = $props();
  const base = import.meta.env.VITE_API_URL ?? "";
  const memory = $derived(pick<OnThisDayData>(view, "onThisDay"));
  const photoUrl = $derived(
    memory?.name
      ? hero
        ? `${base}/api/photos/${encodeURIComponent(memory.name)}`
        : `${base}/api/photos/${encodeURIComponent(memory.name)}/thumb`
      : null,
  );
  const caption = $derived(
    memory?.yearsAgo === 1
      ? "1 year ago"
      : `${memory?.yearsAgo ?? 0} years ago`,
  );
</script>

<Card accent="generic" {stale} {hero} bleed={!!photoUrl}>
  {#if photoUrl}
    <div class="frame" class:hero-frame={hero}>
      <img class="photo" src={photoUrl} alt="" />
      <span class="chip" class:hero-chip={hero}>On this day · {caption}</span>
    </div>
  {/if}
</Card>

<style>
  .frame {
    position: relative;
    align-self: stretch;
    flex: 1;
    min-height: var(--cell-min);
    border-radius: inherit;
    overflow: hidden;
  }
  .photo {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .chip {
    position: absolute;
    left: var(--space-2);
    bottom: var(--space-2);
    padding: calc(0.2rem * var(--ui-scale)) calc(0.55rem * var(--ui-scale));
    border-radius: var(--radius-pill);
    background: rgba(15, 13, 19, 0.62);
    backdrop-filter: blur(8px);
    color: #e8e4ec;
    font-size: var(--type-caption);
    font-weight: var(--weight-label);
  }
  .chip.hero-chip {
    left: var(--space-4);
    bottom: var(--space-4);
    padding: 6px 16px;
    font-size: var(--type-sm);
    background: rgba(15, 13, 19, 0.75);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  }
</style>
