<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { rowCount, type Grid } from "../lib/grid";

  let { grid, tint }: { grid: Grid | null; tint: (card: string) => string } =
    $props();
  const rows = $derived(grid ? Math.max(1, rowCount(grid.items)) : 1);
</script>

<div
  class="thumb"
  aria-hidden="true"
  style:--cols={grid?.cols ?? 1}
  style:--rows={rows}
>
  {#if grid}
    {#each grid.items as item (item.card)}
      <span
        style:grid-column="{item.x + 1} / span {item.w}"
        style:grid-row="{item.y + 1} / span {item.h}"
        style:background={tint(item.card)}
      ></span>
    {/each}
  {:else}
    <em>Auto</em>
  {/if}
</div>

<style>
  .thumb {
    width: 72px;
    aspect-ratio: 16 / 9;
    flex: none;
    display: grid;
    grid-template-columns: repeat(var(--cols), minmax(0, 1fr));
    grid-template-rows: repeat(var(--rows), minmax(0, 1fr));
    gap: 2px;
    padding: 3px;
    border-radius: 6px;
    background: #050505;
    box-shadow: 0 0 0 1px var(--rule);
  }
  span {
    border-radius: 2px;
  }
  em {
    grid-column: 1 / -1;
    place-self: center;
    font-size: 11px;
    color: var(--soft);
  }
</style>
