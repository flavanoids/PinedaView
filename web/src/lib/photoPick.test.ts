// SPDX-License-Identifier: Apache-2.0
import type { Photo } from "@pinedaview/protocol";
import { describe, expect, it } from "vitest";

import { photoLook, pickNext, recentLimit, timeFit } from "./photoPick";

const RISE = 7 * 60 + 30;
const SET = 18 * 60 + 45;

function photo(name: string, extra: Partial<Photo> = {}): Photo {
  return {
    name,
    uploaded_at: 0,
    rotation: 0,
    original_filename: name,
    sort: 0,
    taken_at: null,
    pending: false,
    has_subject: false,
    colours: [],
    tint: null,
    motion: false,
    ...extra,
  } as Photo;
}

const BRIGHT = photo("bright", { colours: ["#f0f4ff", "#e8eef8"] });
const DARK = photo("dark", { colours: ["#101418", "#20160e"] });
const WARM = photo("warm", { colours: ["#f08030", "#c05010"] });
const at = (h: number, m = 0) => new Date(2026, 9, 17, h, m);
/** Draw k of n, evenly over 0–1: the weights' shares, exactly. */
const sweep = (k: number, n: number) => () => (k + 0.5) / n;

describe("photoLook", () => {
  it("reads luma and warmth from the swatches", () => {
    expect(photoLook(BRIGHT.colours).luma).toBeGreaterThan(0.9);
    expect(photoLook(DARK.colours).luma).toBeLessThan(0.1);
    expect(photoLook(WARM.colours).warmth).toBeGreaterThan(0.7);
  });
  it("is middling with no colours", () => {
    expect(photoLook([])).toEqual({ luma: 0.5, warmth: 0.5 });
  });
});

describe("timeFit", () => {
  it("favours bright photos at midday", () => {
    expect(timeFit(BRIGHT, 13 * 60, RISE, SET)).toBeGreaterThan(
      timeFit(DARK, 13 * 60, RISE, SET),
    );
  });
  it("favours dark photos late at night", () => {
    expect(timeFit(DARK, 22 * 60, RISE, SET)).toBeGreaterThan(
      timeFit(BRIGHT, 22 * 60, RISE, SET),
    );
  });
  it("favours warm photos round sunset", () => {
    expect(timeFit(WARM, SET + 20, RISE, SET)).toBeGreaterThan(
      timeFit(BRIGHT, SET + 20, RISE, SET),
    );
  });
  it("likes a photo taken near this time of day", () => {
    const evening = photo("e", {
      colours: BRIGHT.colours,
      taken_at: at(21, 30).getTime() / 1000,
    });
    expect(timeFit(evening, 21 * 60, RISE, SET)).toBeGreaterThan(0.8);
  });
});

describe("pickNext", () => {
  const lib = Array.from({ length: 8 }, (_, i) => photo(`p${i}`));

  it("never picks the current photo", () => {
    for (let k = 0; k < 20; k++)
      expect(pickNext(lib, 3, [], at(12), RISE, SET)).not.toBe(3);
  });

  it("skips photos shown lately", () => {
    const recent = ["p0", "p1", "p2", "p4", "p5", "p6"];
    expect(recentLimit(lib.length)).toBe(6);
    for (let k = 0; k < 20; k++)
      expect(pickNext(lib, 3, recent, at(12), RISE, SET)).toBe(7);
  });

  it("starts over when everything was shown lately", () => {
    const recent = lib.map((p) => p.name);
    expect(pickNext(lib, 0, recent, at(12), RISE, SET)).not.toBe(0);
  });

  it("leans towards the hour's photos", () => {
    const pair = [BRIGHT, DARK, photo("x", { colours: ["#808080"] })];
    let dark = 0;
    for (let k = 0; k < 400; k++)
      if (pickNext(pair, 2, [], at(23), RISE, SET, sweep(k, 400)) === 1) dark++;
    expect(dark).toBeGreaterThan(240);
  });

  it("leans towards tall photos on a tall screen", () => {
    const mix = [
      photo("cur"),
      photo("tall", { aspect: 0.75 }),
      photo("wide", { aspect: 1.333 }),
      photo("turned", { aspect: 1.333, rotation: 90 }),
    ];
    const count = (tall: boolean) => {
      let n = 0;
      for (let k = 0; k < 400; k++) {
        const i = pickNext(mix, 0, [], at(12), RISE, SET, sweep(k, 400), tall);
        if (i === 1 || i === 3) n++;
      }
      return n;
    };
    expect(count(false)).toBeLessThan(300);
    expect(count(true)).toBeGreaterThan(330);
  });

  it("passes over the rest of a burst", () => {
    const t = at(12).getTime() / 1000;
    const shots = [
      photo("a", { taken_at: t }),
      photo("b", { taken_at: t + 5 }),
      photo("c", { taken_at: t + 86_400 }),
    ];
    let other = 0;
    for (let k = 0; k < 200; k++)
      if (pickNext(shots, 0, [], at(12), RISE, SET, sweep(k, 200)) === 2)
        other++;
    expect(other).toBeGreaterThan(160);
  });

  it("is lone or empty without a choice", () => {
    expect(pickNext([BRIGHT], 0, [], at(12), RISE, SET)).toBe(0);
    expect(pickNext([], 0, [], at(12), RISE, SET)).toBe(-1);
  });
});
