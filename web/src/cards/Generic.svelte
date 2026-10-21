<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import type { CardProps } from "./types";

  // Fallback for a card the client has no bespoke view for yet — a stranger's
  // card still shows something (its name, and any store data) with no rebuild.
  let {
    view,
    stale,
    hero,
    id = "card",
  }: CardProps & { id?: string } = $props();

  const payload = $derived(
    Object.entries((view.data as Record<string, unknown>) ?? {})
      .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
      .join("\n"),
  );
</script>

<Card accent="generic" {stale} {hero}>
  <span class="name">{id}</span>
  {#if payload}<pre class="data">{payload}</pre>{/if}
</Card>

<style>
  .name {
    font-size: var(--type-md);
    font-weight: var(--weight-label);
  }
  .data {
    margin-top: var(--space-2);
    font-size: var(--type-caption);
    color: var(--on-card-faint);
    white-space: pre-wrap;
    overflow: hidden;
  }
</style>
