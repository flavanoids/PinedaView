// SPDX-License-Identifier: Apache-2.0
import type { ViewModel } from "@pinedaview/protocol";

/** A card's data is old: `false`, or when it was last fresh (ISO 8601) —
    `true` when that isn't known. */
export type Stale = boolean | string;

export interface CardProps {
  view: ViewModel;
  stale: Stale;
  hero: boolean;
}

// Loose shapes for the store payloads the cards read out of `view.data`.
export interface WeatherHour {
  hour: number;
  tempC?: number | null;
  feelsLikeC?: number | null;
  desc?: string;
  code?: string;
  precip?: number;
  uvIndex?: number;
  isDay?: boolean;
}
export interface WeatherDay {
  index: number;
  date: string;
  highC?: number | null;
  lowC?: number | null;
  code?: string;
  desc?: string;
  precip?: number;
  sunrise?: string;
  sunset?: string;
}
export interface WeatherData {
  current?: {
    tempC?: number | null;
    feelsLikeC?: number | null;
    desc?: string;
    code?: string;
    humidity?: number;
    windMs?: number | null;
    windDir?: string;
    /** Degrees the wind blows *from*, 0 = north. */
    windDeg?: number | null;
    uvIndex?: number | null;
    isDay?: boolean;
  };
  /** The next 24 hours, one slot per hour, starting with the current one. */
  hourly?: WeatherHour[];
  forecast?: WeatherDay[];
  /** Today's normals and records (US only, via NOAA ACIS); null elsewhere. */
  climate?: WeatherClimate | null;
  place?: string;
}
export interface WeatherClimate {
  normalHighC?: number | null;
  normalLowC?: number | null;
  recordHighC?: number | null;
  recordHighYear?: number | null;
  recordLowC?: number | null;
  recordLowYear?: number | null;
  /** First year of the station's record. */
  since?: number | null;
  station?: string | null;
}

export interface MoonData {
  name?: string;
  phase?: number;
  illumination?: number;
}

export interface IndoorClimateData {
  /** Latest indoor temperature, already unit-normalized server-side. */
  tempC?: number | null;
  humidity?: number | null;
  setpointC?: number | null;
  outdoorC?: number | null;
  /** Compressor runtime over the last 30 min, percent. */
  runtimePct?: number | null;
  /** When the AC engine last sampled, `YYYY-MM-DDTHH:MM`. */
  sampledAt?: string;
}

export interface DailyContentData {
  affirmation?: { text?: string; author?: string; year?: number | null };
  /** The day's rotating set of quotes; the card cross-fades through them.
      Falls back to `[affirmation]` for older servers. */
  affirmations?: { text?: string; author?: string; year?: number | null }[];
  word?: {
    english?: string;
    /** Word-for-word gloss, for idioms that don't translate straight. */
    literal?: string | null;
    /** One line on how/when the phrase is used. */
    note?: string | null;
    languages?: {
      lang: string;
      code?: string;
      dir?: string;
      text: string;
      pron: string;
    }[];
  };
}

export interface NewsStory {
  /** A hash of the article URL — stable while the story is in rotation. */
  id: string;
  title: string;
  /** The article at the outlet, tracking tags removed — the QR opens it. */
  url: string;
  outlet: string;
  /** Which of the household's beats it was picked for: US, World, … */
  beat: string;
  /** When the outlet published it (ISO 8601). */
  published: string;
  /** The story's own picture, blurred on the server; null when it has none. */
  image: string | null;
  /** That picture's average colour (#rrggbb), for the card's scrim. */
  tint: string | null;
}

export interface NewsData {
  stories?: NewsStory[];
}

export interface TrafficCam {
  id: string;
  label: string;
  /** `/api/cams/407.jpg?v=<capture>` — a new capture is a new URL. */
  src: string;
  /** A short flipbook's frames (empty for a plain still). */
  frames: string[];
  frameMs: number;
  capturedAt: string;
  /** Missed a refresh — the caption's time turns amber. */
  stale: boolean;
}

export interface TrafficSegment {
  /** SVG polyline points in the mosaic's 0–100 space, already nudged to the
      right of travel so the two directions sit side by side. */
  d: string;
  /** fast ≥50 mph, ok 40s, slow 30s, crawl under 30, none = no reading. */
  level: "fast" | "ok" | "slow" | "crawl" | "none";
}

export interface TrafficIncident {
  x: number;
  y: number;
  crash: boolean;
  kind?: "crash" | "closure" | "flood" | "stall";
  desc?: string;
  location?: string;
}

export interface TrafficCamMarker {
  id: string;
  label: string;
  x: number;
  y: number;
}

export interface TrafficAlert {
  type: "slow" | "crash" | "closure" | "flood" | "stall" | "ok";
  text: string;
}

export interface TrafficMap {
  /** Mosaic width in tiles (and height), as on the radar card. */
  cols: number;
  zoom?: number;
  /** Shift, as a percent of the mosaic, that centres home. */
  focus: { dx: number; dy: number };
  basemap: string[];
  roads: string[];
  segments: TrafficSegment[];
  /** Active (not cleared) crashes and stalls, in mosaic percent. */
  incidents: TrafficIncident[];
  cameras?: TrafficCamMarker[];
  /** The slowest stretch near home, when anything's under 50 mph. */
  slowest: { label: string; mph: number; delay?: number } | null;
  alerts?: TrafficAlert[];
  updatedAt: string | null;
  stale: boolean;
}

export interface TrafficData {
  /** Inside a commute window; outside, the card is just the quote. */
  active?: boolean;
  cams?: TrafficCam[];
  /** TranStar freeway speeds around home — the loop's first slide. */
  map?: TrafficMap | null;
}

export interface HomeCam {
  /** The camera's name in [cameras.streams]: "front_door", "garage". */
  id: string;
  label: string;
  /** `/api/home-cams/garage.jpg?v=<taken>` — a new photo is a new URL. */
  src: string;
  capturedAt: string;
  /** Missed a few refreshes (or it's night) — the time turns amber. */
  stale: boolean;
  /** Percent; null when Home Assistant doesn't say. */
  battery: number | null;
  /** Below Antigua's warning level: the photo says to charge it. */
  lowBattery: boolean;
  /** In [cameras] always_battery: its level shows on its own photo. */
  alwaysBattery?: boolean;
}

export interface HomeCamsData {
  cams?: HomeCam[];
}

export interface CommuteData {
  routes?: {
    label: string;
    address: string;
    minutes: number;
    delayMinutes: number;
    status: string;
  }[];
  duringRush?: boolean;
}

export interface AlertsData {
  count?: number;
  top?: { severity: string; event: string; headline: string } | null;
}

export interface RadarFrame {
  time: string | null;
  /** `cols`² tile URLs, row-major, forming one square mosaic. */
  tiles: string[];
}

export interface RadarStorm {
  x: number;
  y: number;
  x2: number;
  y2: number;
  mph: number;
  hail: boolean;
  rotation: boolean;
}

export interface RadarData {
  /** Mosaic width in tiles (and height — it's square). */
  cols?: number;
  /** Shift, as a percent of the mosaic, that centres the location. */
  focus?: { dx: number; dy: number };
  /** `cols`² dark basemap tile URLs, row-major — the layer under the radar. */
  basemap?: string[];
  /** Same grid: Esri's transparent roads overlay, between basemap and radar. */
  roads?: string[];
  /** Newest frame only — the card is a still image. */
  frames?: RadarFrame[];
  /** Nearby NEXRAD storm cells (US only) as tracks in mosaic percent: now at
      (x, y), in 30 minutes at (x2, y2). */
  storms?: RadarStorm[];
  /** ISO 8601 time of the newest radar frame, for the on-map timestamp. */
  generated_at?: string;
}

export interface TimerEntry {
  id: string;
  label: string;
  fires_at: string;
  source?: string | null;
  /** An alarm shows when it goes off ("7:00 AM"), not a countdown. */
  kind?: "timer" | "alarm" | "reminder";
  /** What the user called it; none, and the clock's list leaves it blank. */
  name?: string | null;
}

export function pick<T>(view: ViewModel, key: string): T | undefined {
  return (view.data as Record<string, unknown>)[key] as T | undefined;
}

/** Which store backs each card — mirrors the server's map for stale flags. */
export const CARD_STORE: Record<string, string> = {
  weather: "weather",
  forecast: "weather",
  affirmation: "dailyContent",
  phrase: "dailyContent",
  moon: "moon",
  "moon-climate": "moon",
  "air-quality": "airQuality",
  commute: "commute",
  alerts: "alerts",
  radar: "radar",
  "indoor-climate": "indoorClimate",
  "on-this-day": "onThisDay",
  traffic: "traffic",
  news: "news",
  calendar: "calendar",
};

export function isCardStale(view: ViewModel, cardId: string): boolean {
  const fromList = view.cards.find((card) => card.id === cardId)?.stale;
  if (fromList !== undefined) return fromList;
  const store = CARD_STORE[cardId];
  return store ? view.stale_stores.includes(store) : false;
}

/** As `isCardStale`, with when the card's data was last fresh if known. */
export function cardStale(view: ViewModel, cardId: string): Stale {
  if (!isCardStale(view, cardId)) return false;
  const store = CARD_STORE[cardId];
  return (store && view.stale_since?.[store]) || true;
}
