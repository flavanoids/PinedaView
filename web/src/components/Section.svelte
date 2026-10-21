<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    id: string;
    title: string;
    hint?: string;
    /** Inner SVG markup (24×24, stroked) for the tile beside the title. */
    icon?: string;
    /** The tile's colour. */
    tint?: string;
    open: boolean;
    /** Filtered out by search: kept in the page (so its settings can still
        be found) but not shown. */
    hidden?: boolean;
    onToggle: () => void;
    children: Snippet;
  }
  let {
    id,
    title,
    hint,
    icon,
    tint = "#8e8e93",
    open,
    hidden = false,
    onToggle,
    children,
  }: Props = $props();
</script>

<section class="section" {hidden} data-section={id}>
  <h3>
    <button
      type="button"
      class="header"
      aria-expanded={open}
      aria-controls="{id}-body"
      onclick={onToggle}
    >
      {#if icon}
        <span class="tile" style="background: {tint}" aria-hidden="true">
          <!-- eslint-disable-next-line svelte/no-at-html-tags -- fixed icon markup from Settings.svelte, not user input -->
          <svg viewBox="0 0 24 24">{@html icon}</svg>
        </span>
      {/if}
      <span class="title">{title}</span>
      {#if hint}<span class="hint">{hint}</span>{/if}
      <span class="chev" class:open aria-hidden="true">›</span>
    </button>
  </h3>
  <div id="{id}-body" class="body" hidden={!open}>
    {@render children()}
  </div>
</section>

<style>
  .section {
    border-radius: 14px;
    background: color-mix(in srgb, var(--on-stage) 5%, transparent);
    overflow: hidden;
  }
  .section[hidden] {
    display: none;
  }
  h3 {
    margin: 0;
    font: inherit;
  }
  .header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    min-height: 3.25rem;
    padding: 0 var(--space-3);
    border: none;
    background: none;
    color: var(--on-stage);
    font: inherit;
    font-size: var(--type-sm);
    font-weight: 600;
    text-align: left;
    cursor: pointer;
  }
  .header:active {
    background: color-mix(in srgb, var(--on-stage) 6%, transparent);
  }
  .tile {
    flex: none;
    display: grid;
    place-items: center;
    width: 1.85rem;
    height: 1.85rem;
    border-radius: 8px;
    color: #fff;
  }
  .tile svg {
    width: 1.15rem;
    height: 1.15rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.9;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .title {
    flex: none;
  }
  .hint {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: right;
    font-weight: 400;
    color: var(--on-stage-soft);
    font-size: var(--type-caption);
  }
  .chev {
    margin-left: auto;
    font-size: 1.1rem;
    color: var(--on-stage-soft);
    transition: transform var(--dur-fast) var(--ease-spring);
  }
  .chev.open {
    transform: rotate(90deg);
  }
  .body {
    padding: 0 var(--space-3) var(--space-3);
  }
  .body[hidden] {
    display: none;
  }
</style>
