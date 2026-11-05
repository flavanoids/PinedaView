// SPDX-License-Identifier: Apache-2.0
import { prefs } from "./prefs.svelte";

export type Units = "imperial" | "metric";

export function formatTemp(
  celsius: number | null | undefined,
  units: Units,
): string {
  if (celsius == null) return "—";
  const value = Math.round(
    units === "metric" ? celsius : (celsius * 9) / 5 + 32,
  );
  // A true minus sign: a hyphen sits too low and too short beside numerals.
  return value < 0 ? `−${-value}°` : `${value}°`;
}

export function formatSpeed(
  metresPerSecond: number | null | undefined,
  units: Units,
): string {
  if (metresPerSecond == null) return "—";
  return units === "metric"
    ? `${Math.round(metresPerSecond * 3.6)} km/h`
    : `${Math.round(metresPerSecond * 2.23694)} mph`;
}

/** "7:13 AM" → minutes after midnight, or null when missing/malformed — the
    inverse of the clock faces' "h:mm" labels, for sunrise/sunset times the
    weather provider sends as preformatted strings. */
export function parseClockTime(time: string | undefined | null): number | null {
  const m = time?.match(/^(\d{1,2}):(\d{2})\s*([AP]M)$/i);
  if (!m) return null;
  const h = (Number(m[1]) % 12) + (m[3]?.toUpperCase() === "PM" ? 12 : 0);
  return h * 60 + Number(m[2]);
}

const UV_BANDS: [number, string][] = [
  [2, "Low"],
  [5, "Moderate"],
  [7, "High"],
  [10, "Very high"],
  [Infinity, "Extreme"],
];

/** EPA/WHO UV index band name for a given index value. */
export function uvBand(uvIndex: number): string {
  return UV_BANDS.find(([max]) => uvIndex <= max)?.[1] ?? "";
}

/** Commute delay severity band, for the delay badge's colour. */
export function delayBand(delayMinutes: number): "clear" | "slow" | "heavy" {
  if (delayMinutes >= 15) return "heavy";
  if (delayMinutes >= 5) return "slow";
  return "clear";
}

// Fixed, not themed — these encode NWS severity meaning and would lose it if
// swapped by a card-color theme (same reasoning as WeatherGlyph's colours).
const UNKNOWN_SEVERITY_COLOR = "var(--on-card-faint)";
const SEVERITY_COLOR: Record<string, string> = {
  Extreme: "#d1373e",
  Severe: "#e2703a",
  Moderate: "#d8a72b",
  Minor: "#8a8f5c",
  Unknown: UNKNOWN_SEVERITY_COLOR,
};

export function alertSeverityColor(severity: string | undefined): string {
  if (severity === undefined) return UNKNOWN_SEVERITY_COLOR;
  return SEVERITY_COLOR[severity] ?? UNKNOWN_SEVERITY_COLOR;
}

export function formatDayName(iso: string, index: number): string {
  if (index === 0) return "Today";
  if (index === 1) return "Tomorrow";
  const date = new Date(`${iso}T12:00:00`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, { weekday: "short" });
}

const WIND_ARROWS: Record<string, string> = {
  N: "↓",
  NNE: "↓",
  NE: "↙",
  ENE: "↙",
  E: "←",
  ESE: "←",
  SE: "↖",
  SSE: "↖",
  S: "↑",
  SSW: "↑",
  SW: "↗",
  WSW: "↗",
  W: "→",
  WNW: "→",
  NW: "↘",
  NNW: "↘",
};

/** A 16-point compass bearing as the arrow the wind is blowing *towards* — a
    compact stand-in for the letters on a tight metric. Falls back to the
    bearing text for anything unrecognised. */
export function windArrow(dir: string | undefined): string {
  if (!dir) return "";
  return WIND_ARROWS[dir.toUpperCase()] ?? dir;
}

/** A 24h slot number (0, 3, 6 … 21) as a short wall-clock label: "12am",
    "6am", "Noon", "3pm". */
export function formatHour(hour: number): string {
  const h = ((hour % 24) + 24) % 24;
  if (h === 0) return "12am";
  if (h === 12) return "Noon";
  return h < 12 ? `${h}am` : `${h - 12}pm`;
}

/** A Google Maps turn-by-turn link for a commute stop's address. */
export function mapsUrl(address: string): string {
  const params = new URLSearchParams({
    api: "1",
    destination: address,
    travelmode: "driving",
  });
  return `https://www.google.com/maps/dir/?${params}`;
}

/** "7:42 AM", or "07:42" on a 24-hour household — a time of day in a line
    of text. */
export function timeOfDay(date: Date): string {
  const { time, ampm } = formatClock(date);
  return ampm ? `${time} ${ampm}` : time;
}

/** "7:42 AM" — clock time `minutes` from now, for a commute card's ETA. */
export function etaFrom(now: Date, minutes: number): string {
  return timeOfDay(new Date(now.getTime() + minutes * 60_000));
}

/** "7:00 AM" — when an alarm goes off, for where a timer shows its countdown. */
export function alarmTime(firesAtIso: string): string {
  return timeOfDay(new Date(firesAtIso));
}

/** "4:05" or "1:02:05" — a running timer's time left, from whole seconds. */
export function formatCountdown(total: number): string {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** "3:07" — seconds as m:ss, for a Now-playing elapsed/duration readout. */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(s / 60);
  const seconds = s % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

const HOUR_WORDS = [
  "twelve",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
];

const PAST_WORDS: Record<number, string> = {
  0: "",
  5: "five past",
  10: "ten past",
  15: "quarter past",
  20: "twenty past",
  25: "twenty-five past",
  30: "half past",
  35: "twenty-five to",
  40: "twenty to",
  45: "quarter to",
  50: "ten to",
  55: "five to",
};

/**
 * The time spelled out, rounded to the nearest five minutes: "half past nine",
 * "quarter to ten", "nine o'clock". Lowercase — the clock card sets the tone
 * with type, not capitals.
 */
export function formatWords(now: Date): string {
  const rounded = Math.round(now.getMinutes() / 5) * 5;
  const carry = rounded === 60;
  const slot = carry ? 0 : rounded;
  // "to" phrases (35–55) and the top of the next hour name the coming hour.
  const hour12 = (now.getHours() + (slot >= 35 || carry ? 1 : 0)) % 12;
  const hourWord = HOUR_WORDS[hour12];
  return slot === 0 ? `${hourWord} o'clock` : `${PAST_WORDS[slot]} ${hourWord}`;
}

/** The QLOCKTWO letter board: ten rows of eleven, the time hidden in it. */
export const QLOCK_ROWS = [
  "ITLISASAMPM",
  "ACQUARTERDC",
  "TWENTYFIVEX",
  "HALFSTENFTO",
  "PASTERUNINE",
  "ONESIXTHREE",
  "FOURFIVETWO",
  "EIGHTELEVEN",
  "SEVENTWELVE",
  "TENSEOCLOCK",
] as const;

// [row, column, length] of each word the board can light.
const QLOCK_WORDS = {
  it: [0, 0, 2],
  is: [0, 3, 2],
  am: [0, 7, 2],
  pm: [0, 9, 2],
  quarter: [1, 2, 7],
  twenty: [2, 0, 6],
  fiveMin: [2, 6, 4],
  half: [3, 0, 4],
  tenMin: [3, 5, 3],
  to: [3, 9, 2],
  past: [4, 0, 4],
  nine: [4, 7, 4],
  one: [5, 0, 3],
  six: [5, 3, 3],
  three: [5, 6, 5],
  four: [6, 0, 4],
  five: [6, 4, 4],
  two: [6, 8, 3],
  eight: [7, 0, 5],
  eleven: [7, 5, 6],
  seven: [8, 0, 5],
  twelve: [8, 5, 6],
  ten: [9, 0, 3],
  oclock: [9, 5, 6],
} as const satisfies Record<string, readonly [number, number, number]>;

type QlockWord = keyof typeof QLOCK_WORDS;

const QLOCK_HOURS: QlockWord[] = [
  "twelve",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
];

const QLOCK_MINUTES: Record<number, QlockWord[]> = {
  0: ["oclock"],
  5: ["fiveMin", "past"],
  10: ["tenMin", "past"],
  15: ["quarter", "past"],
  20: ["twenty", "past"],
  25: ["twenty", "fiveMin", "past"],
  30: ["half", "past"],
  35: ["twenty", "fiveMin", "to"],
  40: ["twenty", "to"],
  45: ["quarter", "to"],
  50: ["tenMin", "to"],
  55: ["fiveMin", "to"],
};

/**
 * Which letters of QLOCK_ROWS are lit, as `row * 11 + col` indices, plus the
 * corner dots — one per minute past the last five, the way a QLOCKTWO does it
 * (floored, not rounded like formatWords: the dots carry the remainder).
 */
export function qlockLit(now: Date): { lit: Set<number>; dots: number } {
  const minutes = now.getMinutes();
  const slot = minutes - (minutes % 5);
  const hour12 = (now.getHours() + (slot >= 35 ? 1 : 0)) % 12;
  const words: QlockWord[] = [
    "it",
    "is",
    ...QLOCK_MINUTES[slot]!,
    QLOCK_HOURS[hour12]!,
    now.getHours() < 12 ? "am" : "pm",
  ];
  const lit = new Set<number>();
  for (const w of words) {
    const [row, col, len] = QLOCK_WORDS[w];
    for (let i = 0; i < len; i++) lit.add(row * 11 + col + i);
  }
  return { lit, dots: minutes % 5 };
}

const DATE_STYLES = {
  long: { weekday: "long", month: "long", day: "numeric" },
  short: { weekday: "short", month: "short", day: "numeric" },
} as const satisfies Record<string, Intl.DateTimeFormatOptions>;

export interface FormattedClock {
  time: string;
  /** Hour and minute split out so the clock card can animate the colon. */
  hh: string;
  mm: string;
  ampm: string;
  date: string;
}

let lastFormattedClock: {
  key: string;
  result: FormattedClock;
} | null = null;

/** The clock's parts, in the household's time format and date style
    (Settings → Time & weather). `ampm` is "" in 24-hour time and `date` is ""
    when the date is turned off. */
export function formatClock(
  now: Date,
  hour24 = prefs.time_format === "24h",
  dateStyle = prefs.date_style,
): FormattedClock {
  const y = now.getFullYear();
  const m = now.getMonth();
  const d = now.getDate();
  const h = now.getHours();
  const min = now.getMinutes();
  const key = `${y}-${m}-${d}-${h}-${min}-${hour24 ? 1 : 0}-${dateStyle}`;

  if (lastFormattedClock && lastFormattedClock.key === key) {
    return lastFormattedClock.result;
  }

  const hh = hour24 ? String(h).padStart(2, "0") : String(h % 12 || 12);
  const minutes = String(min).padStart(2, "0");
  const result: FormattedClock = {
    time: `${hh}:${minutes}`,
    hh,
    mm: minutes,
    ampm: hour24 ? "" : h < 12 ? "AM" : "PM",
    date:
      dateStyle === "off"
        ? ""
        : now.toLocaleDateString(undefined, DATE_STYLES[dateStyle]),
  };

  lastFormattedClock = { key, result };
  return result;
}
