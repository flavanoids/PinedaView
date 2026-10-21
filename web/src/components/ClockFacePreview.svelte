<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Settings → Display: pick a clock face from live thumbnails of each. -->
<script lang="ts">
  import ClockFaces from "../cards/ClockFaces.svelte";
  import {
    clockFace,
    currentFace,
    FACES,
    setClockFace,
  } from "../lib/clockface.svelte";
  import { formatClock, formatWords } from "../lib/format";
  import { clock } from "../lib/time.svelte";

  const parts = $derived(formatClock(clock.now));
  const words = $derived(formatWords(clock.now));
  const face = $derived(currentFace());
  // A face pushed from the phone menu overrides this picker until cleared there.
  const locked = $derived(clockFace.pushed !== null);
</script>

<div class="grid" role="radiogroup" aria-label="Clock face">
  {#each FACES as f (f.id)}
    <button
      type="button"
      role="radio"
      aria-checked={face === f.id}
      class:on={face === f.id}
      disabled={locked}
      onclick={() => setClockFace(f.id)}
    >
      <span class="thumb">
        <ClockFaces now={clock.now} {parts} {words} face={f.id} />
      </span>
      <span class="name">{f.label}</span>
    </button>
  {/each}
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
    /* Auto rows sized each thumb's 4:3 box against its widest possible
       column, leaving a tall gap under every row. */
    grid-auto-rows: min-content;
    gap: var(--space-2);
  }
  button:disabled {
    cursor: default;
  }
  button {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 0;
    border: none;
    background: none;
    color: var(--on-stage);
    cursor: pointer;
    font: inherit;
  }
  .thumb {
    display: block;
    overflow: hidden;
    aspect-ratio: 4 / 3;
    padding: var(--space-2);
    border-radius: var(--radius-card);
    background: var(--card-clock);
    color: var(--on-card);
    outline: 2px solid transparent;
    outline-offset: 2px;
  }
  button.on .thumb {
    outline-color: var(--accent);
  }
  button:focus-visible .thumb {
    outline-color: var(--on-stage);
  }
  .name {
    font-size: var(--type-caption);
    font-weight: var(--weight-label);
    color: var(--on-stage-soft);
  }
  button.on .name {
    color: var(--on-stage);
  }
</style>
