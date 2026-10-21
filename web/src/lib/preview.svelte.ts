// SPDX-License-Identifier: Apache-2.0
/**
 * `/?preview=<device id>`: the phone menu's live miniature of a screen.
 *
 * The page draws that screen's live view, read-only: it never pairs, never
 * reports what it shows, and copies the screen's own clock face, Pi mode and
 * text scale (which live in the screen's browser, so it reports them — see
 * App's reportLook). The photo follows whatever the screen says it's showing
 * rather than running a slideshow of its own.
 */
import type { Client } from "@pinedaview/protocol";

import { clockFace, isClockFace } from "./clockface.svelte";
import { forceScale } from "./display.svelte";
import { platform } from "./platform.svelte";

export const previewId: string | null = (() => {
  if (typeof location === "undefined") return null;
  const id = new URLSearchParams(location.search).get("preview");
  const valid = id && /^[0-9a-f]{16}$/.test(id) ? id : null;
  if (valid && typeof document !== "undefined") {
    document.documentElement.dataset.preview = "true";
  }
  return valid;
})();

/** The photo the real screen has up, by name. */
export const mirror = $state<{ photo: string | null }>({ photo: null });

const POLL_MS = 10_000;

/** Keep copying the screen's look and photo. Returns a stop function. */
export function startMirror(client: Client, deviceId: string): () => void {
  async function poll(): Promise<void> {
    try {
      const shown = await client.nowShowing(deviceId);
      const look = shown.look;
      if (look) {
        if (isClockFace(look.clock_face)) clockFace.face = look.clock_face;
        platform.isPi = look.pi;
        forceScale(look.scale);
      }
      mirror.photo = shown.photo?.name ?? null;
    } catch {
      /* next poll */
    }
  }
  void poll();
  const id = setInterval(() => {
    if (!document.hidden) void poll();
  }, POLL_MS);
  return () => clearInterval(id);
}
