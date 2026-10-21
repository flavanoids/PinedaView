// SPDX-License-Identifier: Apache-2.0
/**
 * The Settings sheet's shared state: the screens, profiles and household
 * config it edits, which screen it's editing (this one by default — a phone
 * can reach a locked wall screen's settings this way), and one place to save
 * through. Plain changes show at once and say nothing — the control moving is
 * the confirmation — and go back if the save fails; actions (copy, restore,
 * delete) pass the words to confirm them with.
 */
import { getContext, setContext } from "svelte";
import {
  createClient,
  type ConfigUpdate,
  type ConfigView,
  type Device,
  type DeviceUpdate,
  type Profile,
  type ProfileUpdate,
} from "@pinedaview/protocol";

const CONTEXT = Symbol("settings");
const STALE_AFTER_MS = 30 * 24 * 3600 * 1000;
/** How long an "Undo" stays offered — and so how long a delete waits. */
export const UNDO_MS = 5000;

export interface NoticeAction {
  label: string;
  run: () => void;
}

export class SettingsState {
  readonly client = createClient(import.meta.env.VITE_API_URL ?? "");
  readonly hereId: string;

  devices = $state<Device[]>([]);
  profiles = $state<Profile[]>([]);
  config = $state<ConfigView | null>(null);
  targetId = $state("");
  notice = $state<{
    text: string;
    error: boolean;
    /** A button on the toast — "Undo" after a delete. */
    action?: NoticeAction;
  } | null>(null);

  #noticeTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(hereId: string) {
    this.hereId = hereId;
    this.targetId = hereId;
  }

  /** Screens in use: seen in the last 30 days, this one, and the one being
      edited. Pairings that never came back (a browser opened once, a test
      run) would otherwise bury the real screens. */
  get activeScreens(): Device[] {
    const cutoff = Date.now() - STALE_AFTER_MS;
    return this.devices.filter(
      (d) =>
        d.id === this.hereId ||
        d.id === this.targetId ||
        (d.last_seen != null && Date.parse(d.last_seen) >= cutoff),
    );
  }
  get staleScreens(): Device[] {
    const active = new Set(this.activeScreens.map((d) => d.id));
    return this.devices.filter((d) => !active.has(d.id));
  }

  /** The screen being edited. */
  get screen(): Device | undefined {
    return this.devices.find((d) => d.id === this.targetId);
  }
  /** Its profile — where the shared look and timings live. */
  get profile(): Profile | undefined {
    return this.profiles.find((p) => p.id === this.screen?.profile_id);
  }
  get editingHere(): boolean {
    return this.targetId === this.hereId;
  }
  /** "this screen", or the other screen's name, for sentences. */
  get screenName(): string {
    return this.editingHere ? "this screen" : (this.screen?.name ?? "it");
  }

  async load(): Promise<void> {
    [this.devices, this.profiles, this.config] = await Promise.all([
      this.client.listDevices(),
      this.client.listProfiles(),
      this.client.getConfig(),
    ]);
    if (!this.screen) this.targetId = this.hereId;
  }

  flash(text: string, error = false, action?: NoticeAction): void {
    clearTimeout(this.#noticeTimer);
    this.notice = { text, error, action };
    this.#noticeTimer = setTimeout(
      () => (this.notice = null),
      error || action ? UNDO_MS : 1600,
    );
  }

  /** Press the toast's button, and put the toast away. */
  act(): void {
    const action = this.notice?.action;
    clearTimeout(this.#noticeTimer);
    this.notice = null;
    action?.run();
  }

  /** Run a save, then say how it went. Returns the result, or undefined. */
  async save<T>(work: () => Promise<T>, done = ""): Promise<T | undefined> {
    try {
      const result = await work();
      if (done) this.flash(done);
      return result;
    } catch {
      this.flash(
        "Couldn't save that. Check the connection and try again.",
        true,
      );
      return undefined;
    }
  }

  /** As `save`, for work with no result: did it succeed? */
  async attempt(work: () => Promise<unknown>, done = ""): Promise<boolean> {
    try {
      await work();
      if (done) this.flash(done);
      return true;
    } catch {
      this.flash(
        "Couldn't save that. Check the connection and try again.",
        true,
      );
      return false;
    }
  }

  async saveScreen(patch: DeviceUpdate): Promise<void> {
    const id = this.targetId;
    const before = this.devices;
    this.devices = before.map((d) => (d.id === id ? merged(d, patch) : d));
    const updated = await this.save(() => this.client.updateDevice(id, patch));
    this.devices = updated
      ? this.devices.map((d) => (d.id === id ? updated : d))
      : before;
  }

  async saveProfile(patch: ProfileUpdate): Promise<void> {
    const id = this.profile?.id;
    if (!id) return;
    const before = this.profiles;
    this.profiles = before.map((p) => (p.id === id ? merged(p, patch) : p));
    const updated = await this.save(() => this.client.updateProfile(id, patch));
    this.profiles = updated
      ? this.profiles.map((p) => (p.id === id ? updated : p))
      : before;
  }

  async saveConfig(patch: ConfigUpdate): Promise<void> {
    const before = this.config;
    if (before) this.config = merged(before, patch);
    const updated = await this.save(() => this.client.updateConfig(patch));
    this.config = updated ?? before;
  }
}

/** `item` as it will be once `patch` saves — so the control moves at once. */
function merged<T extends object>(item: T, patch: object): T {
  const set = Object.entries(patch).filter(([, v]) => v != null);
  return { ...item, ...Object.fromEntries(set) };
}

export function provideSettings(state: SettingsState): SettingsState {
  return setContext(CONTEXT, state);
}

export function useSettings(): SettingsState {
  return getContext<SettingsState>(CONTEXT);
}
