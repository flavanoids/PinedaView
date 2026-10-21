<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import {
    PHOTO_CLOCK_FONTS,
    resolvePhotoClock,
    type PhotoClockGlass,
    type PhotoClockLayout,
    type PhotoClockSettings,
    type PhotoClockSize,
    type PhotoClockTransition,
  } from "../lib/clockface.svelte";
  import { useSettings } from "../lib/settings.svelte";
  import PhotoClockPreview from "./PhotoClockPreview.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import ResetButton from "./settings/ResetButton.svelte";
  import Scope from "./settings/Scope.svelte";
  import Segmented from "./settings/Segmented.svelte";
  import Switch from "./settings/Switch.svelte";

  const settings = useSettings();
  const screen = $derived(settings.screen);

  const PEEKS = [
    { value: "30", label: "30 s" },
    { value: "60", label: "1 min" },
    { value: "120", label: "2 min" },
    { value: "300", label: "5 min" },
  ] as const;

  const PHOTO_SIZES: { value: PhotoClockSize; label: string }[] = [
    { value: "s", label: "S" },
    { value: "m", label: "M" },
    { value: "l", label: "L" },
    { value: "xl", label: "XL" },
  ];
  const GLASS: { value: PhotoClockGlass; label: string }[] = [
    { value: "liquid", label: "Liquid" },
    { value: "frosted", label: "Frosted" },
    { value: "crystal", label: "Crystal" },
    { value: "flat", label: "Flat" },
  ];
  /** Looks drawn in each photo's own colours, in place of the glass. */
  const INKS: { value: PhotoClockGlass; label: string }[] = [
    { value: "mesh", label: "Blend" },
    { value: "match", label: "Photo" },
    { value: "opposite", label: "Opposite" },
    { value: "chrome", label: "Chrome" },
    { value: "print", label: "Print" },
    { value: "neon", label: "Neon" },
  ];
  const LAYOUTS: { value: PhotoClockLayout; label: string }[] = [
    { value: "row", label: "Row" },
    { value: "stack", label: "Stacked" },
  ];
  const TRANSITIONS: { value: PhotoClockTransition; label: string }[] = [
    { value: "swipe", label: "Swipe" },
    { value: "fade", label: "Fade" },
  ];
  const FACES = [
    { value: "digits", label: "Numbers" },
    { value: "hands", label: "Round" },
  ] as const;
  const MOTIONS = [
    { value: "tick", label: "Tick" },
    { value: "smooth", label: "Smooth" },
  ] as const;

  const photoClock = $derived(resolvePhotoClock(screen?.photo_clock));
  function updatePhotoClock(patch: Partial<PhotoClockSettings>): void {
    void settings.saveScreen({ photo_clock: { ...photoClock, ...patch } });
  }
  /** The opacity slider while it's held, before it's saved. */
  let opacityDraft = $state<number | null>(null);
  const opacity = $derived(opacityDraft ?? photoClock.opacity);
  /** The film grain slider while held. */
  let grainDraft = $state<number | null>(null);
  const grain = $derived(grainDraft ?? photoClock.grain);
  let previewing = $state(false);

  const dimming = $derived(!!(screen?.dim_start && screen?.dim_end));
  const screenOff = $derived(
    !!(screen?.blackout_start && screen?.blackout_end),
  );
  const peekValue = $derived(String(screen?.peek_s ?? 60));
  const peeks = $derived(
    PEEKS.some((p) => p.value === peekValue)
      ? PEEKS
      : [...PEEKS, { value: peekValue, label: `${peekValue} s` }],
  );
</script>

{#if screen}
  <Scope kind="screen" name={settings.editingHere ? "" : screen.name} />

  <Group
    title="Night clock"
    description="Late at night the dashboard gives way to a large, dim clock on black."
  >
    <Field label="Night clock">
      {#snippet children(id)}
        <Switch
          {id}
          checked={screen.night_clock}
          onchange={(on) =>
            settings.saveScreen(
              on
                ? { night_clock: true }
                : { night_clock: false, night_clock_hold: false },
            )}
        />
      {/snippet}
    </Field>
    {#if screen.night_clock}
      <Field
        label="School nights start at"
        hint="Sunday to Thursday. A time after midnight still counts as that night."
      >
        {#snippet children(id)}
          <input
            {id}
            type="time"
            value={screen.night_weeknight_start}
            onchange={(e) =>
              settings.saveScreen({
                night_weeknight_start: e.currentTarget.value,
              })}
          />
        {/snippet}
      </Field>
      <Field label="Weekend nights start at" hint="Friday and Saturday.">
        {#snippet children(id)}
          <input
            {id}
            type="time"
            value={screen.night_weekend_start}
            onchange={(e) =>
              settings.saveScreen({
                night_weekend_start: e.currentTarget.value,
              })}
          />
        {/snippet}
      </Field>
      <Field label="Until" hint="When the dashboard comes back each morning.">
        {#snippet children(id)}
          <input
            {id}
            type="time"
            value={screen.night_end}
            onchange={(e) =>
              settings.saveScreen({ night_end: e.currentTarget.value })}
          />
        {/snippet}
      </Field>
      <Field
        label="A tap shows the dashboard for"
        hint="Then the night clock comes back."
      >
        {#snippet children(id)}
          <Segmented
            {id}
            options={peeks}
            value={peekValue}
            onchange={(v) => settings.saveScreen({ peek_s: Number(v) })}
          />
        {/snippet}
      </Field>
      <Field
        label="Show it now"
        hint="Keeps the night clock up, day or night, until you turn this off."
      >
        {#snippet children(id)}
          <Switch
            {id}
            checked={screen.night_clock_hold}
            onchange={(on) =>
              settings.saveScreen({
                night_clock_hold: on,
                ...(on ? { alternate: false } : {}),
              })}
          />
        {/snippet}
      </Field>
      <Field
        label="Alternate with cards"
        hint="Takes turns: the Photo Clock for 1 min, then the cards for 30 s, with handoff animations."
      >
        {#snippet children(id)}
          <Switch
            {id}
            checked={screen.alternate}
            onchange={(on) =>
              settings.saveScreen({
                alternate: on,
                ...(on
                  ? { night_clock_hold: false, night_clock_photo: true }
                  : {}),
              })}
          />
        {/snippet}
      </Field>
      <Field
        label="Show photos"
        hint="While it's shown now: your photos fill the screen with the time over them, tucked behind the people in them. The small-hours clock stays dark."
      >
        {#snippet children(id)}
          <Switch
            {id}
            checked={screen.night_clock_photo}
            onchange={(on) => settings.saveScreen({ night_clock_photo: on })}
          />
        {/snippet}
      </Field>
      {#if screen.night_clock_photo || screen.alternate}
        <Field
          label="Photo clock"
          hint="Glass numbers over the full-screen photos, or a round clock: the photos in a circle with glass hands."
        >
          {#snippet children(id)}
            <Segmented
              {id}
              options={FACES}
              value={photoClock.face}
              onchange={(face) => updatePhotoClock({ face })}
            />
          {/snippet}
        </Field>
        {#if photoClock.face === "hands"}
          <Field label="Second hand">
            {#snippet children(id)}
              <Switch
                {id}
                checked={photoClock.seconds}
                onchange={(seconds) => updatePhotoClock({ seconds })}
              />
            {/snippet}
          </Field>
          <Field
            label="Hands move"
            hint={photoClock.sweep
              ? "The hands glide, redrawn 60 times a second with a second hand. That keeps the screen busy all the time, so it costs more power and heat than ticking."
              : "The second hand ticks once a second and the minute hand once a minute."}
          >
            {#snippet children(id)}
              <Segmented
                {id}
                options={MOTIONS}
                value={photoClock.sweep ? "smooth" : "tick"}
                onchange={(v) => updatePhotoClock({ sweep: v === "smooth" })}
              />
            {/snippet}
          </Field>
        {/if}
        {#if photoClock.face !== "hands"}
          <Field label="Photo clock font">
            {#snippet children(id)}
              <select
                {id}
                value={photoClock.font}
                onchange={(e) =>
                  updatePhotoClock({
                    font: e.currentTarget.value as typeof photoClock.font,
                  })}
              >
                {#each PHOTO_CLOCK_FONTS as f (f.id)}
                  <option value={f.id}>{f.label}</option>
                {/each}
              </select>
            {/snippet}
          </Field>
          <Field label="Photo clock size">
            {#snippet children(id)}
              <Segmented
                {id}
                options={PHOTO_SIZES}
                value={photoClock.size}
                onchange={(size) => updatePhotoClock({ size })}
              />
            {/snippet}
          </Field>
        {/if}
        <Field
          label="Glass"
          hint={photoClock.face === "hands"
            ? "How the hands catch the photo behind them."
            : "How the numbers catch the photo behind them."}
        >
          {#snippet children(id)}
            <Segmented
              {id}
              options={GLASS}
              value={photoClock.glass}
              onchange={(glass) => updatePhotoClock({ glass })}
            />
          {/snippet}
        </Field>
        {#if photoClock.face !== "hands"}
          <Field
            label="Photo colours"
            hint="Numbers in each photo's own colours instead of glass: a blend, its main colour, the opposite colour, chrome, a two-ink print or neon."
          >
            {#snippet children(id)}
              <Segmented
                {id}
                options={INKS}
                value={photoClock.glass}
                onchange={(glass) => updatePhotoClock({ glass })}
              />
            {/snippet}
          </Field>
        {/if}
        <Field
          label="Glass opacity"
          hint={`${Math.round(opacity * 100)}%. Lower is clearer glass that shows more of the photo; higher is milkier and easier to read.`}
          stacked
        >
          {#snippet children(id)}
            <input
              {id}
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={opacity}
              oninput={(e) => (opacityDraft = Number(e.currentTarget.value))}
              onchange={(e) => {
                opacityDraft = null;
                updatePhotoClock({ opacity: Number(e.currentTarget.value) });
              }}
            />
          {/snippet}
        </Field>
        <Field
          label="Preview"
          hint="Shows the photo clock full screen here, with its glass controls, so you can see each change as you make it."
        >
          {#snippet children()}
            <button
              type="button"
              class="btn"
              onclick={() => (previewing = true)}>Preview</button
            >
          {/snippet}
        </Field>
        {#if photoClock.face !== "hands"}
          <Field
            label="Tuck the time behind people"
            hint="Photos marked ✨ in Photos have a cutout; others keep the time in front."
          >
            {#snippet children(id)}
              <Switch
                {id}
                checked={photoClock.depth}
                onchange={(depth) => updatePhotoClock({ depth })}
              />
            {/snippet}
          </Field>
        {/if}
        <Field label="Show the date">
          {#snippet children(id)}
            <Switch
              {id}
              checked={photoClock.date}
              onchange={(date) => updatePhotoClock({ date })}
            />
          {/snippet}
        </Field>
        {#if photoClock.face !== "hands"}
          <Field
            label="Digits layout"
            hint="Row keeps time side-by-side; stacked places hours over minutes for portrait framing."
          >
            {#snippet children(id)}
              <Segmented
                {id}
                options={LAYOUTS}
                value={photoClock.layout}
                onchange={(layout) => updatePhotoClock({ layout })}
              />
            {/snippet}
          </Field>
        {/if}
        <Field
          label="Transition"
          hint="Swipe slides the next photo from the side; fade dissolves softly between photos."
        >
          {#snippet children(id)}
            <Segmented
              {id}
              options={TRANSITIONS}
              value={photoClock.transition}
              onchange={(transition) => updatePhotoClock({ transition })}
            />
          {/snippet}
        </Field>
        <Field
          label="Motion drift"
          hint="Gentle 3D parallax zoom while each photo is on screen."
        >
          {#snippet children(id)}
            <Switch
              {id}
              checked={photoClock.drift}
              onchange={(drift) => updatePhotoClock({ drift })}
            />
          {/snippet}
        </Field>
        <Field
          label="Memory whisper"
          hint="Briefly reveals the memory date and year of the photo, then softly dissolves away."
        >
          {#snippet children(id)}
            <Switch
              {id}
              checked={photoClock.whisper}
              onchange={(whisper) => updatePhotoClock({ whisper })}
            />
          {/snippet}
        </Field>
        <Field
          label="Weather in date"
          hint="Subtly shows current temperature and condition glyph in the date pill."
        >
          {#snippet children(id)}
            <Switch
              {id}
              checked={photoClock.weather}
              onchange={(weather) => updatePhotoClock({ weather })}
            />
          {/snippet}
        </Field>
        <Field
          label="Film grain"
          hint={`${Math.round(grain * 100)}%. Fine-art analog texture to soften digital screen glare.`}
          stacked
        >
          {#snippet children(id)}
            <input
              {id}
              type="range"
              min="0"
              max="0.25"
              step="0.05"
              value={grain}
              oninput={(e) => (grainDraft = Number(e.currentTarget.value))}
              onchange={(e) => {
                grainDraft = null;
                updatePhotoClock({ grain: Number(e.currentTarget.value) });
              }}
            />
          {/snippet}
        </Field>
      {/if}
    {/if}
  </Group>
  {#if previewing}
    <PhotoClockPreview
      settings={photoClock}
      font={screen.night_clock_font}
      tint={screen.night_clock_tint}
      sizes={PHOTO_SIZES}
      glasses={GLASS}
      inks={INKS}
      onchange={updatePhotoClock}
      onclose={() => (previewing = false)}
    />
  {/if}

  <Group title="Brightness">
    <Field
      label="Brightness"
      hint={`${Math.round(screen.brightness * 100)}%. Dims the picture in the browser; the screen's own backlight isn't changed.`}
      stacked
    >
      {#snippet children(id)}
        <input
          {id}
          type="range"
          min="0.1"
          max="1"
          step="0.05"
          value={screen.brightness}
          onchange={(e) =>
            settings.saveScreen({ brightness: Number(e.currentTarget.value) })}
        />
      {/snippet}
    </Field>
    <Field label="Dim on a schedule" hint="Lower the brightness every evening.">
      {#snippet children(id)}
        <Switch
          {id}
          checked={dimming}
          onchange={(on) =>
            settings.saveScreen(
              on
                ? { dim_start: "21:00", dim_end: "07:00" }
                : { dim_start: "", dim_end: "" },
            )}
        />
      {/snippet}
    </Field>
    {#if dimming}
      <Field label="Dim from">
        {#snippet children(id)}
          <span class="times">
            <input
              {id}
              type="time"
              value={screen.dim_start}
              onchange={(e) =>
                settings.saveScreen({ dim_start: e.currentTarget.value })}
            />
            <span>to</span>
            <input
              type="time"
              aria-label="Dim until"
              value={screen.dim_end}
              onchange={(e) =>
                settings.saveScreen({ dim_end: e.currentTarget.value })}
            />
          </span>
        {/snippet}
      </Field>
      <Field
        label="Dimmed brightness"
        hint={`${Math.round(screen.dim_level * 100)}%`}
        stacked
      >
        {#snippet children(id)}
          <input
            {id}
            type="range"
            min="0.1"
            max="1"
            step="0.05"
            value={screen.dim_level}
            onchange={(e) =>
              settings.saveScreen({ dim_level: Number(e.currentTarget.value) })}
          />
        {/snippet}
      </Field>
    {/if}
  </Group>

  <Group title="Screen off">
    <Field
      label="Go dark on a schedule"
      hint="The screen goes almost completely black between these times, night clock included."
    >
      {#snippet children(id)}
        <Switch
          {id}
          checked={screenOff}
          onchange={(on) =>
            settings.saveScreen(
              on
                ? { blackout_start: "23:00", blackout_end: "06:00" }
                : { blackout_start: "", blackout_end: "" },
            )}
        />
      {/snippet}
    </Field>
    {#if screenOff}
      <Field label="Dark from">
        {#snippet children(id)}
          <span class="times">
            <input
              {id}
              type="time"
              value={screen.blackout_start}
              onchange={(e) =>
                settings.saveScreen({ blackout_start: e.currentTarget.value })}
            />
            <span>to</span>
            <input
              type="time"
              aria-label="Dark until"
              value={screen.blackout_end}
              onchange={(e) =>
                settings.saveScreen({ blackout_end: e.currentTarget.value })}
            />
          </span>
        {/snippet}
      </Field>
    {/if}
  </Group>

  <ResetButton
    what="the night clock, dimming and screen-off times for {screen.name}"
    onreset={async () => {
      const done = await settings.save(
        () =>
          settings.client.resetSection({
            section: "night",
            device_id: screen.id,
          }),
        "Night settings reset",
      );
      if (done) await settings.load();
    }}
  />
{/if}
