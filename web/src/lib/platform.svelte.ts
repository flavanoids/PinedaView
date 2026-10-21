// SPDX-License-Identifier: Apache-2.0
/**
 * Detects a Raspberry Pi client (as opposed to an iPad/Android/phone) so the
 * render path can be trimmed specifically for that hardware — the classic
 * Pi 3/4 Chromium kiosk has a much weaker GPU than any tablet or phone we
 * target, so it needs cuts the capability-based motion tier (tier.svelte.ts)
 * doesn't make on its own. Stamped as `data-platform="pi"` on <html>; tokens.css
 * keys off it directly, independent of the user's chosen motion tier.
 */
import { readLocal } from "./storage";

export const platform = $state<{ isPi: boolean }>({ isPi: false });

/**
 * A kiosk launch URL can seed this directly (`?pi=1`/`?pi=0`, wired up in
 * App.svelte's seedKioskParams, same pattern as the clock face and motion
 * tier) — it wins outright over detection. Sniffing is inherently fragile
 * (Chrome's User-Agent Reduction, or plain-HTTP kiosks where Client Hints
 * are unavailable — see detectPiClientHints below) and a provisioned kiosk
 * shouldn't be at the mercy of the next Chromium update.
 */
export const PLATFORM_KEY = "pineda.platformPi";

/**
 * Raspberry Pi OS Chromium reports an X11/Linux desktop-style UA carrying the
 * board's arm architecture (armv6l/armv7l/aarch64) — nothing else in our
 * target fleet does: Android's UA says "Android", never an arch token, and
 * iPadOS/iOS say "iPad"/"iPhone"/"CPU OS". A bare "Linux <arm arch>" with
 * neither of those present is specific enough to be a Pi.
 *
 * Chrome's User-Agent Reduction can genericize this string on Linux (the arch
 * token disappears), so this is a best-effort fallback — see
 * detectPiClientHints for the check that still works once that happens.
 */
export function detectPi(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  if (/android|iphone|ipad|ipod/i.test(ua)) return false;
  return (
    /raspbian|\braspberry pi\b/i.test(ua) ||
    /linux (armv6l|armv7l|aarch64)/i.test(ua)
  );
}

/**
 * User-Agent Client Hints report the real CPU architecture even after
 * Chrome's User-Agent Reduction freezes/genericizes navigator.userAgent —
 * this is the resilient path forward; detectPi()'s regex stays only as a
 * fallback for browsers that never supported UA-CH at all. Returns null when
 * the API (or the "architecture" hint) isn't available, so the caller can
 * fall back to the UA regex's result instead of overriding it with a guess.
 */
async function detectPiClientHints(): Promise<boolean | null> {
  const uaData = (navigator as { userAgentData?: UADataLike }).userAgentData;
  if (!uaData || uaData.mobile || uaData.platform !== "Linux") return null;
  try {
    const { architecture } = await uaData.getHighEntropyValues([
      "architecture",
    ]);
    if (!architecture) return null;
    return architecture.toLowerCase() === "arm";
  } catch {
    return null;
  }
}

interface UADataLike {
  mobile: boolean;
  platform: string;
  getHighEntropyValues(hints: string[]): Promise<{ architecture?: string }>;
}

export function initPlatform(): void {
  const override = readLocal(PLATFORM_KEY);
  if (override === "1" || override === "0") {
    platform.isPi = override === "1";
    stampPlatform();
    return;
  }

  platform.isPi = detectPi();
  stampPlatform();

  void detectPiClientHints().then((result) => {
    if (result === null) return;
    platform.isPi = result;
    stampPlatform();
  });
}

export function stampPlatform(): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (platform.isPi) root.dataset.platform = "pi";
  else delete root.dataset.platform;
}
