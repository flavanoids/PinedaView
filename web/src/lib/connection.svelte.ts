// SPDX-License-Identifier: Apache-2.0
import {
  createClient,
  type Client,
  type ViewModel,
} from "@pinedaview/protocol";

import { readLocal, writeLocal } from "./storage";

const CACHE_KEY = "pineda.lastView";

export type ConnectionStatus =
  "connecting" | "live" | "reconnecting" | "offline";

function readCache(): ViewModel | null {
  const raw = readLocal(CACHE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ViewModel;
  } catch {
    return null;
  }
}

/**
 * Holds the current view model, fed by the SSE stream. `EventSource` handles
 * its own reconnect backoff; we surface that as `status` and keep the last good
 * model in `localStorage` so a reload or a blip never shows a blank screen.
 */
export class Connection {
  view = $state<ViewModel | null>(readCache());
  status = $state<ConnectionStatus>("connecting");
  identifyAt = $state(0);

  #unsubscribe: (() => void) | null = null;
  #client: Client;
  #deviceId: string;

  constructor(baseUrl: string, deviceId: string) {
    this.#client = createClient(baseUrl);
    this.#deviceId = deviceId;
  }

  start(): void {
    this.#unsubscribe = this.#client.stream(this.#deviceId, {
      onView: (view) => {
        this.status = "live";
        this.view = view;
        writeLocal(CACHE_KEY, JSON.stringify(view));
      },
      onGone: () => {
        this.status = "offline";
      },
      onIdentify: () => {
        this.identifyAt = Date.now();
      },
      onError: () => {
        this.status = this.view ? "reconnecting" : "connecting";
      },
    });
  }

  stop(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }
}
