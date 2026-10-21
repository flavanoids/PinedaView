<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import {
    dayLabel,
    position,
    segments,
    toSpans,
    trackWindow,
    untilLabel,
    upcoming,
    weekDays,
    type CalendarData,
    type Segment,
    type Span,
  } from "../lib/calendar";
  import { formatClock, formatHour, timeOfDay } from "../lib/format";
  import { clock } from "../lib/time.svelte";
  import type { CardProps } from "./types";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();

  const data = $derived(pick<CalendarData>(view, "calendar"));
  const mode = $derived(data?.view ?? "week");
  const spans = $derived(toSpans(data?.events ?? []));
  // Minute resolution: the 1 s clock tick would otherwise re-lay out the
  // tracks every second for a marker that moves a pixel an hour.
  const minute = $derived(Math.floor(clock.now.getTime() / 60_000));
  const now = $derived(new Date(minute * 60_000));

  // ---- Next 12 hours / Today ----
  const listMode = $derived(mode === "week" ? null : mode);
  const win = $derived(listMode && trackWindow(listMode, now, spans));
  const segs = $derived(win ? segments(spans, win.from, win.to) : []);
  const list = $derived(listMode ? upcoming(spans, listMode, now) : null);
  const lead = $derived(list?.timed[0]);
  const rest = $derived(list?.timed.slice(1, data?.maxEvents ?? 6) ?? []);
  const ticks = $derived.by(() => {
    if (!win) return [];
    const out: { at: number; label: string }[] = [];
    const t = new Date(win.from);
    t.setHours(Math.ceil(t.getHours() / 3) * 3, 0, 0, 0);
    for (; t < win.to; t.setHours(t.getHours() + 3)) {
      out.push({
        at: position(t, win.from, win.to),
        label: formatHour(t.getHours()),
      });
    }
    return out;
  });

  // ---- Next 7 days ----
  const days = $derived(mode === "week" ? weekDays(spans, now) : []);
  const todayTrack = $derived.by(() => {
    const today = days[0]?.date;
    if (!today) return null;
    const from = new Date(today);
    from.setHours(6);
    const to = new Date(today);
    to.setDate(to.getDate() + 1);
    return { from, to };
  });

  /** "3:00 – 3:30 PM", the meridiem said once when both ends share it. */
  function range(s: Span): string {
    const a = formatClock(s.start);
    const b = formatClock(s.end);
    if (s.end.getTime() === s.start.getTime()) return timeOfDay(s.start);
    if (a.ampm === b.ampm) return `${a.time} – ${b.time} ${b.ampm}`.trim();
    return `${timeOfDay(s.start)} – ${timeOfDay(s.end)}`;
  }

  /** What a week row says about its first event: its time, or "All day",
      or "Until 10 AM" for something carried over from the night before. */
  function when(s: Span, day: Date): string {
    if (s.event.allDay) return "All day";
    if (s.start < day) return `Until ${timeOfDay(s.end)}`;
    return timeOfDay(s.start);
  }

  /** In today's row, only what's still ahead is worth naming. */
  function ahead(dayIndex: number, list: Span[]): Span[] {
    return dayIndex === 0
      ? list.filter((s) => s.event.allDay || s.end > now)
      : list;
  }

  const emptyText = $derived(
    mode === "next12h"
      ? "Nothing in the next 12 hours."
      : mode === "today"
        ? "Nothing else today."
        : "",
  );
</script>

{#snippet track(segs: Segment[], from: Date, to: Date, live: boolean)}
  {@const at = live ? position(now, from, to) : -1}
  <span class="track" aria-hidden="true">
    {#each segs as seg (seg.id)}
      <span
        class="seg"
        class:past={seg.to <= at}
        style:left="{seg.from * 100}%"
        style:width="{(seg.to - seg.from) * 100}%"
        style:--c={seg.color ?? undefined}
      ></span>
    {/each}
    {#if at > 0 && at < 1}
      <span class="now" style:left="{at * 100}%"></span>
    {/if}
  </span>
{/snippet}

<Card accent="calendar" {stale} {hero} fill>
  <div class="cal">
    {#if !data}
      <p class="empty">
        Connect a calendar in Settings › Connect to see it here.
      </p>
    {:else if listMode && win}
      <div class="ruler">
        {@render track(segs, win.from, win.to, true)}
        <span class="ticks" aria-hidden="true">
          {#each ticks as tick (tick.label)}
            <span style:left="{tick.at * 100}%">{tick.label}</span>
          {/each}
        </span>
      </div>

      {#if lead}
        {@const until = untilLabel(lead.start, lead.end, now)}
        <div class="lead">
          <p class="lead-title">{lead.event.title}</p>
          <p class="lead-when">
            <span class="dot" style:--c={lead.event.color ?? undefined}></span>
            {#if until}<span class="until"
                >{until === "now" ? "Now" : until}</span
              >{/if}
            <span
              >{until === "now"
                ? `until ${timeOfDay(lead.end)}`
                : range(lead)}</span
            >
          </p>
        </div>
      {/if}

      {#if list && (list.allDay.length || rest.length)}
        <ul class="rest">
          {#each list.allDay as s (s.event.id)}
            <li>
              <span class="time">All day</span>
              <span class="dot" style:--c={s.event.color ?? undefined}></span>
              <span class="title">{s.event.title}</span>
            </li>
          {/each}
          {#each rest as s (`${s.event.id}@${s.start.getTime()}`)}
            <li>
              <span class="time">{timeOfDay(s.start)}</span>
              <span class="dot" style:--c={s.event.color ?? undefined}></span>
              <span class="title">{s.event.title}</span>
            </li>
          {/each}
        </ul>
      {/if}

      {#if !lead && !list?.allDay.length}
        <p class="empty">{emptyText}</p>
      {/if}
    {:else}
      <ol class="week">
        {#each days as day, i (day.date.getTime())}
          {@const shown = ahead(i, day.spans)}
          {@const first = shown[0]}
          {@const allDay = day.spans.filter((s) => s.event.allDay)}
          <li class:today={i === 0} class:clear={!day.spans.length}>
            <span class="date">
              <span class="wd">{dayLabel(day.date, now)}</span>
              <span class="num">{day.date.getDate()}</span>
            </span>
            <span class="lane">
              {#each allDay as s (s.event.id)}
                <span class="allday" style:--c={s.event.color ?? undefined}
                ></span>
              {/each}
              {#if i === 0 && todayTrack}
                {@render track(
                  day.segments,
                  todayTrack.from,
                  todayTrack.to,
                  true,
                )}
              {:else}
                {@render track(day.segments, day.date, day.date, false)}
              {/if}
            </span>
            <span class="first">
              {#if first}
                <span class="title">{first.event.title}</span>
                <span class="when">{when(first, day.date)}</span>
                {#if shown.length > 1}<span class="more"
                    >+{shown.length - 1}</span
                  >{/if}
              {/if}
            </span>
          </li>
        {/each}
      </ol>
    {/if}
  </div>
</Card>

<style>
  .cal {
    /* A calendar's colour is the owner's pick and can match the theme's card
       (Apple's default red on a pink card), so every mark gets a hairline
       of the card's text colour to stand on. */
    --ring: 0 0 0 0.1em color-mix(in srgb, var(--on-card) 45%, transparent);
    --lane: color-mix(in srgb, var(--on-card) 11%, transparent);
    --track-h: 0.6em;

    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    container-type: size;
    /* A size container has no content height on a phone; give it a floor. */
    min-height: 56cqi;
    font-size: var(--type-sm);
  }

  /* ---- The track: busy time is ink, free time is empty lane ---- */
  .track {
    position: relative;
    display: block;
    height: var(--track-h);
    border-radius: var(--radius-pill);
    background: var(--lane);
  }
  .seg {
    position: absolute;
    top: 0;
    bottom: 0;
    border-radius: var(--radius-pill);
    background: var(--c, var(--accent));
    box-shadow: var(--ring);
  }
  .seg.past {
    opacity: 0.35;
  }
  .now {
    position: absolute;
    top: -0.3em;
    bottom: -0.3em;
    width: 2px;
    margin-left: -1px;
    border-radius: 1px;
    background: var(--on-card);
  }

  /* ---- Next 12 hours / Today ---- */
  .ruler {
    --track-h: 0.85em;
    padding-top: 0.3em;
  }
  .ticks {
    position: relative;
    display: block;
    height: 1.4em;
    margin-top: 0.45em;
    font-size: var(--type-caption);
    color: var(--on-card-faint);
    font-variant-numeric: tabular-nums;
  }
  .ticks span {
    position: absolute;
    transform: translateX(-50%);
    white-space: nowrap;
  }
  .ticks span:first-child {
    transform: none;
  }

  .lead {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 0;
  }
  .lead-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--type-lg);
    font-weight: var(--weight-display);
    line-height: 1.05;
    letter-spacing: -0.015em;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .lead-when {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.5em;
    color: var(--on-card-soft);
    font-size: var(--type-md);
    font-variant-numeric: tabular-nums;
  }
  .until {
    color: var(--on-card);
    font-weight: var(--weight-label);
  }
  :global(.card.hero) .lead-title {
    font-size: clamp(var(--type-xl), 6cqi, var(--type-hero));
    line-height: 1.1;
  }
  :global(.card.hero) .lead-when {
    font-size: var(--type-lg);
  }
  :global(.card.hero) .rest {
    font-size: var(--type-md);
    gap: var(--space-3);
  }
  :global(.card.hero) .week {
    gap: var(--space-3);
  }
  :global(.card.hero) .week li {
    font-size: var(--type-md);
  }

  .dot {
    flex: none;
    width: 0.6em;
    height: 0.6em;
    border-radius: 50%;
    background: var(--c, var(--accent));
    box-shadow: var(--ring);
  }

  .rest {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-height: 0;
    overflow: hidden;
  }
  .rest li {
    display: grid;
    grid-template-columns: 4.6em auto minmax(0, 1fr);
    align-items: center;
    gap: 0.6em;
  }
  .time {
    color: var(--on-card-soft);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ---- Next 7 days ---- */
  /* One grid for all seven days (rows are display: contents), so the
     date column is as wide as "Tomorrow" needs and every track lines up. */
  .week {
    flex: 1;
    min-height: 0;
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr) minmax(0, 1.15fr);
    align-content: space-between;
    align-items: center;
    column-gap: 0.8em;
    row-gap: var(--space-1);
  }
  .week li {
    display: contents;
  }
  .date {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.45em;
    color: var(--on-card-soft);
  }
  .wd {
    font-size: var(--type-caption);
  }
  /* Fraunces, same as the clock: the date numbers read as part of the
     clock's family, not as UI text. */
  .num {
    font-family: var(--font-clock);
    font-optical-sizing: auto;
    font-weight: 600;
    font-size: 1.35em;
    line-height: 1;
    font-variant-numeric: lining-nums tabular-nums;
  }
  .today .date,
  .today .num {
    color: var(--on-card);
  }
  .today .num {
    font-weight: 800;
  }
  .lane {
    display: flex;
    flex-direction: column;
    gap: 0.2em;
  }
  /* An all-day event is a hairline over the whole day, not a block on it —
     a birthday doesn't make the day busy. */
  .allday {
    display: block;
    height: 0.18em;
    border-radius: var(--radius-pill);
    background: var(--c, var(--accent));
  }
  .first {
    display: flex;
    align-items: baseline;
    gap: 0.45em;
    min-width: 0;
  }
  .first .title {
    flex: 0 1 auto;
  }
  .when,
  .more {
    flex: none;
    color: var(--on-card-faint);
    font-size: var(--type-caption);
    font-variant-numeric: tabular-nums;
  }
  .clear .date {
    color: var(--on-card-faint);
  }

  .empty {
    margin: auto 0;
    color: var(--on-card-faint);
  }

  /* Narrow tile: the tracks carry the week on their own. */
  @container (max-width: 22rem) {
    .week {
      grid-template-columns: max-content minmax(0, 1fr);
    }
    .first {
      display: none;
    }
  }
  /* The big space: let the next thing be read from across the room. */
  @container (min-height: 30rem) and (min-width: 34rem) {
    .lead-title {
      font-size: var(--type-xl);
    }
    .ruler {
      --track-h: 1.1em;
    }
  }
  /* Short tile: today and tomorrow, and no list under the lead event. */
  @container (max-height: 13rem) {
    .week li:nth-child(n + 3) {
      display: none;
    }
    .rest,
    .ticks {
      display: none;
    }
  }
</style>
