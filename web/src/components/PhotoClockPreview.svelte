<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The Photo Clock full screen over Settings, with its glass controls along
  the bottom: each change shows on the clock as it's made. Saved as it goes,
  like the rest of Settings; Done goes back to the sheet.
-->
<script lang="ts">
  import PhotoClock from "../cards/PhotoClock.svelte";
  import RoundPhotoClock from "../cards/RoundPhotoClock.svelte";
  import type {
    PhotoClockGlass,
    PhotoClockSettings,
    PhotoClockSize,
  } from "../lib/clockface.svelte";
  import { formatClock } from "../lib/format";
  import { clock } from "../lib/time.svelte";
  import Segmented from "./settings/Segmented.svelte";

  let {
    settings,
    font = null,
    tint = null,
    sizes,
    glasses,
    inks = [],
    onchange,
    onclose,
  }: {
    settings: PhotoClockSettings;
    /** As the clock gets them from the view: the phone's Clock only font
        and the glass tint. */
    font?: string | null;
    tint?: string | null;
    sizes: readonly { value: PhotoClockSize; label: string }[];
    glasses: readonly { value: PhotoClockGlass; label: string }[];
    /** The photo-colour looks, picked in place of the glass. */
    inks?: readonly { value: PhotoClockGlass; label: string }[];
    onchange: (patch: Partial<PhotoClockSettings>) => void;
    onclose: () => void;
  } = $props();

  const parts = $derived(formatClock(clock.now));
  // The slider moves the glass on every step; it's saved when let go.
  let dragging = $state<number | null>(null);
  const opacity = $derived(dragging ?? settings.opacity);
  const shown = $derived({ ...settings, opacity });

  let el = $state<HTMLDivElement>();
  $effect(() => el?.focus());
</script>

<div
  bind:this={el}
  class="preview"
  role="dialog"
  aria-modal="true"
  aria-label="Photo clock preview"
  tabindex="-1"
  onkeydown={(e) => {
    if (e.key !== "Escape") return;
    e.stopPropagation();
    onclose();
  }}
>
  {#if shown.face === "hands"}
    <RoundPhotoClock {tint} date={parts.date} settings={shown} />
  {:else}
    <PhotoClock
      {parts}
      {font}
      {tint}
      settings={shown}
      weather={{ current: { tempC: 22, code: "113", isDay: true } }}
      units="imperial"
      share={false}
    />
  {/if}
  <div class="controls">
    <label class="row">
      <span>Glass opacity</span>
      <input
        type="range"
        min="0"
        max="1"
        step="0.05"
        value={opacity}
        oninput={(e) => (dragging = Number(e.currentTarget.value))}
        onchange={(e) => {
          dragging = null;
          onchange({ opacity: Number(e.currentTarget.value) });
        }}
      />
      <output>{Math.round(opacity * 100)}%</output>
    </label>
    <div class="row">
      <Segmented
        label="Glass"
        options={glasses}
        value={settings.glass}
        onchange={(glass) => onchange({ glass })}
      />
      {#if inks.length && settings.face !== "hands"}
        <Segmented
          label="Photo colours"
          options={inks}
          value={settings.glass}
          onchange={(glass) => onchange({ glass })}
        />
      {/if}
      <Segmented
        label="Size"
        options={sizes}
        value={settings.size}
        onchange={(size) => onchange({ size })}
      />
      <button type="button" class="btn primary" onclick={onclose}>Done</button>
    </div>
  </div>
</div>

<style>
  .preview {
    position: fixed;
    inset: 0;
    z-index: 10;
    background: #000;
  }
  .controls {
    position: absolute;
    left: 50%;
    bottom: max(1rem, env(safe-area-inset-bottom));
    translate: -50% 0;
    width: min(600px, calc(100% - 2rem));
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
    border-radius: 20px;
    background: color-mix(in srgb, var(--stage) 82%, transparent);
    color: var(--on-stage);
    backdrop-filter: blur(16px);
    box-shadow: 0 10px 40px rgb(0 0 0 / 0.4);
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
  }
  .row input {
    flex: 1;
    min-width: 8rem;
  }
  output {
    min-width: 3ch;
    font-variant-numeric: tabular-nums;
    text-align: end;
  }
  .row .btn {
    margin-inline-start: auto;
  }
</style>
