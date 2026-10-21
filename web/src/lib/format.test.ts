// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import {
  alertSeverityColor,
  delayBand,
  etaFrom,
  formatClock,
  formatDayName,
  formatDuration,
  formatHour,
  formatSpeed,
  formatTemp,
  parseClockTime,
  formatWords,
  mapsUrl,
  QLOCK_ROWS,
  qlockLit,
  uvBand,
  windArrow,
} from "./format";

describe("formatTemp", () => {
  it("converts to Fahrenheit for imperial", () => {
    expect(formatTemp(0, "imperial")).toBe("32°");
    expect(formatTemp(-3.4, "metric")).toBe("−3°");
    expect(formatTemp(-0.4, "metric")).toBe("0°");
    expect(formatTemp(29.4, "imperial")).toBe("85°");
  });
  it("keeps Celsius for metric", () => {
    expect(formatTemp(21.6, "metric")).toBe("22°");
  });
  it("shows a dash for missing data", () => {
    expect(formatTemp(null, "metric")).toBe("—");
    expect(formatTemp(undefined, "imperial")).toBe("—");
  });
});

describe("formatSpeed", () => {
  it("uses mph for imperial and km/h for metric", () => {
    expect(formatSpeed(10, "imperial")).toBe("22 mph");
    expect(formatSpeed(10, "metric")).toBe("36 km/h");
  });
});

describe("formatDuration", () => {
  it("pads seconds under 10", () => {
    expect(formatDuration(65)).toBe("1:05");
  });
  it("handles minutes over 9", () => {
    expect(formatDuration(725)).toBe("12:05");
  });
  it("rounds and floors negative/zero to 0:00", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(-4)).toBe("0:00");
  });
});

describe("formatDayName", () => {
  it("names today and tomorrow", () => {
    expect(formatDayName("2026-08-28", 0)).toBe("Today");
    expect(formatDayName("2026-08-28", 1)).toBe("Tomorrow");
  });
  it("falls back to the raw string on a bad date", () => {
    expect(formatDayName("not-a-date", 3)).toBe("not-a-date");
  });
});

describe("formatHour", () => {
  it("labels 3-hourly slots", () => {
    expect(formatHour(0)).toBe("12am");
    expect(formatHour(6)).toBe("6am");
    expect(formatHour(12)).toBe("Noon");
    expect(formatHour(15)).toBe("3pm");
    expect(formatHour(21)).toBe("9pm");
  });
  it("wraps past midnight", () => {
    expect(formatHour(24)).toBe("12am");
    expect(formatHour(27)).toBe("3am");
  });
});

describe("windArrow", () => {
  it("maps a bearing to a towards-arrow", () => {
    expect(windArrow("S")).toBe("↑");
    expect(windArrow("nw")).toBe("↘");
    expect(windArrow("")).toBe("");
    expect(windArrow("???")).toBe("???");
  });
});

describe("uvBand", () => {
  it("bands the EPA UV index", () => {
    expect(uvBand(1)).toBe("Low");
    expect(uvBand(4)).toBe("Moderate");
    expect(uvBand(6)).toBe("High");
    expect(uvBand(9)).toBe("Very high");
    expect(uvBand(11)).toBe("Extreme");
  });
});

describe("delayBand", () => {
  it("bands a commute delay in minutes", () => {
    expect(delayBand(0)).toBe("clear");
    expect(delayBand(4)).toBe("clear");
    expect(delayBand(5)).toBe("slow");
    expect(delayBand(14)).toBe("slow");
    expect(delayBand(15)).toBe("heavy");
  });
});

describe("alertSeverityColor", () => {
  it("gives Extreme and Severe distinct colours", () => {
    expect(alertSeverityColor("Extreme")).not.toBe(
      alertSeverityColor("Severe"),
    );
  });
  it("falls back to Unknown's colour for an unrecognised severity", () => {
    expect(alertSeverityColor("Nonsense")).toBe(alertSeverityColor("Unknown"));
    expect(alertSeverityColor(undefined)).toBe(alertSeverityColor("Unknown"));
  });
});

describe("mapsUrl", () => {
  it("builds a driving-directions link, encoding the address", () => {
    const url = mapsUrl("123 Main St, Houston, TX");
    expect(url).toContain("https://www.google.com/maps/dir/?");
    expect(url).toContain("destination=123+Main+St%2C+Houston%2C+TX");
    expect(url).toContain("travelmode=driving");
  });
});

describe("etaFrom", () => {
  it("adds the minutes to the given time", () => {
    expect(etaFrom(new Date(2026, 0, 1, 7, 15), 25)).toBe("7:40 AM");
  });
  it("rolls over noon and midnight correctly", () => {
    expect(etaFrom(new Date(2026, 0, 1, 11, 50), 20)).toBe("12:10 PM");
    expect(etaFrom(new Date(2026, 0, 1, 23, 50), 20)).toBe("12:10 AM");
  });
});

describe("formatWords", () => {
  const at = (h: number, m: number): string =>
    formatWords(new Date(2026, 0, 1, h, m));

  it("names the hour on the hour", () => {
    expect(at(9, 0)).toBe("nine o'clock");
    expect(at(9, 2)).toBe("nine o'clock");
  });
  it("uses past for the first half", () => {
    expect(at(9, 5)).toBe("five past nine");
    expect(at(9, 15)).toBe("quarter past nine");
    expect(at(9, 30)).toBe("half past nine");
  });
  it("counts to the coming hour for the second half", () => {
    expect(at(9, 35)).toBe("twenty-five to ten");
    expect(at(9, 45)).toBe("quarter to ten");
  });
  it("rounds to the nearest five minutes", () => {
    expect(at(9, 13)).toBe("quarter past nine");
    expect(at(9, 58)).toBe("ten o'clock");
  });
  it("wraps 12 and midnight", () => {
    expect(at(12, 0)).toBe("twelve o'clock");
    expect(at(11, 45)).toBe("quarter to twelve");
    expect(at(23, 58)).toBe("twelve o'clock");
  });
});

describe("qlockLit", () => {
  const read = (h: number, m: number): string => {
    const { lit } = qlockLit(new Date(2026, 0, 1, h, m));
    return QLOCK_ROWS.map((row, r) =>
      [...row].map((ch, c) => (lit.has(r * 11 + c) ? ch : " ")).join(""),
    )
      .join(" ")
      .split(/\s+/)
      .filter(Boolean)
      .join(" ");
  };

  it("spells the hour on the hour", () => {
    expect(read(9, 0)).toBe("IT IS AM NINE OCLOCK");
  });
  it("floors to five minutes and counts the rest in dots", () => {
    expect(read(21, 17)).toBe("IT IS PM QUARTER PAST NINE");
    expect(qlockLit(new Date(2026, 0, 1, 21, 17)).dots).toBe(2);
  });
  it("counts to the coming hour from :35", () => {
    expect(read(9, 35)).toBe("IT IS AM TWENTYFIVE TO TEN");
    expect(read(23, 55)).toBe("IT IS PM FIVE TO TWELVE");
  });
});

describe("parseClockTime", () => {
  it("parses provider sunrise/sunset strings to minutes after midnight", () => {
    expect(parseClockTime("7:13 AM")).toBe(433);
    expect(parseClockTime("12:00 PM")).toBe(720);
    expect(parseClockTime("12:05 AM")).toBe(5);
    expect(parseClockTime("6:45 pm")).toBe(18 * 60 + 45);
  });
  it("returns null for missing or malformed input", () => {
    expect(parseClockTime(undefined)).toBeNull();
    expect(parseClockTime(null)).toBeNull();
    expect(parseClockTime("soon")).toBeNull();
  });
});

describe("formatClock", () => {
  it("formats 12h time and am/pm", () => {
    const res = formatClock(new Date(2026, 9, 17, 14, 30, 15), false, "off");
    expect(res.time).toBe("2:30");
    expect(res.hh).toBe("2");
    expect(res.mm).toBe("30");
    expect(res.ampm).toBe("PM");
    expect(res.date).toBe("");
  });

  it("formats 24h time", () => {
    const res = formatClock(new Date(2026, 9, 17, 9, 5, 0), true, "off");
    expect(res.time).toBe("09:05");
    expect(res.hh).toBe("09");
    expect(res.mm).toBe("05");
    expect(res.ampm).toBe("");
  });

  it("returns cached reference for same minute and options", () => {
    const d1 = new Date(2026, 9, 17, 10, 45, 1);
    const d2 = new Date(2026, 9, 17, 10, 45, 30);
    const r1 = formatClock(d1, false, "short");
    const r2 = formatClock(d2, false, "short");
    expect(r1).toBe(r2);
  });
});
