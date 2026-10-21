// SPDX-License-Identifier: Apache-2.0
import type { Client } from "@pinedaview/protocol";

import { readLocal, writeLocal } from "./storage";

export const KEY = "pineda.deviceId";

/** Return this browser's device id, pairing with the server on first run. */
export async function ensureDevice(client: Client): Promise<string> {
  const existing = readLocal(KEY);
  if (existing) return existing;

  const device = await client.pairDevice({
    name: "Screen",
    viewport_w: window.innerWidth,
    viewport_h: window.innerHeight,
    kind: deviceKind(navigator.userAgent, navigator.maxTouchPoints),
  });
  writeLocal(KEY, device.id);
  return device.id;
}

/** What this browser is, in words the phone menu shows ("iPad", "Android tablet"). */
export function deviceKind(ua: string, touchPoints: number): string {
  // iPadOS Safari says it's a Mac; only the touch screen gives it away.
  if (/iPad/.test(ua) || (/Macintosh/.test(ua) && touchPoints > 1))
    return "iPad";
  if (/iPhone/.test(ua)) return "iPhone";
  if (/Android/.test(ua))
    return /Mobile/.test(ua) ? "Android phone" : "Android tablet";
  if (/CrOS/.test(ua)) return "Chromebook";
  if (/Raspberry|armv7l|aarch64/.test(ua)) return "Display";
  return "Computer";
}

/** Tell the server this screen's current size, now and whenever it's
 *  turned or resized, so the phone menu draws it the right shape. */
export function reportViewport(baseUrl: string, id: string): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const send = (): void => {
    void fetch(`${baseUrl}/api/devices/${encodeURIComponent(id)}/viewport`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ w: window.innerWidth, h: window.innerHeight }),
    }).catch(() => {});
  };
  const later = (): void => {
    clearTimeout(timer);
    timer = setTimeout(send, 1000);
  };
  send();
  window.addEventListener("resize", later);
  return () => {
    clearTimeout(timer);
    window.removeEventListener("resize", later);
  };
}
