// SPDX-License-Identifier: Apache-2.0
export interface HelpEntry {
  title: string;
  body: string;
  tags: string[];
}

export const HELP: HelpEntry[] = [
  {
    title: "Change the weather location",
    body: "Settings → Time & weather → Weather for. Type a city, a US ZIP code, or “latitude,longitude”, or tap Find my location. Air quality, alerts and sunrise times follow it.",
    tags: ["weather", "location", "zip", "city", "forecast"],
  },
  {
    title: "Switch between °F and °C, or 12- and 24-hour time",
    body: "Settings → Time & weather → Format. Every screen updates straight away. The date under the clock can be full, short or hidden.",
    tags: [
      "units",
      "fahrenheit",
      "celsius",
      "temperature",
      "metric",
      "imperial",
      "24-hour",
      "12-hour",
      "date",
    ],
  },
  {
    title: "Change the theme or colours",
    body: "Settings → Appearance. Pick a theme, an accent colour, and what happens after sunset. Every screen on the same profile changes together.",
    tags: ["theme", "colour", "color", "accent", "look", "dark", "light"],
  },
  {
    title: "Turn on the morning countdown",
    body: "Settings → Time & weather → Morning countdown. Set when it starts and the time to leave; on weekday mornings the big card counts down, then flashes.",
    tags: ["countdown", "alarm", "morning", "alert", "school", "work"],
  },
  {
    title: "Rearrange the cards on a screen",
    body: "Settings → Cards & layout → Rearrange cards, or press and hold any card. Drag cards into place, then save to this screen or to its profile.",
    tags: ["layout", "rearrange", "cards", "order", "edit", "drag"],
  },
  {
    title: "Hide a card on one screen",
    body: "Settings → Cards & layout → turn the card off under “On this screen”. It keeps its place, so turning it back on puts it where it was.",
    tags: ["hide", "remove", "card", "off"],
  },
  {
    title: "Slow down or speed up the rotating cards",
    body: "Settings → Cards & layout → Rotation speed. Relaxed holds each quote, headline and camera view longer; Brisk moves on sooner. The photo timing is under Photos.",
    tags: ["speed", "pace", "slow", "fast", "rotate", "cycle", "quotes"],
  },
  {
    title: "Keep certain news or quotes off the screen",
    body: "Settings → Cards & layout → Hide topics. Add a word or phrase and any headline or quote mentioning it is skipped.",
    tags: ["news", "filter", "hide", "block", "headlines", "topics"],
  },
  {
    title: "Give a screen its own set of cards",
    body: "Settings → Screens & profiles → give that screen its own profile, or rearrange its cards and save them to that screen only. To make a new screen match an existing one, use Copy settings from.",
    tags: ["profile", "multiple", "devices", "tablet", "different", "copy"],
  },
  {
    title: "Change another screen's settings",
    body: "When there's more than one screen, “Settings for” at the top of Settings chooses which one you're changing — handy for a wall screen with no settings button.",
    tags: ["other", "screen", "kiosk", "remote", "device"],
  },
  {
    title: "Set the night clock and dimming",
    body: "Settings → Night & sleep. Choose when the night clock starts before weekdays and weekends, when it ends, and how long a tap shows the dashboard. You can also dim on a schedule or have the screen go dark.",
    tags: [
      "night",
      "clock",
      "dim",
      "brightness",
      "sleep",
      "blackout",
      "bedtime",
    ],
  },
  {
    title: "Add photos",
    body: "Settings → Photos → Add photos. Guests can add their own by scanning the code on the photo card or opening /upload; under Guests you can allow that, require your approval first, or turn it off.",
    tags: ["photo", "picture", "upload", "frame", "family", "guests"],
  },
  {
    title: "Change how the slideshow plays",
    body: "Settings → Photos → Slideshow. Choose how long each photo shows, the order (yours, newest first, or shuffled) and whether photos fill the card or show whole.",
    tags: ["slideshow", "shuffle", "order", "crop", "fit", "seconds"],
  },
  {
    title: "Add a Google Maps key for the Commute card",
    body: "Settings → Backup & server → API keys. The Commute card starts working once the key is saved.",
    tags: ["commute", "traffic", "google", "maps", "api key", "directions"],
  },
  {
    title: "Back up or move your settings",
    body: "Settings → Backup & server → Download backup saves every setting to a file. Restore from file puts them back, here or on another server. Photos and API keys aren't in the file.",
    tags: ["backup", "export", "import", "restore", "move", "save"],
  },
  {
    title: "Undo changes to a section",
    body: "Most sections end with Reset to defaults. It only resets that section, and says exactly what it will change before it does.",
    tags: ["reset", "default", "undo"],
  },
  {
    title: "A timer made no sound",
    body: "Settings → Timers → Sound picks the sound for this screen. Some browsers stay silent until the screen has been tapped once after loading.",
    tags: ["timer", "sound", "chime", "silent", "alarm"],
  },
  {
    title: "Motion feels sluggish",
    body: "Settings → Accessibility → Motion. Reduced stops card animation entirely; Auto picks what suits this device.",
    tags: [
      "slow",
      "laggy",
      "animation",
      "motion",
      "tier",
      "performance",
      "stutter",
    ],
  },
  {
    title: "“Reconnecting” keeps showing",
    body: "The screen reconnects on its own. If the message stays, the server can't be reached — check it's running and on the same network. The last dashboard stays on screen meanwhile.",
    tags: ["reconnecting", "offline", "connection", "stream", "sse", "network"],
  },
  {
    title: "Install the app or keep the screen awake",
    body: "Both need a secure (HTTPS) address. On a home network, use a Tailscale address, run Caddy with its local certificate, or point a real domain at the server. Then choose “Add to Home Screen”.",
    tags: [
      "install",
      "pwa",
      "https",
      "wake lock",
      "awake",
      "tailscale",
      "caddy",
      "certificate",
    ],
  },
  {
    title: "Write your own card",
    body: "A card is a folder in cards/ with a card.json. It declares what it needs (location, network, secret:<key>, photos, provider:<store>) and can include a provider.py. Run `pinedaview dev` to reload manifests as you edit. See docs/CARD_MANIFEST.md and docs/CARD_SDK.md.",
    tags: [
      "card",
      "develop",
      "sdk",
      "manifest",
      "plugin",
      "extend",
      "provider",
    ],
  },
  {
    title: "Start over",
    body: "Settings → Backup & server → Run setup walks through the first-run questions again. To clear everything, delete config.toml and household.json on the server and restart; screens and photos are kept.",
    tags: ["reset", "wipe", "start over", "config", "setup"],
  },
  {
    title: "Keyboard and screen readers",
    body: "Tab reaches every control; the setup wizard, Settings and card details keep focus inside and close with Escape. On the dashboard, Tab first offers “Rearrange cards” — activate it, move the focused card with the arrow keys, and press Escape to finish. Settings → Accessibility has motion, transparency, text size, contrast and spoken updates; your device's own reduce-motion and contrast settings are always respected.",
    tags: [
      "accessibility",
      "a11y",
      "keyboard",
      "screen reader",
      "focus",
      "voiceover",
      "reduced motion",
      "contrast",
    ],
  },
];
