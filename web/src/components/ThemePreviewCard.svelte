<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Theme } from "@pinedaview/protocol";

  interface Props {
    theme: Theme;
    selected: boolean;
    onSelect: () => void;
    onEdit?: (theme: Theme) => void;
  }

  let { theme, selected, onSelect, onEdit }: Props = $props();

  const isGlass = $derived(theme.surface === "glass");
  const weatherColor = $derived(theme.cards?.weather ?? "#3a3732");
  const clockColor = $derived(theme.cards?.clock ?? "#282622");
  const affirmationColor = $derived(theme.cards?.affirmation ?? "#645e54");
</script>

<div
  role="radio"
  tabindex="0"
  aria-checked={selected}
  class="theme-card"
  class:selected
  onclick={onSelect}
  onkeydown={(e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect();
    }
  }}
>
  <div class="swatch-frame" style:background={theme.stage}>
    <div class="mini-cards">
      <div
        class="mini-card weather"
        class:glass={isGlass}
        style:background={weatherColor}
        style:color={theme.on_card}
      >
        <span class="mini-line" style:background={theme.on_card}></span>
        <span class="mini-line short" style:background={theme.on_card}></span>
      </div>
      <div class="mini-col">
        <div
          class="mini-card clock"
          class:glass={isGlass}
          style:background={clockColor}
          style:color={theme.on_card}
        >
          <span class="mini-dot" style:background={theme.on_card}></span>
        </div>
        <div
          class="mini-card quote"
          class:glass={isGlass}
          style:background={affirmationColor}
          style:color={theme.on_card}
        >
          <span class="mini-line" style:background={theme.on_card}></span>
        </div>
      </div>
    </div>
    <div
      class="accent-dot"
      style:background={theme.accent}
      title="Accent: {theme.accent}"
    ></div>
    {#if isGlass}
      <span class="glass-tag">Glass</span>
    {/if}
  </div>

  <div class="meta">
    <div class="header">
      <span class="label">{theme.label}</span>
      {#if theme.custom}
        <span class="custom-badge">Custom</span>
      {/if}
    </div>
    {#if theme.blurb}
      <p class="blurb">{theme.blurb}</p>
    {/if}

    {#if theme.custom && onEdit}
      <button
        type="button"
        class="edit-btn"
        onclick={(e) => {
          e.stopPropagation();
          onEdit(theme);
        }}
      >
        <svg
          viewBox="0 0 16 16"
          width="12"
          height="12"
          fill="none"
          stroke="currentColor"
          stroke-width="1.75"
        >
          <path d="M11.5 2.5l2 2L4.5 13.5H2.5v-2L11.5 2.5z" />
        </svg>
        Edit
      </button>
    {/if}
  </div>
</div>

<style>
  .theme-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    border-radius: 14px;
    border: 2px solid color-mix(in srgb, var(--on-stage) 10%, transparent);
    background: color-mix(in srgb, var(--on-stage) 3%, transparent);
    color: var(--on-stage);
    cursor: pointer;
    text-align: start;
    transition:
      border-color var(--dur-fast) ease,
      box-shadow var(--dur-fast) ease,
      transform var(--dur-fast) ease;
    user-select: none;
  }
  .theme-card:hover {
    border-color: color-mix(in srgb, var(--on-stage) 25%, transparent);
    transform: translateY(-1px);
  }
  .theme-card.selected {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .theme-card:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .swatch-frame {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 10;
    border-radius: 9px;
    overflow: hidden;
    padding: 8px;
    box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.2);
  }

  .mini-cards {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 5px;
    height: 100%;
  }

  .mini-col {
    display: grid;
    grid-template-rows: 1fr 1fr;
    gap: 5px;
  }

  .mini-card {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 3px;
    padding: 4px 5px;
    border-radius: 5px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  }
  .mini-card.glass {
    backdrop-filter: blur(4px);
    border: 1px solid rgba(255, 255, 255, 0.35);
  }

  .mini-line {
    display: block;
    height: 2px;
    width: 80%;
    border-radius: 1px;
    opacity: 0.55;
  }
  .mini-line.short {
    width: 50%;
  }
  .mini-dot {
    display: block;
    width: 4px;
    height: 4px;
    border-radius: 50%;
    opacity: 0.65;
  }

  .accent-dot {
    position: absolute;
    bottom: 6px;
    right: 6px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    box-shadow: 0 0 0 1.5px rgba(0, 0, 0, 0.25);
  }

  .glass-tag {
    position: absolute;
    top: 5px;
    right: 5px;
    font-size: 9px;
    font-weight: 600;
    line-height: 1;
    padding: 2px 5px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.3);
    color: #fff;
    backdrop-filter: blur(4px);
  }

  .meta {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }

  .label {
    font-size: var(--type-sm);
    font-weight: 600;
    line-height: 1.2;
  }

  .custom-badge {
    font-size: 10px;
    font-weight: 500;
    padding: 1px 6px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 20%, transparent);
    color: var(--accent);
  }

  .blurb {
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .edit-btn {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-top: 4px;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid color-mix(in srgb, var(--on-stage) 16%, transparent);
    background: color-mix(in srgb, var(--on-stage) 5%, transparent);
    color: var(--on-stage);
    font: inherit;
    font-size: 11px;
    cursor: pointer;
    transition: background var(--dur-fast) ease;
  }
  .edit-btn:hover {
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    border-color: var(--accent);
    color: var(--accent);
  }
</style>
