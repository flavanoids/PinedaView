// SPDX-License-Identifier: Apache-2.0
import {
  createClient,
  type Client,
  type UpdateStatus,
  type ViewModel,
} from "@pinedaview/protocol";

import { readLocal, writeLocal } from "./storage";

const CACHE_KEY = "pineda.lastView";
const UPDATE_CACHE_KEY = "pineda.updateStatus";

export type ConnectionStatus =
  "connecting" | "live" | "reconnecting" | "offline";

function readJson<T>(key: string): T | null {
  try {
    const raw = readLocal(key);
    return raw ? (JSON.parse(raw) as T) : null;
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
  view = $state<ViewModel | null>(readJson(CACHE_KEY));
  status = $state<ConnectionStatus>("connecting");
  identifyAt = $state(0);
  updateStatus = $state<UpdateStatus | null>(readJson(UPDATE_CACHE_KEY));

  #unsubscribe: (() => void) | null = null;
  #client: Client;
  #deviceId: string;

  constructor(baseUrl: string, deviceId: string) {
    this.#client = createClient(baseUrl);
    this.#deviceId = deviceId;
  }

  start(): void {
    void this.checkUpdate();
    this.#unsubscribe = this.#client.stream(this.#deviceId, {
      onView: (view) => {
        this.status = "live";
        this.view = view;
        writeLocal(CACHE_KEY, JSON.stringify(view));
        if (this.updateStatus?.state === "updating") void this.checkUpdate();
      },
      onGone: () => {
        this.status = "offline";
      },
      onIdentify: () => {
        this.identifyAt = Date.now();
      },
      onUpdateStatus: (status) => {
        this.updateStatus = status;
        writeLocal(UPDATE_CACHE_KEY, JSON.stringify(status));
      },
      onError: () => {
        this.status = this.view ? "reconnecting" : "connecting";
      },
    });
  }

  async checkUpdate(): Promise<void> {
    try {
      const s = await this.#client.getUpdateStatus();
      this.updateStatus = s;
      writeLocal(UPDATE_CACHE_KEY, JSON.stringify(s));
    } catch {
      // ignore
    }
  }

  dismissUpdate(): void {
    if (this.updateStatus) {
      this.updateStatus = { ...this.updateStatus, state: "idle" };
      writeLocal(UPDATE_CACHE_KEY, JSON.stringify(this.updateStatus));
    }
  }

  stop(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }
}
