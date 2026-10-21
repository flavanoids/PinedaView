<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Theme } from "@pinedaview/protocol";
  import { FONTS, pickableThemes, type FontId } from "@pinedaview/tokens";

  import { FACES, type ClockFace } from "../lib/clockface.svelte";
  import {
    display,
    setDisplaySize,
    type DisplaySize,
  } from "../lib/display.svelte";
  import { useSettings } from "../lib/settings.svelte";
  import ClockFacePreview from "./ClockFacePreview.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import ResetButton from "./settings/ResetButton.svelte";
  import Scope from "./settings/Scope.svelte";
  import Segmented from "./settings/Segmented.svelte";
  import Switch from "./settings/Switch.svelte";
  import ShapeSettings from "./ShapeSettings.svelte";
  import ThemePreviewCard from "./ThemePreviewCard.svelte";
  import ThemeStudio from "./ThemeStudio.svelte";

  const settings = useSettings();
  const client = settings.client;
  const profile = $derived(settings.profile);

  const SIZES: { value: DisplaySize; label: string }[] = [
    { value: "auto", label: "Auto" },
    { value: "s", label: "S" },
    { value: "m", label: "M" },
    { value: "l", label: "L" },
    { value: "xl", label: "XL" },
  ];

  // A small, legible-on-dark-and-light set; "Custom…" covers the rest.
  const SWATCHES = [
    { hex: "#e0614a", name: "Coral" },
    { hex: "#e8a33d", name: "Amber" },
    { hex: "#7cb342", name: "Leaf" },
    { hex: "#26a69a", name: "Teal" },
    { hex: "#3d8bfd", name: "Blue" },
    { hex: "#7e57c2", name: "Violet" },
    { hex: "#d6539a", name: "Rose" },
    { hex: "#a1887f", name: "Clay" },
  ];

  let themes = $state<Theme[]>([]);
  let hasWallpaper = $state(false);
  let wallpaperRev = $state(Date.now());
  let wallpaperBusy = $state(false);

  $effect(() => {
    void client.listThemes().then((list) => (themes = list.themes));
    void client.hasWallpaper().then((has) => (hasWallpaper = has));
  });

  const theme = $derived(themes.find((t) => t.name === profile?.theme));
  const glass = $derived(theme?.surface === "glass");
  const nightTwin = $derived(
    themes.find((t) => t.name === theme?.night)?.label,
  );
  const pickable = $derived(pickableThemes(themes));

  let studioOpen = $state(false);
  let studioTheme = $state<Theme | null>(null);

  function openStudio(editTheme?: Theme | null): void {
    studioTheme = editTheme ?? null;
    studioOpen = true;
  }

  async function onThemeSaved(saved: Theme): Promise<void> {
    const list = await client.listThemes();
    themes = list.themes;
    settings.flash(studioTheme ? "Theme updated" : "Theme created");
    await settings.saveProfile({ theme: saved.name });
  }

  async function onThemeDeleted(deletedName: string): Promise<void> {
    const list = await client.listThemes();
    themes = list.themes;
    settings.flash("Theme deleted");
    if (profile?.theme === deletedName) {
      await settings.saveProfile({ theme: "blush" });
    }
  }

  async function uploadWallpaper(event: Event): Promise<void> {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    wallpaperBusy = true;
    const ok = await settings.attempt(
      () => client.setWallpaper(file),
      "Background updated",
    );
    wallpaperBusy = false;
    input.value = "";
    if (ok) {
      hasWallpaper = true;
      wallpaperRev = Date.now();
    }
  }

  async function removeWallpaper(): Promise<void> {
    if (
      await settings.attempt(
        () => client.clearWallpaper(),
        "Background removed",
      )
    )
      hasWallpaper = false;
  }
</script>

{#if profile}
  <Scope kind="profile" name={profile.name} />

  <ShapeSettings />

  <Group title="Colour">
    <div class="theme-header">
      <div class="theme-header-text">
        <span class="theme-heading">Theme</span>
        {#if theme?.blurb}<p class="theme-blurb">{theme.blurb}</p>{/if}
      </div>
      <button
        type="button"
        class="make-theme-btn"
        onclick={() => openStudio(null)}
      >
        <span aria-hidden="true">+</span> Make a theme
      </button>
    </div>

    <div class="theme-grid" role="radiogroup" aria-label="Theme selection">
      {#each pickable as t (t.name)}
        <ThemePreviewCard
          theme={t}
          selected={profile.theme === t.name}
          onSelect={() => settings.saveProfile({ theme: t.name })}
          onEdit={(th) => openStudio(th)}
        />
      {/each}
    </div>

    <Field
      label="After sunset"
      hint="Switch to darker colours from sunset to sunrise."
    >
      {#snippet children(id)}
        <select
          {id}
          value={profile.night_theme ?? ""}
          onchange={(e) =>
            settings.saveProfile({ night_theme: e.currentTarget.value })}
        >
          <option value=""
            >{nightTwin ? `Use ${nightTwin}` : "No change"}</option
          >
          {#if nightTwin}<option value="off">No change</option>{/if}
          <optgroup label="Switch to">
            {#each themes.filter((t) => t.name !== profile.theme && t.name !== theme?.night) as t (t.name)}
              <option value={t.name}>{t.label}</option>
            {/each}
          </optgroup>
        </select>
      {/snippet}
    </Field>

    <Field
      label="Accent colour"
      hint="Used for highlights, buttons and switches."
      stacked
    >
      {#snippet children()}
        <div class="swatches" role="radiogroup" aria-label="Accent colour">
          <button
            type="button"
            role="radio"
            class="swatch theme"
            aria-checked={!profile.accent}
            title="The theme's own"
            onclick={() => settings.saveProfile({ accent: "" })}
            ><span>Theme</span></button
          >
          {#each SWATCHES as s (s.hex)}
            <button
              type="button"
              role="radio"
              class="swatch"
              style:background={s.hex}
              aria-checked={profile.accent?.toLowerCase() === s.hex}
              aria-label={s.name}
              title={s.name}
              onclick={() => settings.saveProfile({ accent: s.hex })}
            ></button>
          {/each}
          <label class="swatch custom" title="Custom colour">
            <input
              type="color"
              aria-label="Custom accent colour"
              value={profile.accent ?? theme?.accent ?? "#888888"}
              onchange={(e) =>
                settings.saveProfile({ accent: e.currentTarget.value })}
            />
          </label>
        </div>
      {/snippet}
    </Field>

    <Field
      label="Animated background"
      hint={glass
        ? "Liquid Glass has its own background, so this shows on the other themes."
        : "A slow drift of the theme's colours behind the cards."}
    >
      {#snippet children(id)}
        <Switch
          {id}
          checked={profile.animated_background}
          onchange={(on) => settings.saveProfile({ animated_background: on })}
        />
      {/snippet}
    </Field>
  </Group>

  <Group title="Text">
    <Field
      label="Font"
      hint="Used for everything except the clock. Stays the same when you change themes."
      stacked
    >
      {#snippet children()}
        <div class="fonts" role="radiogroup" aria-label="Font">
          <button
            type="button"
            role="radio"
            aria-checked={!profile.font}
            class:on={!profile.font}
            onclick={() => settings.saveProfile({ font: "" })}
          >
            <span class="specimen">Theme default</span>
            <span class="note">The font this theme was designed with.</span>
          </button>
          {#each FONTS as font (font.id)}
            <button
              type="button"
              role="radio"
              aria-checked={profile.font === font.id}
              class:on={profile.font === font.id}
              onclick={() => settings.saveProfile({ font: font.id as FontId })}
            >
              <span class="specimen" style:font-family={font.stack}
                >{font.label}</span
              >
              <span class="note">{font.note}</span>
            </button>
          {/each}
        </div>
      {/snippet}
    </Field>
  </Group>

  <Group title="Clock">
    <Field
      label="Clock face for every screen"
      hint="Pick one face for every screen on this profile, or let each screen choose its own."
    >
      {#snippet children(id)}
        <select
          {id}
          value={profile.clock_face ?? ""}
          onchange={(e) =>
            settings.saveProfile({
              clock_face: e.currentTarget.value as ClockFace | "",
            })}
        >
          <option value="">Each screen chooses</option>
          {#each FACES as f (f.id)}
            <option value={f.id}>{f.label}</option>
          {/each}
        </select>
      {/snippet}
    </Field>
    {#if settings.editingHere}
      <Field
        label="This screen's clock face"
        hint={profile.clock_face
          ? "Set for every screen above. Choose “Each screen chooses” to pick one here."
          : "Dial and word faces always read in 12-hour time."}
        stacked
      >
        {#snippet children()}
          <ClockFacePreview />
        {/snippet}
      </Field>
    {/if}
  </Group>

  <Group
    title="Background image"
    description={glass
      ? "Liquid Glass shows this behind the cards. With no image, it uses its built-in gradient."
      : "Shown behind the cards on Liquid Glass, and on this theme too if you turn that on below."}
  >
    <div class="wallpaper">
      {#if hasWallpaper}
        <img
          class="wp-preview"
          src={client.wallpaperUrl(wallpaperRev)}
          alt="Current background"
        />
      {/if}
      <div class="wp-actions">
        <label class="btn" class:busy={wallpaperBusy}>
          {wallpaperBusy
            ? "Uploading…"
            : hasWallpaper
              ? "Replace image"
              : "Choose image"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={wallpaperBusy}
            onchange={uploadWallpaper}
          />
        </label>
        {#if hasWallpaper}
          <button type="button" class="btn danger" onclick={removeWallpaper}
            >Remove</button
          >
        {/if}
      </div>
      <p class="hint">You can also use any photo from Photos.</p>
    </div>
    <Field
      label="Use with every theme"
      hint="Show the image behind solid themes as well, softened so the cards stay readable."
    >
      {#snippet children(id)}
        <Switch
          {id}
          checked={profile.wallpaper_everywhere}
          disabled={!hasWallpaper}
          onchange={(on) => settings.saveProfile({ wallpaper_everywhere: on })}
        />
      {/snippet}
    </Field>
  </Group>

  {#if settings.editingHere}
    <Group title="This device">
      <Field
        label="Interface size"
        hint={`Scales text, spacing and cards together. Auto picked ${Math.round(display.detected * 100)}% for this screen.`}
      >
        {#snippet children(id)}
          <Segmented
            {id}
            options={SIZES}
            value={display.choice}
            onchange={setDisplaySize}
          />
        {/snippet}
      </Field>
    </Group>
  {/if}

  <ResetButton
    what="the accent colour, after-sunset theme, font, clock face and background options. The theme and background image stay as they are"
    onreset={async () => {
      const config = await settings.save(
        () =>
          client.resetSection({
            section: "appearance",
            profile_id: profile.id,
          }),
        "Appearance reset",
      );
      if (config) await settings.load();
    }}
  />

  {#if studioOpen}
    <ThemeStudio
      initialTheme={studioTheme}
      {themes}
      currentProfileTheme={profile.theme}
      onClose={() => {
        studioOpen = false;
        studioTheme = null;
      }}
      onSaved={onThemeSaved}
      onDeleted={onThemeDeleted}
    />
  {/if}
{/if}

<style>
  .theme-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: var(--space-2);
  }
  .theme-header-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .theme-heading {
    font-size: var(--type-sm);
    font-weight: 600;
  }
  .theme-blurb {
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
  }
  .make-theme-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--on-stage);
    font: inherit;
    font-size: var(--type-caption);
    font-weight: 600;
    cursor: pointer;
    transition:
      background var(--dur-fast) ease,
      color var(--dur-fast) ease;
    white-space: nowrap;
  }
  .make-theme-btn:hover {
    background: var(--accent);
    color: var(--stage);
  }
  .theme-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .swatches {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .swatch {
    position: relative;
    width: 2.25rem;
    height: 2.25rem;
    padding: 0;
    border-radius: 50%;
    border: 2px solid transparent;
    box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.15);
    cursor: pointer;
  }
  .swatch[aria-checked="true"] {
    border-color: var(--on-stage);
    outline: 2px solid var(--stage);
    outline-offset: -4px;
  }
  .swatch.theme {
    width: auto;
    padding: 0 12px;
    border-radius: var(--radius-pill);
    background: color-mix(in srgb, var(--on-stage) 8%, transparent);
    color: var(--on-stage);
    font: inherit;
    font-size: var(--type-caption);
  }
  .swatch.custom {
    overflow: hidden;
    background: conic-gradient(
      #e0614a,
      #e8a33d,
      #7cb342,
      #26a69a,
      #3d8bfd,
      #7e57c2,
      #d6539a,
      #e0614a
    );
  }
  .swatch.custom input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }
  .fonts {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr));
    gap: var(--space-2);
  }
  .fonts button {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    padding: 10px 12px;
    border-radius: 12px;
    border: 1px solid color-mix(in srgb, var(--on-stage) 14%, transparent);
    background: none;
    color: var(--on-stage);
    font: inherit;
    text-align: start;
    cursor: pointer;
  }
  .fonts button.on {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
  }
  .specimen {
    font-size: calc(var(--type-sm) * 1.25);
    font-weight: 500;
    line-height: 1.15;
  }
  .note {
    font-size: var(--type-caption);
    line-height: 1.35;
    color: var(--on-stage-soft);
  }
  .wallpaper {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: 12px 0;
  }
  .wp-preview {
    width: 100%;
    max-height: 140px;
    object-fit: cover;
    border-radius: 12px;
  }
  .wp-actions {
    display: flex;
    gap: var(--space-2);
  }
  .wp-actions input {
    display: none;
  }
  .busy {
    opacity: 0.6;
  }
</style>
