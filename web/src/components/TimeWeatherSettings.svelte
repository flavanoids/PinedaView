<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { formatClock } from "../lib/format";
  import { useSettings } from "../lib/settings.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import ResetButton from "./settings/ResetButton.svelte";
  import Scope from "./settings/Scope.svelte";
  import Segmented from "./settings/Segmented.svelte";
  import Switch from "./settings/Switch.svelte";

  const settings = useSettings();
  const config = $derived(settings.config);

  let detecting = $state(false);

  const sample = new Date();
  sample.setHours(19, 30, 0, 0);
  const DATE_STYLES = [
    { value: "long", label: "Full" },
    { value: "short", label: "Short" },
    { value: "off", label: "Hidden" },
  ] as const;
  const datePreview = $derived(
    config?.date_style === "off"
      ? "The clock shows only the time."
      : `Under the clock: ${formatClock(sample, false, config?.date_style ?? "long").date}.`,
  );

  async function useDetected(): Promise<void> {
    detecting = true;
    const found = await settings.save(
      () => settings.client.detectLocation(),
      "",
    );
    detecting = false;
    if (!found) {
      settings.flash(
        "Couldn't work out where this is. Type a city instead.",
        true,
      );
      return;
    }
    await settings.saveConfig({
      location_query: found.query,
      location_label: found.label,
    });
  }
</script>

{#if config}
  <Scope kind="home" />

  <Group title="Location">
    <Field
      label="Weather for"
      hint={config.location_label &&
      config.location_label !== config.location_query
        ? `Showing ${config.location_label}. Type a city, a US ZIP code, or “latitude,longitude”.`
        : "Type a city, a US ZIP code, or “latitude,longitude”."}
      stacked
    >
      {#snippet children(id)}
        <div class="location">
          <input
            {id}
            value={config.location_query}
            autocomplete="off"
            onchange={(e) => {
              const query = e.currentTarget.value.trim();
              if (query)
                void settings.saveConfig({
                  location_query: query,
                  location_label: "",
                });
            }}
          />
          <button
            type="button"
            class="btn"
            disabled={detecting}
            onclick={useDetected}
            >{detecting ? "Finding…" : "Find my location"}</button
          >
        </div>
      {/snippet}
    </Field>
  </Group>

  <Group title="Format">
    <Field label="Temperature">
      {#snippet children(id)}
        <Segmented
          {id}
          options={[
            { value: "imperial", label: "°F" },
            { value: "metric", label: "°C" },
          ]}
          value={config.units}
          onchange={(units) => settings.saveConfig({ units })}
        />
      {/snippet}
    </Field>
    <Field
      label="Clock"
      hint={config.time_format === "24h" ? "19:30" : "7:30 PM"}
    >
      {#snippet children(id)}
        <Segmented
          {id}
          options={[
            { value: "12h", label: "12-hour" },
            { value: "24h", label: "24-hour" },
          ]}
          value={config.time_format}
          onchange={(time_format) => settings.saveConfig({ time_format })}
        />
      {/snippet}
    </Field>
    <Field label="Date" hint={datePreview}>
      {#snippet children(id)}
        <Segmented
          {id}
          options={DATE_STYLES}
          value={config.date_style}
          onchange={(date_style) => settings.saveConfig({ date_style })}
        />
      {/snippet}
    </Field>
  </Group>

  <Group
    title="Morning countdown"
    description="On weekday mornings the big card counts down to the time you need to leave, then flashes when it's time to go."
  >
    <Field label="Countdown">
      {#snippet children(id)}
        <Switch
          {id}
          checked={config.countdown_enabled}
          onchange={(on) => settings.saveConfig({ countdown_enabled: on })}
        />
      {/snippet}
    </Field>
    {#if config.countdown_enabled}
      <Field label="Show from" hint="When the countdown starts.">
        {#snippet children(id)}
          <input
            {id}
            type="time"
            value={config.countdown_start}
            onchange={(e) =>
              settings.saveConfig({ countdown_start: e.currentTarget.value })}
          />
        {/snippet}
      </Field>
      <Field label="Time to leave" hint="When it reaches zero.">
        {#snippet children(id)}
          <input
            {id}
            type="time"
            value={config.countdown_end}
            onchange={(e) =>
              settings.saveConfig({ countdown_end: e.currentTarget.value })}
          />
        {/snippet}
      </Field>
    {/if}
  </Group>

  <ResetButton
    what="the temperature units, clock and date format. Your location and countdown stay as they are"
    onreset={async () => {
      const updated = await settings.save(
        () => settings.client.resetSection({ section: "time" }),
        "Time & weather reset",
      );
      if (updated) settings.config = updated;
    }}
  />
{/if}

<style>
  .location {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .location input {
    flex: 1 1 12rem;
  }
</style>
