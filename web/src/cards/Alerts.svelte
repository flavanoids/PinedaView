<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { alertSeverityColor } from "../lib/format";
  import type { AlertsData, CardProps } from "./types";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();
  const alerts = $derived(pick<AlertsData>(view, "alerts"));
  const top = $derived(alerts?.top ?? null);
  const color = $derived(alertSeverityColor(top?.severity));
</script>

<Card accent="generic" {stale} {hero}>
  {#if top}
    <span class="badge" style="--badge: {color}">{top.severity}</span>
    <span class="event">{top.event}</span>
    {#if hero && top.headline}<span class="headline">{top.headline}</span>{/if}
    {#if (alerts?.count ?? 0) > 1}
      <span class="more">+{(alerts?.count ?? 1) - 1} more</span>
    {/if}
  {:else}
    <span class="clear">No active alerts</span>
  {/if}
</Card>

<style>
  .badge {
    align-self: flex-start;
    padding: 0.15em 0.6em;
    border-radius: var(--radius-pill);
    font-size: var(--type-caption);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: white;
    background: var(--badge);
  }
  .event {
    font-size: var(--type-md);
    font-weight: var(--weight-display);
  }
  .headline {
    font-size: var(--type-sm);
    color: var(--on-card-soft);
  }
  .more {
    font-size: var(--type-caption);
    color: var(--on-card-faint);
  }
  .clear {
    color: var(--on-card-faint);
    font-size: var(--type-sm);
  }
</style>
