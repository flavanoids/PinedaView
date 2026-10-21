// SPDX-License-Identifier: Apache-2.0
import type { Component } from "svelte";

import Affirmation from "./Affirmation.svelte";
import AirQuality from "./AirQuality.svelte";
import Calendar from "./Calendar.svelte";
import Alerts from "./Alerts.svelte";
import Clock from "./Clock.svelte";
import Commute from "./Commute.svelte";
import Forecast from "./Forecast.svelte";
import Generic from "./Generic.svelte";
import HomeCams from "./HomeCams.svelte";
import IndoorClimate from "./IndoorClimate.svelte";
import Moon from "./Moon.svelte";
import MoonClimate from "./MoonClimate.svelte";
import News from "./News.svelte";
import NowPlaying from "./NowPlaying.svelte";
import OnThisDay from "./OnThisDay.svelte";
import Photo from "./Photo.svelte";
import Phrase from "./Phrase.svelte";
import Radar from "./Radar.svelte";
import Timer from "./Timer.svelte";
import Traffic from "./Traffic.svelte";
import Video from "./Video.svelte";
import Weather from "./Weather.svelte";
import type { CardProps } from "./types";

export const CARDS: Record<string, Component<CardProps>> = {
  clock: Clock,
  weather: Weather,
  forecast: Forecast,
  affirmation: Affirmation,
  phrase: Phrase,
  moon: Moon,
  "moon-climate": MoonClimate,
  "home-cams": HomeCams,
  photo: Photo,
  "air-quality": AirQuality,
  "now-playing": NowPlaying,
  commute: Commute,
  alerts: Alerts,
  radar: Radar,
  timer: Timer,
  "indoor-climate": IndoorClimate,
  "on-this-day": OnThisDay,
  traffic: Traffic,
  video: Video,
  news: News,
  calendar: Calendar,
};

/** A bespoke view if one exists, otherwise the Generic fallback so an unknown
    card still renders. */
export function cardComponent(
  id: string,
): Component<CardProps & { id?: string }> {
  return CARDS[id] ?? Generic;
}
