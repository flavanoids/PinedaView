// SPDX-License-Identifier: Apache-2.0
import { afterEach, describe, expect, it } from "vitest";

import {
  detectPi,
  initPlatform,
  platform,
  PLATFORM_KEY,
  stampPlatform,
} from "./platform.svelte";

function ua(value: string): void {
  Object.defineProperty(navigator, "userAgent", {
    value,
    configurable: true,
  });
}

const REAL_UA = navigator.userAgent;
afterEach(() => ua(REAL_UA));

describe("detectPi", () => {
  it("recognizes Raspberry Pi OS Chromium (armv7l)", () => {
    ua(
      "Mozilla/5.0 (X11; Linux armv7l) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    );
    expect(detectPi()).toBe(true);
  });

  it("recognizes 64-bit Raspberry Pi OS (aarch64)", () => {
    ua(
      "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    );
    expect(detectPi()).toBe(true);
  });

  it("recognizes an explicit Raspbian token", () => {
    ua("Mozilla/5.0 (X11; Raspbian) Gecko/20100101 Firefox/115.0");
    expect(detectPi()).toBe(true);
  });

  it("does not flag an iPad", () => {
    ua(
      "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    );
    expect(detectPi()).toBe(false);
  });

  it("does not flag an Android tablet/phone", () => {
    ua(
      "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    );
    expect(detectPi()).toBe(false);
  });

  it("does not flag a desktop browser", () => {
    ua(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    );
    expect(detectPi()).toBe(false);
  });
});

describe("stampPlatform and initPlatform", () => {
  afterEach(() => {
    delete document.documentElement.dataset.platform;
    platform.isPi = false;
    localStorage.clear();
  });

  it("stamps dataset.platform when platform.isPi is true", () => {
    platform.isPi = true;
    stampPlatform();
    expect(document.documentElement.dataset.platform).toBe("pi");
  });

  it("removes dataset.platform when platform.isPi is false", () => {
    document.documentElement.dataset.platform = "pi";
    platform.isPi = false;
    stampPlatform();
    expect(document.documentElement.dataset.platform).toBeUndefined();
  });

  it("honors localStorage override PLATFORM_KEY = 1", () => {
    localStorage.setItem(PLATFORM_KEY, "1");
    initPlatform();
    expect(platform.isPi).toBe(true);
    expect(document.documentElement.dataset.platform).toBe("pi");
  });

  it("honors localStorage override PLATFORM_KEY = 0", () => {
    localStorage.setItem(PLATFORM_KEY, "0");
    initPlatform();
    expect(platform.isPi).toBe(false);
    expect(document.documentElement.dataset.platform).toBeUndefined();
  });
});
