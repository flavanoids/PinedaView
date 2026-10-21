<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { CustomColours, Theme } from "@pinedaview/protocol";
  import { FONTS, type FontId } from "@pinedaview/tokens";

  import { modal } from "../lib/modal";
  import { useSettings } from "../lib/settings.svelte";
  import {
    contrastRatio,
    generateHarmoniousPalette,
    generateNightTwin,
    inkFor,
    isValidHex,
    normalizeHex,
  } from "../lib/themeHelpers";
  import CloseIcon from "./CloseIcon.svelte";

  interface Props {
    initialTheme?: Theme | null;
    themes: Theme[];
    currentProfileTheme?: string;
    onClose: () => void;
    onSaved: (theme: Theme) => void;
    onDeleted?: (themeName: string) => void;
  }

  let {
    initialTheme = null,
    themes,
    currentProfileTheme = "",
    onClose,
    onSaved,
    onDeleted,
  }: Props = $props();

  const settings = useSettings();
  const client = settings.client;
  const isEditing = $derived(!!initialTheme && initialTheme.custom);
  const isInUse = $derived(
    isEditing && initialTheme?.name === currentProfileTheme,
  );

  // Form state
  let label = $state("My theme");
  let stage = $state("#181b22");
  let accent = $state("#e7a34a");
  let weather = $state("#2a3443");
  let clock = $state("#202834");
  let affirmation = $state("#38475c");
  let font = $state<FontId | "">("");

  $effect(() => {
    if (initialTheme) {
      label = initialTheme.label ?? "My theme";
      stage = initialTheme.stage ?? "#181b22";
      accent = initialTheme.accent ?? "#e7a34a";
      weather = initialTheme.cards?.weather ?? "#2a3443";
      clock = initialTheme.cards?.clock ?? "#202834";
      affirmation = initialTheme.cards?.affirmation ?? "#38475c";
      font = (initialTheme.font as FontId | undefined) ?? "";
    }
  });

  let saving = $state(false);
  let deleting = $state(false);
  let errorMsg = $state("");
  let importOpen = $state(false);
  let importJsonText = $state("");
  let copyFeedback = $state(false);

  async function copyThemeJson(): Promise<void> {
    const payload = {
      label: label.trim() || "My theme",
      stage: normalizeHex(stage),
      accent: normalizeHex(accent),
      weather: normalizeHex(weather),
      clock: normalizeHex(clock),
      affirmation: normalizeHex(affirmation),
      font: font || null,
    };
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      copyFeedback = true;
      setTimeout(() => (copyFeedback = false), 2000);
    } catch {
      errorMsg = "Unable to copy to clipboard.";
    }
  }

  function applyImportJson(): void {
    try {
      const parsed = JSON.parse(importJsonText.trim()) as Record<
        string,
        unknown
      >;
      if (typeof parsed.label === "string" && parsed.label.trim()) {
        label = parsed.label.trim();
      }
      if (typeof parsed.stage === "string" && isValidHex(parsed.stage)) {
        stage = parsed.stage.toLowerCase();
      }
      if (typeof parsed.accent === "string" && isValidHex(parsed.accent)) {
        accent = parsed.accent.toLowerCase();
      }
      if (typeof parsed.weather === "string" && isValidHex(parsed.weather)) {
        weather = parsed.weather.toLowerCase();
      }
      if (typeof parsed.clock === "string" && isValidHex(parsed.clock)) {
        clock = parsed.clock.toLowerCase();
      }
      if (
        typeof parsed.affirmation === "string" &&
        isValidHex(parsed.affirmation)
      ) {
        affirmation = parsed.affirmation.toLowerCase();
      }
      if (typeof parsed.font === "string") {
        font = (parsed.font as FontId) || "";
      }
      importOpen = false;
      importJsonText = "";
      errorMsg = "";
    } catch {
      errorMsg = "Invalid JSON. Please verify the format.";
    }
  }

  // Live computed inks & contrast
  const stageInk = $derived(inkFor(stage));
  const cardInk = $derived(inkFor(weather, clock, affirmation));
  const stageContrast = $derived(contrastRatio(stage, stageInk));
  const cardContrast = $derived(contrastRatio(weather, cardInk));
  const accentContrast = $derived(contrastRatio(stage, accent));

  function applyPreset(sourceTheme: Theme): void {
    stage = sourceTheme.stage;
    accent = sourceTheme.accent;
    weather = sourceTheme.cards.weather ?? weather;
    clock = sourceTheme.cards.clock ?? clock;
    affirmation = sourceTheme.cards.affirmation ?? affirmation;
    if (sourceTheme.font) {
      font = sourceTheme.font as FontId;
    }
  }

  function harmonize(
    mode: "monochromatic" | "analogous" | "complementary" | "vibrant",
  ): void {
    const pal = generateHarmoniousPalette(stage, mode, label);
    stage = pal.stage;
    accent = pal.accent;
    weather = pal.weather;
    clock = pal.clock;
    affirmation = pal.affirmation;
  }

  function makeNightVariant(): void {
    const dayColours: CustomColours = {
      label,
      stage,
      accent,
      weather,
      clock,
      affirmation,
      font: font || null,
    };
    const night = generateNightTwin(dayColours);
    label = night.label;
    stage = night.stage;
    accent = night.accent;
    weather = night.weather;
    clock = night.clock;
    affirmation = night.affirmation;
  }

  async function handleSave(): Promise<void> {
    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      errorMsg = "Please give your theme a name.";
      return;
    }
    if (
      !isValidHex(stage) ||
      !isValidHex(accent) ||
      !isValidHex(weather) ||
      !isValidHex(clock) ||
      !isValidHex(affirmation)
    ) {
      errorMsg = "All colours must be valid 6-digit hex values (#rrggbb).";
      return;
    }

    errorMsg = "";
    saving = true;

    const payload: CustomColours = {
      label: trimmedLabel,
      stage: normalizeHex(stage),
      accent: normalizeHex(accent),
      weather: normalizeHex(weather),
      clock: normalizeHex(clock),
      affirmation: normalizeHex(affirmation),
      phrase: normalizeHex(affirmation),
      font: font || null,
    };

    try {
      let savedTheme: Theme;
      if (isEditing && initialTheme) {
        savedTheme = await client.updateCustomTheme(initialTheme.name, payload);
      } else {
        savedTheme = await client.createCustomTheme(payload);
      }
      onSaved(savedTheme);
      onClose();
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : "Failed to save theme.";
    } finally {
      saving = false;
    }
  }

  async function handleDelete(): Promise<void> {
    if (!initialTheme?.name || !isEditing) return;
    if (isInUse) {
      errorMsg = "Cannot delete a theme that is currently in use.";
      return;
    }
    if (!confirm(`Delete ${initialTheme.label}? This cannot be undone.`))
      return;

    deleting = true;
    try {
      await client.deleteCustomTheme(initialTheme.name);
      onDeleted?.(initialTheme.name);
      onClose();
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : "Failed to delete theme.";
    } finally {
      deleting = false;
    }
  }
</script>

<div class="backdrop" use:modal={{ onClose }}>
  <div
    class="sheet"
    role="dialog"
    aria-modal="true"
    aria-labelledby="theme-studio-title"
  >
    <div class="top-bar">
      <h2 id="theme-studio-title">
        {isEditing ? `Edit ${initialTheme?.label}` : "Make a theme"}
      </h2>
      <button
        type="button"
        class="icon-btn"
        aria-label="Close"
        onclick={onClose}
      >
        <CloseIcon />
      </button>
    </div>

    <div class="content">
      <!-- Live Preview Hero Mockup -->
      <section
        class="preview-hero"
        style:background={stage}
        style:color={stageInk}
      >
        <div class="preview-stage-meta">
          <span
            class="preview-badge"
            style:background={accent}
            style:color={stage}
          >
            Accent Highlight
          </span>
          <span class="contrast-score">
            Text: {stageContrast.toFixed(1)}:1
          </span>
        </div>

        <div class="preview-board">
          <div
            class="mock-card weather"
            style:background={weather}
            style:color={cardInk}
          >
            <span class="mock-label">Weather</span>
            <span class="mock-val">72°</span>
            <span class="mock-sub">Sunny · Austin</span>
          </div>

          <div
            class="mock-card clock"
            style:background={clock}
            style:color={cardInk}
          >
            <span class="mock-label">Clock</span>
            <span class="mock-val clock-val">10:42</span>
            <span class="mock-sub">Sunday, Oct 18</span>
          </div>

          <div
            class="mock-card quote"
            style:background={affirmation}
            style:color={cardInk}
          >
            <span class="mock-label">Quote</span>
            <p class="mock-quote">
              “Simplicity is prerequisite for reliability.”
            </p>
            <span class="mock-sub">— Dijkstra</span>
          </div>
        </div>

        <div class="preview-footer">
          <span class="card-contrast-tag">
            Card ink contrast: {cardContrast.toFixed(1)}:1 ({cardContrast >= 4.5
              ? "Good"
              : "Low"})
          </span>
          <span class="accent-contrast-tag">
            Accent contrast: {accentContrast.toFixed(1)}:1
          </span>
        </div>
      </section>

      {#if errorMsg}
        <div class="error-banner" role="alert">{errorMsg}</div>
      {/if}

      <!-- Preset / Remix Selector -->
      <div class="section-box">
        <div class="split-header">
          <label for="theme-preset-select" class="field-title"
            >Start from existing theme</label
          >
          <div class="share-actions">
            <button
              type="button"
              class="mini-action-btn"
              onclick={copyThemeJson}
              title="Copy theme JSON to clipboard"
            >
              {copyFeedback ? "✓ Copied!" : "Export JSON"}
            </button>
            <button
              type="button"
              class="mini-action-btn"
              onclick={() => (importOpen = !importOpen)}
              title="Import theme from JSON"
            >
              {importOpen ? "Close Import" : "Import JSON"}
            </button>
          </div>
        </div>
        <p class="field-hint">
          Copy colors from any theme to customize, or import/export JSON.
        </p>
        <select
          id="theme-preset-select"
          class="text-input"
          onchange={(e) => {
            const picked = themes.find((t) => t.name === e.currentTarget.value);
            if (picked) applyPreset(picked);
          }}
        >
          <option value="" disabled selected>Choose a theme to remix…</option>
          {#each themes as t (t.name)}
            <option value={t.name}>{t.label}</option>
          {/each}
        </select>

        {#if importOpen}
          <div class="import-box">
            <textarea
              class="text-input json-area"
              bind:value={importJsonText}
              placeholder={'{\n  "label": "My Theme",\n  "stage": "#101820",\n  "accent": "#f2aa4c",\n  "weather": "#2b3a4a",\n  "clock": "#1f2a36",\n  "affirmation": "#3d5066"\n}'}
              rows="4"
            ></textarea>
            <button
              type="button"
              class="tool-btn apply-json-btn"
              onclick={applyImportJson}
              disabled={!importJsonText.trim()}
            >
              Apply imported JSON
            </button>
          </div>
        {/if}
      </div>

      <!-- Generator shortcuts -->
      <div class="section-box">
        <span class="field-title">Color Harmonies & Night Mode</span>
        <p class="field-hint">
          Generate harmonious cards from your background color.
        </p>
        <div class="tools-row">
          <button
            type="button"
            class="tool-btn"
            onclick={() => harmonize("analogous")}
          >
            Analogous
          </button>
          <button
            type="button"
            class="tool-btn"
            onclick={() => harmonize("monochromatic")}
          >
            Monochrome
          </button>
          <button
            type="button"
            class="tool-btn"
            onclick={() => harmonize("complementary")}
          >
            Complementary
          </button>
          <button
            type="button"
            class="tool-btn"
            onclick={() => harmonize("vibrant")}
          >
            Vibrant
          </button>
          <button
            type="button"
            class="tool-btn night"
            onclick={makeNightVariant}
            title="Deepen colors for sunset"
          >
            ☾ Make Night Twin
          </button>
        </div>
      </div>

      <!-- Form Inputs -->
      <div class="section-box">
        <label for="theme-name-input" class="field-title">Theme name</label>
        <input
          id="theme-name-input"
          type="text"
          class="text-input"
          maxlength="40"
          bind:value={label}
          placeholder="e.g. Nordic Dusk"
        />

        <div class="color-grid">
          <div class="color-control">
            <span class="color-title">Stage (Background)</span>
            <div class="color-row">
              <input
                type="color"
                bind:value={stage}
                class="color-picker"
                aria-label="Stage background color"
              />
              <input
                type="text"
                bind:value={stage}
                class="hex-input"
                maxlength="7"
              />
            </div>
          </div>

          <div class="color-control">
            <span class="color-title">Accent (Highlights)</span>
            <div class="color-row">
              <input
                type="color"
                bind:value={accent}
                class="color-picker"
                aria-label="Accent highlight color"
              />
              <input
                type="text"
                bind:value={accent}
                class="hex-input"
                maxlength="7"
              />
            </div>
          </div>

          <div class="color-control">
            <span class="color-title">Most cards (Weather, etc.)</span>
            <div class="color-row">
              <input
                type="color"
                bind:value={weather}
                class="color-picker"
                aria-label="Weather card color"
              />
              <input
                type="text"
                bind:value={weather}
                class="hex-input"
                maxlength="7"
              />
            </div>
          </div>

          <div class="color-control">
            <span class="color-title">Clock card</span>
            <div class="color-row">
              <input
                type="color"
                bind:value={clock}
                class="color-picker"
                aria-label="Clock card color"
              />
              <input
                type="text"
                bind:value={clock}
                class="hex-input"
                maxlength="7"
              />
            </div>
          </div>

          <div class="color-control">
            <span class="color-title">Quote card</span>
            <div class="color-row">
              <input
                type="color"
                bind:value={affirmation}
                class="color-picker"
                aria-label="Quote card color"
              />
              <input
                type="text"
                bind:value={affirmation}
                class="hex-input"
                maxlength="7"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Typeface -->
      <div class="section-box">
        <span class="field-title">Typeface</span>
        <p class="field-hint">
          The font this theme wears. A screen's custom font choice outranks it.
        </p>
        <div class="font-chips" role="radiogroup" aria-label="Theme font">
          <button
            type="button"
            role="radio"
            class="chip"
            aria-checked={!font}
            class:active={!font}
            onclick={() => (font = "")}
          >
            The usual
          </button>
          {#each FONTS as f (f.id)}
            <button
              type="button"
              role="radio"
              class="chip"
              style:font-family={f.stack}
              aria-checked={font === f.id}
              class:active={font === f.id}
              onclick={() => (font = f.id)}
            >
              {f.label}
            </button>
          {/each}
        </div>
      </div>
    </div>

    <!-- Bottom Actions -->
    <div class="footer">
      {#if isEditing}
        <button
          type="button"
          class="btn danger"
          disabled={saving || deleting || isInUse}
          title={isInUse
            ? "Switch to another theme before deleting this one"
            : "Delete theme"}
          onclick={handleDelete}
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
      {/if}
      <div class="spacer"></div>
      <button
        type="button"
        class="btn secondary"
        onclick={onClose}
        disabled={saving || deleting}
      >
        Cancel
      </button>
      <button
        type="button"
        class="btn primary"
        onclick={handleSave}
        disabled={saving || deleting}
      >
        {saving ? "Saving…" : isEditing ? "Save changes" : "Save theme"}
      </button>
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-3);
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(8px);
  }

  .sheet {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 680px;
    max-height: 92vh;
    border-radius: 20px;
    background: var(--stage);
    color: var(--on-stage);
    border: 1px solid color-mix(in srgb, var(--on-stage) 16%, transparent);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4);
    overflow: hidden;
  }

  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid
      color-mix(in srgb, var(--on-stage) 10%, transparent);
  }

  h2 {
    font-size: var(--type-md);
    font-weight: 600;
  }

  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: none;
    background: color-mix(in srgb, var(--on-stage) 10%, transparent);
    color: var(--on-stage);
    cursor: pointer;
  }
  .icon-btn:hover {
    background: color-mix(in srgb, var(--on-stage) 18%, transparent);
  }

  .content {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 20px;
    overflow-y: auto;
  }

  .preview-hero {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.15);
  }

  .preview-stage-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .preview-badge {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
  }

  .contrast-score {
    font-size: 11px;
    opacity: 0.8;
  }

  .preview-board {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }

  .mock-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px 12px;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
  }

  .mock-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.7;
  }

  .mock-val {
    font-size: 18px;
    font-weight: 700;
    line-height: 1.1;
  }

  .clock-val {
    font-variant-numeric: tabular-nums;
  }

  .mock-quote {
    font-size: 11px;
    font-style: italic;
    line-height: 1.25;
    margin: 2px 0;
  }

  .mock-sub {
    font-size: 10px;
    opacity: 0.75;
  }

  .preview-footer {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    opacity: 0.8;
  }

  .error-banner {
    padding: 10px 14px;
    border-radius: 10px;
    background: color-mix(in srgb, #ff453a 20%, transparent);
    color: #ff453a;
    font-size: var(--type-sm);
  }

  .section-box {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 14px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--on-stage) 4%, transparent);
    border: 1px solid color-mix(in srgb, var(--on-stage) 8%, transparent);
  }

  .split-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .share-actions {
    display: flex;
    gap: 6px;
  }

  .mini-action-btn {
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid color-mix(in srgb, var(--on-stage) 16%, transparent);
    background: color-mix(in srgb, var(--on-stage) 6%, transparent);
    color: var(--on-stage);
    font: inherit;
    font-size: 11px;
    cursor: pointer;
    transition:
      background var(--dur-fast) ease,
      color var(--dur-fast) ease;
  }
  .mini-action-btn:hover {
    background: var(--accent);
    color: var(--stage);
    border-color: var(--accent);
  }

  .import-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 8px;
    padding: 10px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--on-stage) 6%, transparent);
  }

  .json-area {
    font-family: monospace;
    font-size: 11px;
    resize: vertical;
  }

  .apply-json-btn {
    align-self: flex-start;
  }

  .field-title {
    font-size: var(--type-sm);
    font-weight: 600;
  }

  .field-hint {
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
    margin-bottom: 4px;
  }

  .text-input {
    width: 100%;
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--on-stage) 18%, transparent);
    background: color-mix(in srgb, var(--stage) 80%, black);
    color: var(--on-stage);
    font: inherit;
    font-size: var(--type-sm);
  }

  .tools-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .tool-btn {
    padding: 6px 12px;
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--on-stage) 16%, transparent);
    background: color-mix(in srgb, var(--on-stage) 6%, transparent);
    color: var(--on-stage);
    font: inherit;
    font-size: var(--type-caption);
    cursor: pointer;
    transition: background var(--dur-fast) ease;
  }
  .tool-btn:hover {
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    border-color: var(--accent);
  }
  .tool-btn.night {
    margin-left: auto;
    font-weight: 600;
  }

  .color-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
    gap: 12px;
    margin-top: 6px;
  }

  .color-control {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .color-title {
    font-size: 11px;
    color: var(--on-stage-soft);
  }

  .color-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .color-picker {
    width: 38px;
    height: 38px;
    padding: 0;
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--on-stage) 20%, transparent);
    cursor: pointer;
    background: none;
  }

  .hex-input {
    width: 6.5rem;
    padding: 7px 8px;
    border-radius: 6px;
    border: 1px solid color-mix(in srgb, var(--on-stage) 18%, transparent);
    background: color-mix(in srgb, var(--stage) 80%, black);
    color: var(--on-stage);
    font-family: monospace;
    font-size: 12px;
  }

  .font-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .chip {
    padding: 6px 12px;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--on-stage) 16%, transparent);
    background: none;
    color: var(--on-stage);
    font-size: var(--type-caption);
    cursor: pointer;
  }
  .chip.active {
    background: var(--accent);
    color: var(--stage);
    border-color: var(--accent);
    font-weight: 600;
  }

  .footer {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px 20px;
    border-top: 1px solid color-mix(in srgb, var(--on-stage) 10%, transparent);
  }

  .spacer {
    flex: 1;
  }

  .btn {
    padding: 9px 18px;
    border-radius: 10px;
    font: inherit;
    font-size: var(--type-sm);
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: opacity var(--dur-fast) ease;
  }
  .btn:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .btn.primary {
    background: var(--accent);
    color: var(--stage);
    font-weight: 600;
  }
  .btn.secondary {
    background: color-mix(in srgb, var(--on-stage) 10%, transparent);
    color: var(--on-stage);
  }
  .btn.danger {
    background: color-mix(in srgb, #ff453a 20%, transparent);
    color: #ff453a;
  }
</style>
