<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The weather card, three pages on a slow cycle:

    1. Now — the current temperature and its conditions glyph, biggest; under
       them the next five days in columns (high, low and rain chance).
    2. Next 12 hours — the temperature as a curve with its high and low set
       on the line, a rain chance for every hour under it (even the small
       ones), after-dark hours shaded, and sunset/sunrise marked.
    3. Today vs. normal — how far today's high is from the 1991–2020 normal,
       where today sits between the record low and high for the date (with
       their years), then wind, humidity and UV. Outside the US there are no
       records to show, so the page is just those three.

  Everything is drawn in the theme's own ink and type, so it follows
  whatever theme is on. Radar lives on its own card.
-->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import Cycler from "../components/Cycler.svelte";
  import { glyphFor } from "../components/WeatherGlyph.svelte";
  import {
    formatHour,
    formatSpeed,
    formatTemp,
    uvBand,
    type Units,
  } from "../lib/format";
  import {
    columnX,
    curvePath,
    nextSun,
    nightRuns,
    sunMarks,
    upcoming,
  } from "../lib/hourly";
  import { paced, prefs } from "../lib/prefs.svelte";
  import { settle } from "../lib/settle";
  import { clock } from "../lib/time.svelte";
  import type { CardProps, WeatherData } from "./types";
  import Placeholder from "../components/Placeholder.svelte";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();
  const units = $derived(view.units as Units);
  const weather = $derived(pick<WeatherData>(view, "weather"));
  const current = $derived(weather?.current);
  const forecast = $derived(weather?.forecast ?? []);
  const today = $derived(forecast[0]);
  // Today's high and low sit under the reading, so the outlook starts tomorrow.
  const days = $derived(forecast.slice(1, 6));
  const temp = $derived(formatTemp(current?.tempC, units));

  const CYCLE_MS = 13_000;

  /** "Tue" — short and one width for every column. */
  function weekday(iso: string): string {
    const date = new Date(`${iso}T12:00:00`);
    return Number.isNaN(date.getTime())
      ? iso
      : date.toLocaleDateString(undefined, { weekday: "short" });
  }

  // A rain chance worth a glance. On the five-day row anything below this
  // stays blank; on the hourly row it's still shown, just quieter.
  const WET = 10;

  // ---- Page 2: the next 12 hours ----
  // Twelve hours where there's room for twelve legible columns; eight on a
  // narrow tile, so every hour's rain chance stays readable.
  const WIDE = 560;
  let width = $state(0);
  const SPAN = $derived(width >= WIDE ? 12 : 8);
  const hours = $derived(
    upcoming(weather?.hourly ?? [], clock.now.getHours(), SPAN),
  );
  // The curve keeps clear of the top (for the high's label and the sunset
  // tag) and the bottom (for the low's label).
  const TOP = 30;
  const BOTTOM = 84;
  const MIN_RANGE = 4.5; // °C
  const points = $derived.by(() => {
    const temps = hours.map((h) => h.tempC ?? null);
    const known = temps.filter((t): t is number => t != null);
    if (known.length < 2) return [];
    // At least ~8°F top to bottom, so a 2° wobble doesn't read as a swing.
    const range = Math.max(Math.max(...known) - Math.min(...known), MIN_RANGE);
    const max = (Math.max(...known) + Math.min(...known) + range) / 2;
    return temps.flatMap((t, i) =>
      t == null
        ? []
        : [
            {
              i,
              t,
              x: columnX(i, hours.length),
              y: TOP + ((max - t) / range) * (BOTTOM - TOP),
            },
          ],
    );
  });
  const curve = $derived(curvePath(points));
  const area = $derived(
    points.length
      ? `${curve}L${points[points.length - 1]!.x},100L${points[0]!.x},100Z`
      : "",
  );
  const peak = $derived(
    points.reduce((a, b) => (b.t > a.t ? b : a), points[0]!),
  );
  const trough = $derived(
    points.reduce((a, b) => (b.t < a.t ? b : a), points[0]!),
  );
  const marks = $derived(
    hours.length ? sunMarks(forecast, hours[0]!.hour, hours.length) : [],
  );
  // A sunrise/sunset tag over the peak would sit on its label, so then the
  // high goes under the line instead.
  const peakTagged = $derived(
    points.length > 0 && marks.some((m) => Math.abs(m.x - peak.x) < 16),
  );
  const night = $derived(nightRuns(hours));
  // The next sunset always shows: on the chart when it falls in the window,
  // otherwise in a note under it — along with the sunrise before it, if
  // that's off the chart too (after dark).
  const sunNotes = $derived.by(() => {
    const ahead = nextSun(
      forecast,
      clock.now.getHours() * 60 + clock.now.getMinutes(),
    );
    const upToSunset = ahead.slice(
      0,
      ahead.findIndex((e) => e.kind === "Sunset") + 1 || ahead.length,
    );
    return upToSunset.filter(
      (e) => !marks.some((m) => m.kind === e.kind && m.time === e.time),
    );
  });

  function hourLabel(hour: number, i: number): string {
    if (i === 0) return "Now";
    return prefs.time_format === "24h"
      ? `${String(hour).padStart(2, "0")}:00`
      : formatHour(hour);
  }

  const hoursSummary = $derived(
    points.length
      ? `Next ${hours.length} hours: high ${formatTemp(peak.t, units)} at ` +
          `${formatHour(hours[peak.i]!.hour)}, low ${formatTemp(trough.t, units)} at ` +
          `${formatHour(hours[trough.i]!.hour)}. Rain chance up to ` +
          `${Math.max(...hours.map((h) => h.precip ?? 0))}%.` +
          (today?.sunset ? ` Sunset ${today.sunset}.` : "")
      : "",
  );

  // ---- Page 3: today vs. normal ----
  const climate = $derived(weather?.climate ?? null);
  /** A Celsius reading in the viewer's units, unrounded, for differences. */
  function inUnits(c: number): number {
    return units === "metric" ? c : (c * 9) / 5 + 32;
  }
  const versus = $derived.by(() => {
    if (climate?.normalHighC == null || today?.highC == null) return null;
    const diff = Math.round(
      inUnits(today.highC) - inUnits(climate.normalHighC),
    );
    if (Math.abs(diff) <= 1) return "Right about normal";
    return `${Math.abs(diff)}° ${diff > 0 ? "warmer" : "cooler"} than normal`;
  });
  const dateLabel = $derived(
    clock.now.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
  );
  // The record bar runs from the record low to the record high — stretched
  // if today breaks either.
  const scale = $derived.by(() => {
    const c = climate;
    if (c?.recordLowC == null || c.recordHighC == null) return null;
    const lo = Math.min(c.recordLowC, today?.lowC ?? Infinity);
    const hi = Math.max(c.recordHighC, today?.highC ?? -Infinity);
    return hi > lo ? { lo, hi } : null;
  });
  function at(c: number | null | undefined): number | null {
    return scale && c != null
      ? ((c - scale.lo) / (scale.hi - scale.lo)) * 100
      : null;
  }
  function span(from: number | null, to: number | null): string {
    return from == null || to == null
      ? "display:none"
      : `left:${from}%;width:${Math.max(to - from, 1.5)}%`;
  }

  const pageCount = $derived(!current ? 1 : hours.length >= 4 ? 3 : 2);
  const PAGES = ["now", "hours", "context"] as const;
  function pageAt(i: number) {
    return pageCount === 2 && i === 1 ? "context" : PAGES[i]!;
  }
</script>

{#snippet drop()}
  <svg class="drop" viewBox="0 0 10 12" aria-hidden="true"
    ><path
      d="M5 .8C3.4 3.4 1.4 5.6 1.4 7.7a3.6 3.6 0 0 0 7.2 0C8.6 5.6 6.6 3.4 5 .8Z"
    /></svg
  >
{/snippet}

{#snippet nowPage()}
  <div class="wx">
    {#if current}
      <div class="now">
        <span class="glyph" aria-hidden="true"
          >{glyphFor(current.code, current.isDay ?? true)}</span
        >
        <span class="temp" use:settle={temp}>{temp}</span>
        <span class="summary">
          <span class="desc">{current.desc ?? ""}</span>
          {#if today?.highC != null}
            <span class="hilo"
              >H {formatTemp(today.highC, units)} · L {formatTemp(
                today.lowC,
                units,
              )}</span
            >
          {/if}
        </span>
      </div>
      {#if days.length}
        <ol class="days">
          {#each days as day (day.date)}
            <li>
              <span class="day">{weekday(day.date)}</span>
              <span class="icon" aria-hidden="true">{glyphFor(day.code)}</span>
              <span class="hi">{formatTemp(day.highC, units)}</span>
              <span class="lo">{formatTemp(day.lowC, units)}</span>
              <span class="pop" class:quiet={(day.precip ?? 0) < WET}
                >{@render drop()}{day.precip ?? 0}%</span
              >
            </li>
          {/each}
        </ol>
      {/if}
    {:else}
      <Placeholder label="Waiting for the forecast…" />
    {/if}
  </div>
{/snippet}

{#snippet hoursPage()}
  <div class="wx hours" style:--n={hours.length}>
    <div class="night" aria-hidden="true">
      {#each night as [from, to] (from)}
        <span
          style:left="{(from / hours.length) * 100}%"
          style:width="{((to - from) / hours.length) * 100}%"
        ></span>
      {/each}
    </div>
    <div class="plot" role="img" aria-label={hoursSummary}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <path class="area" d={area} />
        <path class="line" d={curve} />
      </svg>
      {#each marks as mark (mark.kind + mark.time)}
        <span class="sun" style:left="{mark.x}%" aria-hidden="true"></span>
        <span class="sun-tag" style:--x="{mark.x}%" aria-hidden="true"
          >{mark.kind} {mark.time}</span
        >
      {/each}
      {#if points.length}
        <span class="pt" style:left="{peak.x}%" style:top="{peak.y}%"></span>
        <span
          class="reading"
          class:under={peakTagged}
          style:--x="{peak.x}%"
          style:top="{peak.y}%">{formatTemp(peak.t, units)}</span
        >
        {#if trough.i !== peak.i && trough.t !== peak.t}
          <span class="pt" style:left="{trough.x}%" style:top="{trough.y}%"
          ></span>
          <span
            class="reading low under"
            style:--x="{trough.x}%"
            style:top="{trough.y}%">{formatTemp(trough.t, units)}</span
          >
        {/if}
      {/if}
    </div>
    <ol class="rain" aria-hidden="true">
      {#each hours as h, i (i)}
        <li class:quiet={(h.precip ?? 0) < WET}>
          <span class="bar"
            ><span style:height="{Math.max(h.precip ?? 0, 2)}%"></span></span
          >
          <span class="pct">{h.precip ?? 0}%</span>
        </li>
      {/each}
    </ol>
    <ol class="axis" aria-hidden="true">
      {#each hours as h, i (i)}
        <li>{i % 3 === 0 ? hourLabel(h.hour, i) : ""}</li>
      {/each}
    </ol>
    {#if sunNotes.length}
      <span class="note">
        {#each sunNotes as e (e.kind)}
          <span
            >{e.kind}
            {e.time}{e.kind === "Sunset" && e.tomorrow ? " tomorrow" : ""}</span
          >
        {/each}
      </span>
    {/if}
  </div>
{/snippet}

{#snippet contextPage()}
  <div class="wx context" class:bare={!climate}>
    {#if climate}
      <div class="versus">
        {#if versus}<span class="verdict">{versus}</span>{/if}
        {#if climate.normalHighC != null}
          <span class="normal"
            >A normal {dateLabel} is {formatTemp(climate.normalHighC, units)} and
            {formatTemp(climate.normalLowC, units)}</span
          >
        {/if}
      </div>
      {#if scale}
        <div class="records">
          <div class="track" aria-hidden="true">
            <span
              class="band"
              style={span(at(climate.normalLowC), at(climate.normalHighC))}
            ></span>
            <span class="today" style={span(at(today?.lowC), at(today?.highC))}
            ></span>
          </div>
          <div class="ends">
            <span class="end"
              ><span class="rec">{formatTemp(climate.recordLowC, units)}</span>
              <span class="yr">Record low, {climate.recordLowYear}</span></span
            >
            <span class="end right"
              ><span class="rec">{formatTemp(climate.recordHighC, units)}</span>
              <span class="yr">Record high, {climate.recordHighYear}</span
              ></span
            >
          </div>
          <span class="key"
            ><span class="swatch band"></span>Normal
            <span class="swatch today"></span>Today {formatTemp(
              today?.highC,
              units,
            )} / {formatTemp(today?.lowC, units)}</span
          >
        </div>
      {/if}
    {/if}
    {#if current}
      <dl class="stats">
        <div>
          <dt>Wind</dt>
          <dd>
            {#if current.windDeg != null}
              <svg
                class="arrow"
                viewBox="0 0 12 12"
                aria-hidden="true"
                style:rotate="{current.windDeg + 180}deg"
                ><path d="M6 .8 10 10.6 6 8.3 2 10.6Z" /></svg
              >
            {/if}{formatSpeed(current.windMs, units)}
            <span class="sub">from {current.windDir || "—"}</span>
          </dd>
        </div>
        <div>
          <dt>Humidity</dt>
          <dd>{current.humidity ?? "—"}%</dd>
        </div>
        <div>
          <dt>UV index</dt>
          <dd>
            {current.uvIndex ?? "—"}
            {#if current.uvIndex != null}<span class="sub"
                >{uvBand(current.uvIndex)}</span
              >{/if}
          </dd>
        </div>
      </dl>
    {/if}
  </div>
{/snippet}

<Card accent="weather" {stale} {hero} fill>
  <div class="deck" bind:clientWidth={width}>
    <Cycler count={pageCount} intervalMs={paced(CYCLE_MS)} fill>
      {#snippet item(i)}
        {@const page = pageAt(i)}
        {#if page === "hours"}
          {@render hoursPage()}
        {:else if page === "context"}
          {@render contextPage()}
        {:else}
          {@render nowPage()}
        {/if}
      {/snippet}
    </Cycler>
  </div>
</Card>

<style>
  .deck {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  /* The page dots float in the card's bottom padding rather than taking a
     row from every page. */
  .deck :global(.dots) {
    position: absolute;
    bottom: calc(var(--space-3) * -0.5 - 2px);
    left: 50%;
    translate: -50% 0;
  }
  .deck :global(.cycler) {
    flex: 1;
  }

  /* Each page lays out inside its own box: .wx is a size container, and every
     size below is the smaller of the theme's type token and a share of that
     box. The token wins when there's room (so Interface size and Larger text
     still apply); the box share wins on a tight tile, so the card always fits
     the cell it was given instead of clipping or growing the row. */
  .wx {
    --temp: min(var(--type-hero), 34cqh, 26cqi);
    --lead: min(var(--type-md), 9cqh, 6cqi);
    --note: min(var(--type-sm), 6.4cqh, 4.2cqi);
    /* The day columns: each is a fifth of the width, so the width share
       mostly governs; a squat box falls back on the height share. */
    --body: min(var(--type-lg), 9.5cqh, 8cqi);
    --small: min(var(--type-md), 6.4cqh, 5.5cqi);
    --icon: min(var(--type-lg), 11cqh, 9cqi);
    --gap: min(var(--space-3), 4.5cqh, 3cqi);
    --rule: color-mix(in srgb, var(--on-card) 20%, transparent);
    --wet: color-mix(in srgb, #7cc0ff 70%, var(--on-card));

    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: var(--gap);
    container-type: size;
    /* Phones size rows to content, and a size container has none, so give
       it a floor from the cell's width. Below every tile's own height. */
    min-height: 56cqi;
  }

  /* ---- Now: glyph and temp, the conditions beside them ---- */
  .now {
    flex: 1;
    display: flex;
    align-items: center;
    gap: calc(var(--gap) * 0.8);
    min-height: 0;
  }
  .glyph {
    font-size: calc(var(--temp) * 0.78);
    line-height: 1;
  }
  .temp {
    /* Fraunces, same as the clock: the current temp reads as a matching
       object rather than UI text. */
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-weight: 700;
    letter-spacing: -0.035em;
    font-size: var(--temp);
    line-height: 0.9;
  }
  .summary {
    display: flex;
    flex-direction: column;
    gap: 0.25em;
    min-width: 0;
    margin-left: calc(var(--gap) * 0.4);
  }
  .desc {
    font-size: var(--lead);
    font-weight: var(--weight-label);
    line-height: 1.1;
  }
  .hilo {
    font-size: var(--note);
    color: var(--on-card-soft);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  /* ---- Next five days, one column each ---- */
  .days {
    list-style: none;
    margin: 0;
    padding: var(--gap) 0 0;
    border-top: 1px solid var(--rule);
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: calc(var(--gap) * 0.5);
  }
  .days li {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: calc(var(--gap) * 0.35);
    min-width: 0;
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  .day {
    font-size: var(--small);
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
    white-space: nowrap;
  }
  .icon {
    font-size: var(--icon);
    line-height: 1;
  }
  .hi {
    font-size: var(--body);
    font-weight: var(--weight-display);
  }
  .lo {
    font-size: var(--small);
    color: var(--on-card-faint);
  }
  .pop {
    display: inline-flex;
    align-items: center;
    gap: 0.15em;
    font-size: var(--small);
    color: var(--wet);
    white-space: nowrap;
  }
  /* Hidden, not removed, so the columns stay the same height. */
  .pop.quiet {
    visibility: hidden;
  }
  .drop {
    width: 0.7em;
    height: 0.85em;
    fill: currentColor;
  }

  /* ---- Next 12 hours: the curve over a rain-chance row ---- */
  .hours {
    /* A twelfth of the width per hour, so the width share governs. */
    --reading: min(var(--type-lg), 13cqh, 7.5cqi);
    /* Sized from one hour's column, so 8 or 12 of them read the same. */
    --tick: min(var(--type-sm), 6.5cqh, calc(40cqi / var(--n)));
    position: relative;
    justify-content: flex-start;
    gap: calc(var(--gap) * 0.45);
  }
  /* After-dark hours: a faint wash down the whole column, curve to clock. */
  .night {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
  .night span {
    position: absolute;
    top: 0;
    bottom: 0;
    background: color-mix(in srgb, var(--on-card) 7%, transparent);
    border-radius: calc(var(--gap) * 0.6);
  }
  .plot {
    position: relative;
    flex: 1;
    min-height: 0;
  }
  .plot svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    overflow: visible;
  }
  .area {
    fill: color-mix(in srgb, var(--on-card) 9%, transparent);
  }
  .line {
    fill: none;
    stroke: var(--on-card);
    stroke-width: 2.5;
    stroke-linecap: round;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
  }
  .pt {
    position: absolute;
    width: 0.55em;
    height: 0.55em;
    font-size: var(--reading);
    border-radius: 50%;
    background: var(--on-card);
    box-shadow: 0 0 0 0.12em var(--card-bg);
    translate: -50% -50%;
  }
  /* The high and low, written on the line in the clock's Fraunces. Clamped
     so an end-of-window reading never hangs off the card. */
  .reading {
    position: absolute;
    left: clamp(1.1em, var(--x), calc(100% - 1.1em));
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-weight: 700;
    letter-spacing: -0.03em;
    font-size: var(--reading);
    line-height: 1;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    /* A halo in the card's own colour, so the line can pass behind. */
    text-shadow:
      0 0 0.12em var(--card-bg),
      0 0 0.25em var(--card-bg);
  }
  .reading {
    translate: -50% calc(-100% - 0.4em);
  }
  .reading.under {
    translate: -50% 0.4em;
  }
  .reading.low {
    color: var(--on-card-soft);
    font-weight: 600;
  }
  .sun {
    position: absolute;
    top: calc(var(--tick) * 1.7);
    bottom: 0;
    border-left: 1px dashed var(--on-card-faint);
  }
  .sun-tag {
    position: absolute;
    top: 0;
    left: clamp(3.4em, var(--x), calc(100% - 3.4em));
    translate: -50% 0;
    font-size: var(--tick);
    color: var(--on-card-soft);
    white-space: nowrap;
    line-height: 1.2;
  }
  .rain,
  .axis {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(var(--n), minmax(0, 1fr));
    font-variant-numeric: tabular-nums;
    position: relative;
  }
  .rain li {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25em;
    color: var(--on-card-soft);
    font-size: var(--tick);
    line-height: 1;
  }
  .rain .bar {
    display: flex;
    align-items: flex-end;
    width: 46%;
    height: min(10cqh, 2.6em);
  }
  .rain .bar span {
    width: 100%;
    background: var(--wet);
    border-radius: 0.2em 0.2em 0.05em 0.05em;
  }
  /* Under 10% still shows — just quieter, so the wet hours stand out. */
  .rain li.quiet {
    color: var(--on-card-faint);
  }
  .rain li.quiet .bar span {
    opacity: 0.5;
  }
  .axis {
    padding-top: 0.35em;
    border-top: 1px solid var(--rule);
  }
  .axis li {
    font-size: var(--tick);
    color: var(--on-card-soft);
    white-space: nowrap;
    /* Labels sit on every third hour; let them spill into the blank
       neighbours rather than truncate. */
    overflow: visible;
    text-align: center;
    line-height: 1.1;
  }
  .note {
    position: relative;
    align-self: flex-end;
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.2em 1.2em;
    font-size: var(--tick);
    color: var(--on-card-soft);
  }

  /* ---- Today vs. normal ---- */
  .context {
    --verdict: min(var(--type-xl), 14cqh, 8.4cqi);
    --rec: min(var(--type-lg), 10cqh, 6cqi);
    --stat: min(var(--type-lg), 9.5cqh, 6.2cqi);
    --track-h: max(4px, min(2.2cqh, 1.4cqi));
  }
  .versus {
    display: flex;
    flex-direction: column;
    gap: 0.3em;
  }
  .verdict {
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-weight: 700;
    letter-spacing: -0.025em;
    font-size: var(--verdict);
    line-height: 1;
    text-wrap: balance;
  }
  .normal {
    font-size: var(--note);
    color: var(--on-card-soft);
  }
  .records {
    display: flex;
    flex-direction: column;
    gap: calc(var(--gap) * 0.5);
  }
  /* Record low on the left, record high on the right; the normal range as a
     soft band and today's forecast as a solid bar across it. */
  .track {
    position: relative;
    height: var(--track-h);
    border-radius: 99px;
    background: var(--rule);
  }
  .track span {
    position: absolute;
    border-radius: 99px;
  }
  .track .band {
    top: -60%;
    bottom: -60%;
    background: color-mix(in srgb, var(--on-card) 30%, transparent);
  }
  .track .today {
    top: 0;
    bottom: 0;
    background: var(--on-card);
    box-shadow: 0 0 0 2px var(--card-bg);
  }
  .ends {
    display: flex;
    justify-content: space-between;
    gap: var(--gap);
  }
  .end {
    display: flex;
    flex-direction: column;
    gap: 0.15em;
  }
  .end.right {
    align-items: flex-end;
    text-align: right;
  }
  .rec {
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-weight: 600;
    font-size: var(--rec);
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .yr {
    font-size: var(--note);
    color: var(--on-card-soft);
    white-space: nowrap;
  }
  .key {
    display: flex;
    align-items: center;
    gap: 0.4em;
    font-size: var(--note);
    color: var(--on-card-faint);
    white-space: nowrap;
  }
  .swatch {
    display: inline-block;
    width: 1.3em;
    height: 0.45em;
    border-radius: 99px;
  }
  .swatch.band {
    background: color-mix(in srgb, var(--on-card) 30%, transparent);
  }
  .swatch.today {
    margin-left: 0.6em;
    background: var(--on-card);
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--gap);
    margin: 0;
    padding-top: var(--gap);
    border-top: 1px solid var(--rule);
  }
  .stats div {
    display: flex;
    flex-direction: column-reverse;
    justify-content: flex-end;
    gap: 0.3em;
    min-width: 0;
  }
  .stats dt {
    font-size: var(--note);
    color: var(--on-card-soft);
  }
  .stats dd {
    margin: 0;
    font-size: var(--stat);
    font-weight: var(--weight-display);
    line-height: 1;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .stats .sub {
    display: block;
    margin-top: 0.25em;
    font-size: var(--note);
    font-weight: var(--weight-body);
    color: var(--on-card-soft);
  }
  .arrow {
    width: 0.7em;
    height: 0.7em;
    margin-right: 0.2em;
    vertical-align: -0.02em;
    fill: currentColor;
  }
  /* No records to show (outside the US): the three readings take the page. */
  .context.bare {
    --stat: min(var(--type-hero), 18cqh, 11cqi);
    justify-content: center;
  }
  .context.bare .stats {
    border-top: 0;
    padding-top: 0;
  }
</style>
