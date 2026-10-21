<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The outline of a card's content while its data is on the way — so the
  dashboard keeps its shape instead of filling with "Waiting…" lines. Static
  (no shimmer) to spare the Pi. If nothing comes for a while the words show
  too, so a card that never fills says why.
-->
<script lang="ts">
  interface Props {
    /** What's on the way, as a sentence: "Waiting for the forecast…". */
    label: string;
    /** A big reading over two lines, a list of rows, or one block (a map). */
    shape?: "reading" | "list" | "map";
  }
  let { label, shape = "reading" }: Props = $props();

  let slow = $state(false);
  $effect(() => {
    const timer = setTimeout(() => (slow = true), 20_000);
    return () => clearTimeout(timer);
  });
</script>

<div class="placeholder {shape}" role="status">
  {#if shape === "map"}
    <span class="bar block" aria-hidden="true"></span>
  {:else if shape === "list"}
    {#each [0, 1, 2] as i (i)}
      <span class="bar row" aria-hidden="true"></span>
    {/each}
  {:else}
    <span class="bar big" aria-hidden="true"></span>
    <span class="bar" style="width: 70%" aria-hidden="true"></span>
    <span class="bar" style="width: 50%" aria-hidden="true"></span>
  {/if}
  <span class:visually-hidden={!slow} class="label">{label}</span>
</div>

<style>
  .placeholder {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-height: 0;
    flex: 1;
  }
  .bar {
    display: block;
    height: 0.9em;
    border-radius: 6px;
    background: color-mix(in srgb, currentColor 10%, transparent);
  }
  .big {
    width: 40%;
    height: 2.4em;
    border-radius: 10px;
  }
  .row {
    height: 1.4em;
  }
  .block {
    flex: 1;
    min-height: 4em;
    border-radius: 12px;
  }
  .label {
    font-size: var(--type-caption);
    color: var(--on-card-faint);
  }
</style>
