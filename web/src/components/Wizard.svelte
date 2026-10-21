<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import {
    createClient,
    type CardView,
    type Theme,
  } from "@pinedaview/protocol";
  import { pickableThemes } from "@pinedaview/tokens";
  import QRCode from "qrcode";
  import { tick } from "svelte";

  import { benchmarkTier, setMotionTier } from "../lib/tier.svelte";
  import {
    back,
    currentStep,
    isLast,
    next,
    persist,
    reset,
    STEPS,
    wizard,
  } from "../lib/wizard.svelte";

  interface Props {
    deviceId: string;
    onDone: () => void;
  }
  let { deviceId, onDone }: Props = $props();

  const client = createClient(import.meta.env.VITE_API_URL ?? "");
  const d = wizard.draft;

  let themes = $state<Theme[]>([]);
  let cards = $state<CardView[]>([]);
  let detected = $state<string | null>(null);
  let qr = $state("");
  let busy = $state(false);

  $effect(() => {
    void Promise.all([client.listThemes(), client.listCards()]).then(
      ([t, c]) => {
        themes = t.themes;
        cards = c;
      },
    );
    void client.detectLocation().then((loc) => {
      if (loc && !d.location_query) {
        d.location_query = loc.query;
        d.location_label = loc.label;
        detected = loc.label;
        persist();
      }
    });
    void QRCode.toString(location.origin, { type: "svg", margin: 1 }).then(
      (svg) => (qr = svg),
    );
  });

  // As Settings › Accessibility › Motion names them.
  const TIER_LABELS = {
    lite: "Reduced",
    standard: "Full",
    rich: "Full",
  } as const;

  async function runBenchmark(): Promise<void> {
    d.tier = await benchmarkTier();
    persist();
  }

  function toggleCard(id: string): void {
    d.cards = d.cards.includes(id)
      ? d.cards.filter((c) => c !== id)
      : [...d.cards, id];
    persist();
  }

  async function finish(): Promise<void> {
    busy = true;
    try {
      await client.updateConfig({
        units: d.units,
        theme: d.theme,
        location_query: d.location_query || "New York",
        location_label: d.location_label,
        countdown_enabled: d.countdown_enabled,
        countdown_start: d.countdown_start,
        countdown_end: d.countdown_end,
      });
      if (d.maps_key.trim())
        await client.setSecret("google_maps", d.maps_key.trim());
      // The rendered theme comes from the profile, not this server-wide
      // default (which only ever echoes back to this wizard) — apply it here
      // too, or the chosen theme never actually shows up.
      await client.updateProfile("default", {
        card_stack: d.cards,
        theme: d.theme,
      });
      await client.updateDevice(deviceId, {
        name: d.device_name || "Screen",
        tier: d.tier ?? undefined,
      });
      if (d.tier) setMotionTier(d.tier);
      await client.completeSetup();
      reset();
      onDone();
    } finally {
      busy = false;
    }
  }

  async function skip(): Promise<void> {
    busy = true;
    await client.completeSetup();
    reset();
    onDone();
  }

  const stepNumber = $derived(STEPS.indexOf(currentStep()) + 1);

  // On each step, move focus to the new heading so a screen reader announces the
  // step and keyboard focus lands somewhere sensible.
  $effect(() => {
    void currentStep();
    void tick().then(() => document.getElementById("wizard-heading")?.focus());
  });
</script>

<div class="wizard">
  <div
    class="bar"
    role="progressbar"
    aria-label="Setup progress"
    aria-valuemin={1}
    aria-valuemax={STEPS.length}
    aria-valuenow={stepNumber}
  >
    <i style:width={`${(stepNumber / STEPS.length) * 100}%`}></i>
  </div>
  <div class="body" role="group" aria-labelledby="wizard-heading">
    <span class="step">Setup · {stepNumber} of {STEPS.length}</span>

    {#if currentStep() === "welcome"}
      <h2 id="wizard-heading" tabindex="-1">Set up this display</h2>
      <p>About two minutes. Everything here can change later in Settings.</p>
      <div class="field"><span>This server</span><b>{location.host}</b></div>
    {:else if currentStep() === "location"}
      <h2 id="wizard-heading" tabindex="-1">Where is this display?</h2>
      <p>
        Weather, sun times and the moon phase use it. Only the forecast lookup
        leaves your server.
      </p>
      {#if detected}<div class="field">
          <span>Detected</span><b>{detected}</b>
        </div>{/if}
      <label
        >Place
        <input
          bind:value={d.location_query}
          oninput={persist}
          placeholder="City, ZIP, or lat,lon"
        /></label
      >
    {:else if currentStep() === "numbers"}
      <h2 id="wizard-heading" tabindex="-1">Numbers and time</h2>
      <div class="pills" role="group" aria-label="Temperature units">
        <button
          type="button"
          aria-label="Fahrenheit"
          aria-pressed={d.units === "imperial"}
          class:on={d.units === "imperial"}
          onclick={() => ((d.units = "imperial"), persist())}>°F</button
        >
        <button
          type="button"
          aria-label="Celsius"
          aria-pressed={d.units === "metric"}
          class:on={d.units === "metric"}
          onclick={() => ((d.units = "metric"), persist())}>°C</button
        >
      </div>
      <label class="check">
        <input
          type="checkbox"
          bind:checked={d.countdown_enabled}
          onchange={persist}
        />
        Weekday morning countdown
      </label>
      {#if d.countdown_enabled}
        <div class="pills">
          <label class="time"
            >Start<input
              type="time"
              bind:value={d.countdown_start}
              onchange={persist}
            /></label
          >
          <label class="time"
            >End<input
              type="time"
              bind:value={d.countdown_end}
              onchange={persist}
            /></label
          >
        </div>
      {/if}
    {:else if currentStep() === "look"}
      <h2 id="wizard-heading" tabindex="-1">Pick a look</h2>
      <div class="swatches" role="group" aria-label="Theme">
        {#each pickableThemes(themes) as theme (theme.name)}
          <button
            type="button"
            class="swatch"
            class:on={d.theme === theme.name}
            aria-pressed={d.theme === theme.name}
            style:background={theme.stage}
            style:color={theme.on_stage}
            onclick={() => ((d.theme = theme.name), persist())}
          >
            <span aria-hidden="true" style:background={theme.cards.weather}
            ></span>
            {theme.label}
          </button>
        {/each}
      </div>
    {:else if currentStep() === "cards"}
      <h2 id="wizard-heading" tabindex="-1">Choose the starting cards</h2>
      <div class="cardlist">
        {#each cards as card (card.id)}
          <label class:blocked={card.status === "blocked"}>
            <input
              type="checkbox"
              checked={d.cards.includes(card.id)}
              disabled={card.status === "blocked"}
              onchange={() => toggleCard(card.id)}
            />
            {card.name}
            {#if card.status === "blocked"}<em>— {card.reason}</em>{/if}
          </label>
        {/each}
      </div>
      <label
        >Google Maps API key
        <input
          bind:value={d.maps_key}
          oninput={persist}
          placeholder="Optional"
          autocomplete="off"
          spellcheck="false"
        />
        <span class="hint"
          >Turns on live drive times for the Commute card. You can add it later
          in Settings › Connect.</span
        ></label
      >
    {:else if currentStep() === "screen"}
      <h2 id="wizard-heading" tabindex="-1">Name this screen</h2>
      <label>Name <input bind:value={d.device_name} oninput={persist} /></label>
      <p class="hint">
        Shown in Settings when you have more than one screen, like “Kitchen” or
        “Hallway”.
      </p>
      <button class="ghost" onclick={runBenchmark}>Check animation speed</button
      >
      {#if d.tier}<div class="field">
          <span>Motion</span><b>{TIER_LABELS[d.tier]}</b>
        </div>{/if}
    {:else if currentStep() === "invite"}
      <h2 id="wizard-heading" tabindex="-1">Add more screens</h2>
      <p>Open this address on another phone or tablet:</p>
      <div class="field"><span>Address</span><b>{location.origin}</b></div>
      {#if qr}
        <div
          class="qr"
          role="img"
          aria-label="QR code linking to {location.origin}"
        >
          <!-- eslint-disable-next-line svelte/no-at-html-tags -- qrcode lib output, not user input -->
          {@html qr}
        </div>
      {/if}
    {/if}

    <div class="actions">
      <button class="ghost" onclick={skip} disabled={busy}
        >Skip — use defaults</button
      >
      <div>
        {#if stepNumber > 1}<button class="ghost" onclick={back} disabled={busy}
            >Back</button
          >{/if}
        {#if isLast()}
          <button class="primary" onclick={finish} disabled={busy}
            >Finish</button
          >
        {:else}
          <button class="primary" onclick={next} disabled={busy}
            >Continue</button
          >
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .wizard {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--stage);
    color: var(--on-stage);
    padding: var(--space-3);
    z-index: 50;
  }
  .body {
    width: min(440px, 100%);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: color-mix(in srgb, var(--on-stage) 15%, transparent);
  }
  .bar i {
    display: block;
    height: 100%;
    background: var(--accent);
    transition: width var(--dur-mid) var(--ease-spring);
  }
  .step {
    font-size: var(--type-caption);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--on-stage-soft);
  }
  h2 {
    font-weight: var(--weight-label);
    font-size: var(--type-lg);
  }
  p {
    color: var(--on-stage-soft);
    font-size: var(--type-sm);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: var(--type-sm);
  }
  .hint {
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
  }
  label.check {
    flex-direction: row;
    align-items: center;
    gap: var(--space-2);
  }
  input {
    font: inherit;
    background: none;
    border: 1px solid color-mix(in srgb, var(--on-stage) 22%, transparent);
    color: var(--on-stage);
    border-radius: 8px;
    padding: 8px 10px;
  }
  .field {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-top: 1px solid color-mix(in srgb, var(--on-stage) 12%, transparent);
    font-size: var(--type-sm);
  }
  .field span {
    color: var(--on-stage-soft);
  }
  .pills {
    display: flex;
    gap: var(--space-2);
  }
  .pills button,
  .ghost,
  .primary {
    font: inherit;
    font-size: var(--type-sm);
    padding: 8px 16px;
    border-radius: var(--radius-pill);
    border: 1px solid color-mix(in srgb, var(--on-stage) 22%, transparent);
    background: none;
    color: var(--on-stage);
    cursor: pointer;
  }
  .pills button.on {
    background: var(--on-stage);
    color: var(--stage);
  }
  .primary {
    background: var(--accent);
    color: var(--stage);
    border-color: var(--accent);
    font-weight: 600;
  }
  .swatches,
  .cardlist {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    max-height: 44dvh;
    overflow-y: auto;
  }
  .swatch {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 10px 12px;
    border-radius: 10px;
    border: 2px solid transparent;
    cursor: pointer;
    font-size: var(--type-sm);
  }
  .swatch.on {
    border-color: var(--accent);
  }
  .swatch span {
    width: 18px;
    height: 18px;
    border-radius: 5px;
  }
  .cardlist label {
    flex-direction: row;
    gap: var(--space-2);
    align-items: center;
  }
  .cardlist label.blocked {
    color: var(--on-stage-faint, var(--on-stage-soft));
  }
  .cardlist em {
    font-style: normal;
    color: var(--accent);
    font-size: var(--type-caption);
  }
  .qr {
    width: min(var(--qr-size), 200px);
    align-self: center;
  }
  .qr :global(svg) {
    width: 100%;
    height: auto;
  }
  .actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-3);
    flex-wrap: wrap;
  }
  .actions > div {
    display: flex;
    gap: var(--space-2);
  }
</style>
