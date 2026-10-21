<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { remaining } from "../lib/time.svelte";
  import type { CardProps } from "./types";

  let { view }: CardProps = $props();
  const target = $derived(
    view.tickers.find((ticker) => ticker.kind === "countdown")?.target,
  );
  const left = $derived(target ? remaining(target) : null);
  const alerting = $derived(view.state === "alert");
</script>

<Card accent="countdown" hero>
  <div class="countdown" class:alerting data-ambient>
    {#if left && !left.done}
      <span class="value">
        {left.minutes}<i>m</i>{String(left.seconds).padStart(2, "0")}<i>s</i>
      </span>
      <span class="label">until it's time to go</span>
    {:else}
      <span class="value now">Time to go</span>
    {/if}
  </div>
</Card>

<style>
  .countdown {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    height: 100%;
    justify-content: center;
  }
  .value {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    letter-spacing: -0.03em;
    line-height: 0.9;
    font-size: var(--type-hero);
  }
  .value i {
    font-style: normal;
    font-size: 0.32em;
    margin: 0 0.15em 0 0.05em;
    color: var(--on-card-soft);
  }
  .value.now {
    color: var(--accent);
  }
  .label {
    font-size: var(--type-md);
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
  }
  .alerting {
    animation: flash 1s steps(1) infinite;
  }
  @keyframes flash {
    50% {
      opacity: 0.35;
    }
  }
  :global(:root[data-motion="lite"]) .alerting,
  :global(:root[data-reduce-motion="true"]) .alerting {
    animation: none;
  }
</style>
