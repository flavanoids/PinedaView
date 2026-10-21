<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { fade, scale } from "svelte/transition";
  import { createClient, type components } from "@pinedaview/protocol";

  type Takeover = components["schemas"]["Takeover"];
  type ImageSearch = components["schemas"]["ImageSearchTakeover"];
  type ImageItem = components["schemas"]["ImageItem"];

  interface Props {
    takeover: Takeover;
  }
  let { takeover }: Props = $props();

  const client = createClient(import.meta.env.VITE_API_URL ?? "");
  const card = $derived(takeover.card as ImageSearch);
  const images = $derived(card.images ?? []);
  const activeId = $derived(card.highlight?.toUpperCase() ?? null);

  const totalMs = $derived(
    Date.parse(takeover.expires_at) - Date.parse(takeover.shown_at),
  );
  let now = $state(Date.now());
  $effect(() => {
    const id = setInterval(() => {
      now = Date.now();
    }, 250);
    return () => clearInterval(id);
  });
  const leftMs = $derived(
    Math.max(0, Date.parse(takeover.expires_at) - now),
  );
  const progressPercent = $derived(
    totalMs > 0 ? Math.max(0, Math.min(100, (leftMs / totalMs) * 100)) : 100,
  );

  function dismiss(): void {
    void client.clearTakeover().catch(() => {});
  }

  function getSpanClass(index: number): string {
    // Interlocking Tetris / Bento tile assignments for up to 6-8 items
    switch (index) {
      case 0:
        return "tile-hero"; // 2x2 block
      case 1:
        return "tile-tall"; // 1x2 vertical block
      case 2:
        return "tile-wide"; // 2x1 horizontal block
      case 3:
        return "tile-sq1";  // 1x1 accent block
      case 4:
        return "tile-sq2";  // 1x1 accent block
      case 5:
        return "tile-wide2"; // 2x1 horizontal block
      default:
        return "tile-standard";
    }
  }
</script>

<div
  class="collage-takeover"
  in:scale={{ start: 0.98, duration: 280 }}
  out:fade={{ duration: 180 }}
>
  <!-- Drain progress bar -->
  <div class="progress-bar-track">
    <div
      class="progress-bar-fill"
      style:width="{progressPercent}%"
    ></div>
  </div>

  <!-- Header banner -->
  <header class="header">
    <div class="query-pill">
      <svg class="search-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
      </svg>
      <span class="query-text">{card.query}</span>
    </div>
    <div class="hint-pill">
      <span>Ask about <strong>A</strong>, <strong>B</strong>, or say <em>"stop display"</em></span>
    </div>
    <button type="button" class="close-btn" onclick={dismiss} title="Dismiss">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </button>
  </header>

  <!-- Tetris / Mosaic Collage Grid -->
  <main class="grid-container">
    {#each images as item, idx (item.id)}
      {@const isHighlighted = activeId === item.id.toUpperCase()}
      {@const isDimmed = activeId !== null && !isHighlighted}
      <article
        class="mosaic-tile {getSpanClass(idx)}"
        class:highlighted={isHighlighted}
        class:dimmed={isDimmed}
      >
        <img
          src={item.url}
          alt={item.title || card.query}
          loading="eager"
          class="tile-image"
        />

        <!-- Letter / Identifier Badge -->
        <div class="badge" class:badge-active={isHighlighted}>
          {item.id}
        </div>

        <!-- Info overlay -->
        <div class="tile-caption" class:caption-expanded={isHighlighted}>
          <div class="caption-header">
            {#if item.title}
              <h3 class="tile-title">{item.title}</h3>
            {/if}
            {#if item.source}
              <span class="tile-source">{item.source}</span>
            {/if}
          </div>
          {#if isHighlighted && item.snippet}
            <p class="tile-snippet">{item.snippet}</p>
          {/if}
        </div>
      </article>
    {/each}
  </main>
</div>

<style>
  .collage-takeover {
    position: fixed;
    inset: 0;
    z-index: 25;
    display: flex;
    flex-direction: column;
    background: #090a0f;
    color: #f1f5f9;
    padding: max(16px, env(safe-area-inset-top)) max(20px, env(safe-area-inset-right))
      max(16px, env(safe-area-inset-bottom)) max(20px, env(safe-area-inset-left));
    box-sizing: border-box;
    overflow: hidden;
    user-select: none;
  }

  .progress-bar-track {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: rgba(255, 255, 255, 0.08);
  }

  .progress-bar-fill {
    height: 100%;
    background: #facc15;
    transition: width 250ms linear;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    height: 48px;
    margin-bottom: 14px;
    flex-shrink: 0;
  }

  .query-pill {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 9999px;
    padding: 6px 18px;
    font-size: 1.15rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: #ffffff;
  }

  .search-icon {
    color: #facc15;
  }

  .hint-pill {
    display: flex;
    align-items: center;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 9999px;
    padding: 6px 16px;
    font-size: 0.95rem;
    color: #cbd5e1;
  }

  .hint-pill strong {
    color: #facc15;
    margin: 0 3px;
  }

  .hint-pill em {
    color: #94a3b8;
    font-style: normal;
  }

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #94a3b8;
    cursor: pointer;
    transition: all 150ms ease;
  }

  .close-btn:hover {
    background: rgba(255, 255, 255, 0.16);
    color: #ffffff;
  }

  /* Bento / Tetris Mosaic Grid */
  .grid-container {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    grid-template-rows: repeat(2, minmax(0, 1fr));
    grid-auto-flow: dense;
    gap: 12px;
    min-height: 0;
  }

  /* Interlocking Spans */
  .tile-hero {
    grid-column: span 2;
    grid-row: span 2;
  }

  .tile-tall {
    grid-column: span 1;
    grid-row: span 2;
  }

  .tile-wide {
    grid-column: span 1;
    grid-row: span 1;
  }

  .tile-sq1 {
    grid-column: span 1;
    grid-row: span 1;
  }

  .tile-sq2 {
    grid-column: span 1;
    grid-row: span 1;
  }

  .tile-wide2 {
    grid-column: span 1;
    grid-row: span 1;
  }

  .tile-standard {
    grid-column: span 1;
    grid-row: span 1;
  }

  .mosaic-tile {
    position: relative;
    border-radius: 14px;
    overflow: hidden;
    background: #151821;
    border: 1px solid rgba(255, 255, 255, 0.08);
    transition: all 260ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .tile-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    background: #11141c;
  }

  /* Identifier Pill Badge */
  .badge {
    position: absolute;
    top: 12px;
    left: 12px;
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: rgba(10, 12, 18, 0.75);
    backdrop-filter: blur(10px);
    border: 1.5px solid rgba(255, 255, 255, 0.3);
    color: #ffffff;
    font-size: 1.25rem;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    z-index: 5;
    transition: all 220ms ease;
  }

  .badge-active {
    background: #facc15;
    color: #000000;
    border-color: #fde047;
    box-shadow: 0 0 16px rgba(250, 204, 21, 0.7);
    transform: scale(1.1);
  }

  /* Highlight & Dim States */
  .mosaic-tile.highlighted {
    border-color: #facc15;
    box-shadow: 0 0 0 3px #facc15, 0 16px 40px rgba(0, 0, 0, 0.7);
    transform: scale(1.02);
    z-index: 10;
  }

  .mosaic-tile.dimmed {
    opacity: 0.38;
    filter: saturate(0.5) brightness(0.75);
  }

  /* Captions */
  .tile-caption {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: linear-gradient(180deg, transparent 0%, rgba(9, 10, 15, 0.88) 45%, #090a0f 100%);
    padding: 24px 14px 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: all 220ms ease;
  }

  .caption-header {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .tile-title {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: #f8fafc;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
  }

  .tile-source {
    font-size: 0.75rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .tile-snippet {
    margin: 4px 0 0 0;
    font-size: 0.85rem;
    line-height: 1.35;
    color: #fde047;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Responsive layout for portrait / narrower screens */
  @media (max-width: 900px), (orientation: portrait) {
    .grid-container {
      grid-template-columns: repeat(2, 1fr);
      grid-template-rows: auto;
    }

    .tile-hero {
      grid-column: span 2;
      grid-row: span 1;
      height: 220px;
    }

    .tile-tall {
      grid-column: span 1;
      grid-row: span 1;
      height: 180px;
    }

    .tile-wide, .tile-sq1, .tile-sq2, .tile-wide2, .tile-standard {
      grid-column: span 1;
      grid-row: span 1;
      height: 180px;
    }

    .hint-pill {
      display: none;
    }
  }
</style>
