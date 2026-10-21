// SPDX-License-Identifier: Apache-2.0
import type { components } from "./schema.gen";

type Schema = components["schemas"];

export type ViewModel = Schema["ViewModel"];
export type Hero = Schema["Hero"];
export type ViewCard = Schema["ViewCard"];
export type Ticker = Schema["Ticker"];
export type AlertBanner = Schema["AlertBanner"];
export type DisplayState = Schema["DisplayState"];
export type ConfigView = Schema["ConfigView"];
export type ConfigUpdate = Schema["ConfigUpdate"];
export type Theme = Schema["Theme"];
export type ThemeList = Schema["ThemeList"];
export type Device = Schema["Device"];
export type Profile = Schema["Profile"];
export type Grid = Schema["Grid"];
export type GridItem = Schema["GridItem"];
export type LayoutSnapshot = Schema["LayoutSnapshot"];
export type Health = Schema["Health"];
export type Timer = Schema["Timer"];
export type CardView = Schema["CardView"];
export type CardSettings = Schema["CardSettings"];
export type Photo = Schema["Photo"];
export type SecretList = Schema["SecretList"];
export type NowShowingView = Schema["NowShowingView"];
export type ScreenLook = Schema["ScreenLook"];
export type ScreenPrefs = Schema["ScreenPrefs"];
export type DeviceUpdate = Schema["DeviceUpdate"];
export type ProfileUpdate = Schema["ProfileUpdate"];
export type Backup = Schema["Backup"];
export type RestoreSummary = Schema["RestoreSummary"];
export type ResetSection = Schema["ResetRequest"]["section"];
export type ConnectionStatus = Schema["ConnectionStatus"];
export type CalendarChoice = Schema["CalendarChoice"];
export type CalendarSource = Schema["CalendarSource"];
export type CustomColours = Schema["CustomColours"];

export const PROTOCOL_VERSION = "v0";

export class ProtocolError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
    /** The server's own explanation (FastAPI's `detail`), when it gave one. */
    readonly detail?: string,
  ) {
    super(detail ?? `${path} → HTTP ${status}`);
    this.name = "ProtocolError";
  }
}

export interface StreamHandlers {
  onView(view: ViewModel): void;
  onGone?(): void;
  onIdentify?(): void;
  onError?(error: Event): void;
}

export function createClient(baseUrl: string) {
  const base = baseUrl.replace(/\/$/, "");

  async function call<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(base + path, {
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as {
        detail?: unknown;
      } | null;
      const detail = typeof body?.detail === "string" ? body.detail : undefined;
      throw new ProtocolError(response.status, path, detail);
    }
    return response.status === 204
      ? (undefined as T)
      : ((await response.json()) as T);
  }

  const post = <T>(path: string, body: unknown) =>
    call<T>(path, { method: "POST", body: JSON.stringify(body) });

  return {
    health: () => call<Health>("/api/health"),
    view: (deviceId: string) => call<ViewModel>(`/api/view/${deviceId}`),

    getConfig: () => call<ConfigView>("/api/config"),
    updateConfig: (patch: ConfigUpdate) =>
      post<ConfigView>("/api/config", patch),
    detectLocation: () =>
      call<Schema["DetectedLocationView"] | null>("/api/setup/detect-location"),
    completeSetup: () => post<ConfigView>("/api/setup/complete", {}),
    /** Put one Settings section back to its defaults. */
    resetSection: (body: Schema["ResetRequest"]) =>
      post<ConfigView>("/api/config/reset", body),
    exportSettings: () => call<Backup>("/api/config/backup"),
    restoreSettings: (backup: Backup) =>
      post<RestoreSummary>("/api/config/restore", backup),

    listThemes: () => call<ThemeList>("/api/themes"),
    applyTheme: (name: string) =>
      post<ThemeList>("/api/themes/apply", { name }),
    createCustomTheme: (body: Schema["CustomColours"]) =>
      post<Theme>("/api/themes/custom", body),
    updateCustomTheme: (name: string, body: Schema["CustomColours"]) =>
      call<Theme>(`/api/themes/custom/${encodeURIComponent(name)}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    deleteCustomTheme: (name: string) =>
      call<void>(`/api/themes/custom/${encodeURIComponent(name)}`, {
        method: "DELETE",
      }),

    listDevices: () => call<Device[]>("/api/devices"),
    pairDevice: (body: Schema["PairRequest"]) =>
      post<Device>("/api/devices/pair", body),
    updateDevice: (id: string, body: Schema["DeviceUpdate"]) =>
      call<Device>(`/api/devices/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    unpairDevice: (id: string) =>
      call<void>(`/api/devices/${id}`, { method: "DELETE" }),
    identifyDevice: (id: string) =>
      post<void>(`/api/devices/${id}/identify`, {}),
    /** Copy another screen's settings (schedule, cards, brightness) onto this one. */
    copyScreen: (id: string, source: string) =>
      post<Device>(`/api/devices/${id}/copy-from`, { source }),
    /** Hand-placed layout for a screen; null goes back to the automatic one. */
    setGrid: (id: string, grid: Grid | null) =>
      call<Device>(`/api/devices/${id}/grid`, {
        method: "PUT",
        body: JSON.stringify({ grid }),
      }),
    gridHistory: (id: string) =>
      call<LayoutSnapshot[]>(`/api/devices/${id}/grid/history`),

    listProfiles: () => call<Profile[]>("/api/profiles"),
    createProfile: (name: string, copyFrom?: string) =>
      post<Profile>("/api/profiles", { name, copy_from: copyFrom }),
    updateProfile: (id: string, body: Schema["ProfileUpdate"]) =>
      call<Profile>(`/api/profiles/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    deleteProfile: (id: string) =>
      call<void>(`/api/profiles/${id}`, { method: "DELETE" }),

    listCards: () => call<CardView[]>("/api/cards"),
    getCardSettings: (id: string) =>
      call<CardSettings>(`/api/cards/${id}/settings`),
    setCardSettings: (id: string, values: Record<string, unknown>) =>
      call<CardSettings>(`/api/cards/${id}/settings`, {
        method: "PUT",
        body: JSON.stringify({ values }),
      }),

    listSecrets: () => call<SecretList>("/api/secrets"),
    setSecret: (name: string, value: string) =>
      call<void>(`/api/secrets/${name}`, {
        method: "PUT",
        body: JSON.stringify({ value }),
      }),
    deleteSecret: (name: string) =>
      call<void>(`/api/secrets/${name}`, { method: "DELETE" }),

    /** Settings → Connect: every outside service, and whether it's hooked up. */
    listConnections: () => call<ConnectionStatus[]>("/api/connect"),
    connectAppleCalendar: (body: Schema["AppleCalendarConnect"]) =>
      call<CalendarChoice[]>("/api/connect/apple-calendar", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    disconnectAppleCalendar: () =>
      post<void>("/api/calendar/apple/disconnect", {}),
    disconnectGoogleCalendar: () => post<void>("/api/calendar/disconnect", {}),
    /** The calendars a connected account can show, ticked if they're shown. */
    calendarChoices: (
      backend: "apple-calendar" | "google-calendar" | "calendar-links",
    ) =>
      call<CalendarChoice[]>(
        backend === "calendar-links"
          ? "/api/connect/calendar-links"
          : `/api/connect/${backend}/calendars`,
      ),
    /** Replaces the shown calendars of each backend named in `sources`. */
    setCalendarSources: (sources: CalendarSource[]) =>
      post<void>("/api/calendar/sources", { sources }),
    addCalendarLink: (body: Schema["CalendarLinkAdd"]) =>
      post<CalendarChoice>("/api/connect/calendar-links", body),
    removeCalendarLink: (id: string) =>
      call<void>(`/api/connect/calendar-links/${id}`, { method: "DELETE" }),
    connect: (
      id: "home-assistant" | "antigua" | "cameras" | "airplay",
      body:
        | Schema["HomeAssistantConnect"]
        | Schema["AntiguaConnect"]
        | Schema["CamerasConnect"]
        | Schema["MqttConnect"],
    ) =>
      call<void>(`/api/connect/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    disconnect: (id: "home-assistant" | "antigua" | "airplay") =>
      call<void>(`/api/connect/${id}`, { method: "DELETE" }),

    listPhotos: () => call<Photo[]>("/api/photos"),
    photoUrl: (name: string) => `${base}/api/photos/${name}`,
    photoThumbUrl: (name: string) => `${base}/api/photos/${name}/thumb`,
    /** Screen-sized copy for the slideshow (falls back to the original). */
    photoDisplayUrl: (name: string) => `${base}/api/photos/${name}/display`,
    /** Transparent foreground subject cutout (WebP) for depth clock mode. */
    photoSubjectUrl: (name: string) => `${base}/api/photos/${name}/subject`,
    /** The clip (H.264, silent) that plays over a photo made from a Live
        Photo saved as a video; only when `photo.motion`. */
    photoMotionUrl: (name: string) => `${base}/api/photos/${name}/motion`,
    deletePhoto: (name: string) =>
      call<void>(`/api/photos/${name}`, { method: "DELETE" }),
    rotatePhoto: (name: string, degrees: number) =>
      call<Photo>(`/api/photos/${name}/rotate?degrees=${degrees}`, {
        method: "POST",
      }),
    reorderPhotos: (names: string[]) =>
      call<Photo[]>("/api/photos/reorder", {
        method: "POST",
        body: JSON.stringify({ names }),
      }),
    photoToWallpaper: (name: string) =>
      call<void>(`/api/photos/${name}/use-as-wallpaper`, { method: "POST" }),
    /** The owner's upload: straight into the slideshow, whatever the guest policy. */
    uploadPhoto: async (file: File): Promise<Photo> => {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${base}/api/photos/library`, {
        method: "POST",
        body: form,
      });
      if (!response.ok)
        throw new ProtocolError(response.status, "/api/photos/library");
      return (await response.json()) as Photo;
    },
    pendingPhotos: () => call<Photo[]>("/api/photos/pending"),
    approvePhoto: (name: string) =>
      post<Photo>(`/api/photos/${name}/approve`, {}),

    wallpaperUrl: (rev = 0) => `${base}/api/wallpaper${rev ? `?v=${rev}` : ""}`,
    hasWallpaper: async (): Promise<boolean> =>
      (await fetch(`${base}/api/wallpaper`, { method: "HEAD" })).ok,
    setWallpaper: async (file: File): Promise<void> => {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${base}/api/wallpaper`, {
        method: "PUT",
        body: form,
      });
      if (!response.ok)
        throw new ProtocolError(response.status, "/api/wallpaper");
    },
    clearWallpaper: () => call<void>("/api/wallpaper", { method: "DELETE" }),

    setState: (body: Schema["StateRequest"]) =>
      post<void>("/api/control/state", body),

    listTimers: () => call<Timer[]>("/api/timers"),
    addTimer: (
      seconds: number,
      label: string,
      kind: "timer" | "alarm" = "timer",
    ) => post<Timer>("/api/timers", { seconds, label, kind }),
    clearTakeover: () => call<void>("/api/takeover", { method: "DELETE" }),
    cancelTimer: (id: string) =>
      call<void>(`/api/timers/${id}`, { method: "DELETE" }),

    /** Tell the server which photo/quote this screen just put up, so a voice
        assistant can answer "when was this taken?". Best-effort: never throws. */
    reportShowing: (deviceId: string, card: "photo" | "quote", item: string) =>
      post<void>("/api/now-showing", { device_id: deviceId, card, item }).catch(
        () => undefined,
      ),

    /** Tell the server how this screen draws itself (clock face, Pi mode, text
        scale) for the phone menu's live miniature. Best-effort: never throws. */
    reportLook: (deviceId: string, look: ScreenLook) =>
      post<void>("/api/now-showing/look", {
        device_id: deviceId,
        ...look,
      }).catch(() => undefined),

    nowShowing: (deviceId: string) =>
      call<NowShowingView>(
        `/api/now-showing?device_id=${encodeURIComponent(deviceId)}`,
      ),

    /** Subscribe to the live view model. Returns an unsubscribe function. */
    stream(deviceId: string, handlers: StreamHandlers): () => void {
      const source = new EventSource(`${base}/api/stream/${deviceId}`);
      source.addEventListener("view", (event) => {
        handlers.onView(
          JSON.parse((event as MessageEvent<string>).data) as ViewModel,
        );
      });
      source.addEventListener("gone", () => {
        handlers.onGone?.();
        source.close();
      });
      source.addEventListener("identify", () => handlers.onIdentify?.());
      source.onerror = (event) => handlers.onError?.(event);
      return () => source.close();
    },
  };
}

export type Client = ReturnType<typeof createClient>;
