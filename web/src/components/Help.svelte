<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { HELP } from "../lib/help-content";

  let query = $state("");

  const results = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (!q) return HELP;
    return HELP.filter(
      (entry) =>
        entry.title.toLowerCase().includes(q) ||
        entry.body.toLowerCase().includes(q) ||
        entry.tags.some((tag) => tag.includes(q)),
    );
  });
</script>

<div class="help">
  <input
    class="search"
    placeholder="Search help…"
    bind:value={query}
    aria-label="Search help"
  />
  {#if results.length === 0}
    <p class="none">Nothing matches “{query}”.</p>
  {/if}
  {#each results as entry (entry.title)}
    <details open={query.length > 0}>
      <summary>{entry.title}</summary>
      <p>{entry.body}</p>
    </details>
  {/each}
</div>

<style>
  .help {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .search {
    font: inherit;
    background: none;
    border: 1px solid color-mix(in srgb, var(--on-stage) 22%, transparent);
    color: var(--on-stage);
    border-radius: 10px;
    padding: 8px 12px;
    margin-bottom: var(--space-2);
  }
  details {
    border-top: 1px solid color-mix(in srgb, var(--on-stage) 10%, transparent);
    padding: var(--space-2) 0;
  }
  summary {
    cursor: pointer;
    font-size: var(--type-sm);
    font-weight: 600;
  }
  details p {
    margin-top: var(--space-1);
    font-size: var(--type-sm);
    color: var(--on-stage-soft);
    line-height: 1.5;
  }
  .none {
    font-size: var(--type-sm);
    color: var(--on-stage-soft);
  }
</style>
