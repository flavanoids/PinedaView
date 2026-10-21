<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Timer } from "@pinedaview/protocol";

  import { useSettings } from "../lib/settings.svelte";
  import { remaining } from "../lib/time.svelte";
  import {
    playTimerSound,
    setTimerSound,
    timerSound,
    type TimerSound,
  } from "../lib/timerSound.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import Scope from "./settings/Scope.svelte";
  import Segmented from "./settings/Segmented.svelte";

  const settings = useSettings();
  const client = settings.client;

  const PRESETS = [1, 3, 5, 10, 15, 30];
  const SOUNDS: { value: TimerSound; label: string }[] = [
    { value: "chime", label: "Chime" },
    { value: "bell", label: "Bell" },
    { value: "beep", label: "Beep" },
    { value: "off", label: "Silent" },
  ];

  let timers = $state<Timer[]>([]);
  let label = $state("");
  let minutes = $state(5);

  async function refresh(): Promise<void> {
    timers = await client.listTimers();
  }
  $effect(() => {
    void refresh();
  });

  async function start(mins: number): Promise<void> {
    if (mins <= 0) return;
    const name = label.trim() || `${mins} minute timer`;
    const ok = await settings.attempt(
      () => client.addTimer(mins * 60, name),
      `${name} started`,
    );
    if (ok) {
      label = "";
      await refresh();
    }
  }
  async function cancel(id: string): Promise<void> {
    if (await settings.attempt(() => client.cancelTimer(id), "Timer cancelled"))
      await refresh();
  }

  function left(timer: Timer): string {
    const r = remaining(timer.fires_at);
    if (r.done) return "Done";
    return r.minutes >= 60
      ? `${Math.floor(r.minutes / 60)} h ${r.minutes % 60} min`
      : `${r.minutes}:${String(r.seconds).padStart(2, "0")}`;
  }
</script>

<Scope kind="home" />

<Group title="Running">
  {#if timers.length === 0}
    <p class="hint empty">No timers running.</p>
  {:else}
    {#each timers as timer (timer.id)}
      <div class="timer">
        <span class="name">{timer.label}</span>
        <span class="left">{left(timer)}</span>
        {#if !timer.source}
          <button
            type="button"
            class="btn small"
            onclick={() => cancel(timer.id)}>Cancel</button
          >
        {/if}
      </div>
    {/each}
  {/if}
</Group>

<Group
  title="Start a timer"
  description="It counts down on screens with a timer card, and every screen plays its sound when it ends."
>
  <Field label="Name" hint="Optional, like “Pasta” or “Laundry”.">
    {#snippet children(id)}
      <input {id} placeholder="Timer" maxlength="40" bind:value={label} />
    {/snippet}
  </Field>
  <div class="presets" role="group" aria-label="Start a timer for">
    {#each PRESETS as mins (mins)}
      <button type="button" class="btn" onclick={() => start(mins)}
        >{mins} min</button
      >
    {/each}
  </div>
  <form
    class="custom"
    onsubmit={(e) => {
      e.preventDefault();
      void start(minutes);
    }}
  >
    <label for="timer-minutes">Other</label>
    <input
      id="timer-minutes"
      type="number"
      min="1"
      max="1440"
      bind:value={minutes}
    />
    <span class="hint">minutes</span>
    <button type="submit" class="btn primary">Start</button>
  </form>
</Group>

<Group title="Sound">
  <Field
    label="When a timer ends"
    hint="Saved on this device only. Some browsers stay silent until you've tapped the screen once."
    stacked
  >
    {#snippet children(id)}
      <div class="sound">
        <Segmented
          {id}
          options={SOUNDS}
          value={timerSound.choice}
          onchange={(choice) => {
            setTimerSound(choice);
            playTimerSound(choice);
          }}
        />
        <button
          type="button"
          class="btn small"
          disabled={timerSound.choice === "off"}
          onclick={() => playTimerSound()}>Play</button
        >
      </div>
    {/snippet}
  </Field>
</Group>

<style>
  .empty {
    padding: 12px 0;
  }
  .timer {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 10px 0;
    font-size: var(--type-sm);
  }
  .name {
    flex: 1;
    font-weight: 500;
  }
  .left {
    font-variant-numeric: tabular-nums;
    color: var(--on-stage-soft);
  }
  .presets {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 12px 0;
  }
  .custom {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 12px 0;
    font-size: var(--type-sm);
  }
  .custom input {
    width: 5.5rem;
  }
  .custom .btn {
    margin-left: auto;
  }
  .sound {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
</style>
