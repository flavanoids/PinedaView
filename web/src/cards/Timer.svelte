<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { alarmTime } from "../lib/format";
  import { remaining } from "../lib/time.svelte";
  import type { CardProps, TimerEntry } from "./types";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();
  const timers = $derived(pick<TimerEntry[]>(view, "timer") ?? []);
</script>

<Card accent="generic" {stale} {hero} fill={hero}>
  {#if timers.length === 0}
    <div class="empty-state" class:hero-empty={hero}>
      <span class="empty-icon">⏱</span>
      <span class="waiting"
        >No timers running. Start one in Settings › Timers.</span
      >
    </div>
  {:else if hero}
    {@const lead = timers[0]}
    {@const restTimers = timers.slice(1)}
    {@const left = lead ? remaining(lead.fires_at) : null}
    <div class="hero-timer">
      <div class="hero-top">
        <span class="hero-eyebrow">Timer</span>
        <span class="hero-label">{lead?.label}</span>
      </div>

      {#if left}
        <div class="hero-display" class:done={left.done}>
          {#if left.done}
            <span class="hero-digits done-text">Done!</span>
          {:else if lead?.kind === "alarm" || lead?.kind === "reminder"}
            <span class="hero-digits">{alarmTime(lead.fires_at)}</span>
          {:else}
            <span class="hero-digits">
              {left.minutes}<i class="unit">m</i>{String(left.seconds).padStart(
                2,
                "0",
              )}<i class="unit">s</i>
            </span>
          {/if}
        </div>
      {/if}

      {#if restTimers.length > 0}
        <div class="hero-secondary-list">
          {#each restTimers as rTimer (rTimer.id)}
            {@const rLeft = remaining(rTimer.fires_at)}
            <div class="sec-timer" class:done={rLeft.done}>
              <span class="sec-label">{rTimer.label}</span>
              <span class="sec-time">
                {#if rLeft.done}
                  Done!
                {:else}
                  {rLeft.minutes}m {String(rLeft.seconds).padStart(2, "0")}s
                {/if}
              </span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <ul class="timers">
      {#each timers as timer (timer.id)}
        {@const left = remaining(timer.fires_at)}
        <li class="timer" class:done={left.done}>
          <span class="label">{timer.label}</span>
          <span class="time" data-ambient>
            {#if left.done}
              Done!
            {:else if timer.kind === "alarm" || timer.kind === "reminder"}
              {alarmTime(timer.fires_at)}
            {:else}
              {left.minutes}<i>m</i>{String(left.seconds).padStart(2, "0")}<i
                >s</i
              >
            {/if}
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</Card>

<style>
  .timers {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    list-style: none;
  }
  .timer {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .label {
    font-size: var(--type-sm);
    color: var(--on-card-soft);
  }
  .time {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: var(--type-lg);
    white-space: nowrap;
  }
  .time i {
    font-style: normal;
    font-size: 0.6em;
    color: var(--on-card-faint);
    margin: 0 0.15em 0 0.05em;
  }
  .timer.done .time {
    color: var(--accent);
    animation: flash 1s steps(1) infinite;
  }
  @keyframes flash {
    50% {
      opacity: 0.35;
    }
  }
  :global(:root[data-motion="lite"]) .timer.done .time,
  :global(:root[data-reduce-motion="true"]) .timer.done .time {
    animation: none;
  }
  .waiting {
    color: var(--on-card-faint);
    font-size: var(--type-sm);
  }

  /* Hero styling */
  .hero-timer {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 100%;
    padding: var(--space-1) 0;
  }
  .hero-top {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .hero-eyebrow {
    font-size: var(--type-caption);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--on-card-soft);
    font-weight: var(--weight-label);
  }
  .hero-label {
    font-size: var(--type-md);
    font-weight: var(--weight-label);
    color: var(--on-card);
  }
  .hero-display {
    display: flex;
    align-items: baseline;
    margin: var(--space-2) 0;
  }
  .hero-digits {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: clamp(2.5rem, 24cqi, var(--type-hero));
    line-height: 1;
    letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums;
    color: var(--on-card);
  }
  .hero-digits .unit {
    font-style: normal;
    font-size: 0.55em;
    color: var(--on-card-faint);
    margin: 0 0.15em 0 0.05em;
  }
  .hero-display.done .done-text {
    color: var(--accent);
    animation: flash 1s steps(1) infinite;
  }
  .hero-secondary-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding-top: var(--space-2);
    border-top: 1px solid color-mix(in srgb, var(--on-card) 15%, transparent);
  }
  .sec-timer {
    display: flex;
    justify-content: space-between;
    font-size: var(--type-sm);
  }
  .sec-label {
    color: var(--on-card-soft);
  }
  .sec-time {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
  }
  .sec-timer.done .sec-time {
    color: var(--accent);
  }
  .empty-state.hero-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: var(--space-3);
    text-align: center;
  }
  .empty-icon {
    font-size: var(--type-xl);
    opacity: 0.5;
  }
</style>
