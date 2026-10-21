# The API

The full contract is [`packages/protocol/openapi.json`](../packages/protocol/openapi.json)
(OpenAPI 3.1) — load it into any client generator. A typed TypeScript client is
`packages/protocol` (`createClient(baseUrl)`).

- **Base:** the same origin that serves the app, e.g. `http://pineda.local:8090`.
- **Version:** every `ViewModel` carries `version: "v0"`. Changes within v0 are
  additive; a breaking change bumps the number.
- **Network:** LAN, wg0 and loopback only, never the internet; enforced by
  `pinedaview-guard` (see [OPERATIONS.md](OPERATIONS.md#keeping-it-on-the-lan)).
- **Auth:** none by default (LAN trust). Two optional bearer gates:
    - `api.write_token` — every `POST` / `PUT` / `PATCH` / `DELETE` (incl.
      `/api/ingest`) needs `Authorization: Bearer <token>`.
    - `api.admin_token` — the admin surface (`/api/config`, `/api/secrets`,
      `/api/control`, `/api/setup`, `/api/profiles`, `/api/devices`, card settings)
      needs the token, **on reads too**. The public surface stays open.
- **Correlation:** every response carries `X-Request-ID`; send your own to trace
  a call through the logs (`req_id`).

## The shapes you'll use

### Health & Diagnostics

| Path                    | What                                                                                                                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/health`       | App version, provider list, subscribers, cards, ok status, uptime, and per-subsystem checks (`database`, `scheduler`, `mqtt`, `stores`); returns **503** if database is down |
| `GET /api/metrics`      | Prometheus text exposition                                                                                                                                                   |
| `GET /status`           | A no-JS HTML operator status page                                                                                                                                            |
| `GET /api/debug/stores` | Raw snapshots of all stores (for debugging/integration)                                                                                                                      |

### Views & Real-time Stream

| Path                         | What                                                                                                            |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `GET /api/view/{deviceId}`   | The finished `ViewModel` for one screen (touches `last_seen`)                                                   |
| `GET /api/stream/{deviceId}` | SSE connection: initial `view` snapshot, deltas on broadcast, `: ping` keepalives, `identify` and `gone` events |

### Devices & Profiles

| Path                                    | What                                                                                                                                                                                |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/devices`                      | List all paired screens and their metadata                                                                                                                                          |
| `POST /api/devices/pair`                | Pair a new screen (`name`, optional `profile_id`, `viewport_w`, `viewport_h`, `tier`)                                                                                               |
| `PATCH /api/devices/{deviceId}`         | Update device profile, name, locked status, hero card pin, blackout window, stack override, dynamic shuffle preferences (`dynamic_shuffle`, `shuffle_hold_s`, `ambient_cycle_m`), or `frame_inset` (0–20, % of the width a picture frame hides on each side) |
| `DELETE /api/devices/{deviceId}`        | Unpair a device                                                                                                                                                                     |
| `POST /api/devices/{deviceId}/identify` | Broadcast an identify highlight to that physical screen                                                                                                                             |
| `GET /api/profiles`                     | List all screen profiles                                                                                                                                                            |
| `POST /api/profiles`                    | Create a new profile (`name`, `layout`, `card_stack`, `theme`, `hero_card`)                                                                                                         |
| `PATCH /api/profiles/{profileId}`       | Update profile layout, card stack, theme, hero card pin, pushed clock face, or dynamic shuffle defaults (`dynamic_shuffle`, `shuffle_hold_s`, `ambient_cycle_m`)                    |
| `DELETE /api/profiles/{profileId}`      | Delete a profile                                                                                                                                                                    |

#### Dynamic Shuffle & Ambient Loop

- **`dynamic_shuffle`** (`boolean`): Automatically spotlights cards by rotating each active dashboard card into the hero slot for `shuffle_hold_s` before returning it to its grid tile via 60fps FLIP animation. When enabled, the small photo grid card is omitted (the full-screen Photo Clock handles photography), and the clock serves as the anchor hero.
- **`shuffle_hold_s`** (`integer`, default `15`): Dwell duration in seconds per card (10s, 15s, 30s, or 60s).
- **`ambient_cycle_m`** (`integer`, default `5`): When running the full-screen Photo Clock (`night_clock_photo: true`), automatically wakes the screen into the card dashboard for `peek_s` (e.g. 60s) every N minutes (2m, 5m, 10m, or 15m) before returning to the clock. Unbroken queue progress is remembered in `localStorage` across cycles.

### Cards & Settings

| Path                               | What                                                                                        |
| ---------------------------------- | ------------------------------------------------------------------------------------------- |
| `GET /api/cards`                   | Every discovered card, its manifest, and status (`ready` / `blocked` + missing requirement) |
| `GET /api/cards/{cardId}/settings` | Current setting values for a card                                                           |
| `PUT /api/cards/{cardId}/settings` | Update setting values for a card (persisted to `card_settings.json`)                        |

### Photos & Wallpaper

| Path                                       | What                                                                                                |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `GET /api/photos`                          | List all photos in the slideshow library                                                            |
| `POST /api/photos`                         | Upload a photo (JPEG/PNG/WebP/ProRAW DNG/Live video). Exempt from `write_token` for LAN guest drops |
| `DELETE /api/photos/{name}`                | Delete a photo and all versions/derivatives (thumbnails, display render, motion clip, depth cutout) |
| `POST /api/photos/{name}/rotate`           | Rotate a photo by 90/180/270 degrees                                                                |
| `POST /api/photos/reorder`                 | Update slideshow display order                                                                      |
| `POST /api/photos/{name}/use-as-wallpaper` | Set a photo as the Liquid Glass background wallpaper                                                |
| `GET /api/photos/{name}`                   | Original photo file (`Cache-Control: public, max-age=86400`)                                        |
| `GET /api/photos/{name}/display`           | Standard display-sized render (`Cache-Control: public, max-age=86400`)                              |
| `GET /api/photos/{name}/subject`           | Transparent WebP subject cutout (AI extracted, `Cache-Control: public, max-age=86400`)              |
| `GET /api/photos/{name}/thumb`             | Thumbnail render (`Cache-Control: public, max-age=86400`)                                           |
| `GET /api/photos/{name}/motion`            | Live Photo motion video clip (`Cache-Control: public, max-age=86400`)                               |
| `GET /api/wallpaper` / `HEAD`              | Current Liquid Glass background wallpaper image                                                     |
| `PUT /api/wallpaper`                       | Upload new background wallpaper image                                                               |
| `DELETE /api/wallpaper`                    | Clear custom background wallpaper (reverts to CSS gradient)                                         |

### Timers

| Path                            | What                                                             |
| ------------------------------- | ---------------------------------------------------------------- |
| `GET /api/timers`               | List all active timers                                           |
| `POST /api/timers`              | Create a new timer (`seconds`, `label`, optional `sound`)        |
| `PUT /api/timers/sync/{source}` | Mirror timers from another system (e.g. Antigua voice assistant) |
| `DELETE /api/timers/{timerId}`  | Cancel a running timer                                           |

### Calendar Integrations

| Path                                  | What                                                            |
| ------------------------------------- | --------------------------------------------------------------- |
| `GET /connect-calendar`               | Phone-friendly HTML landing page for Google OAuth setup         |
| `GET /api/calendar/oauth/finish`      | OAuth 2.0 redirect callback endpoint                            |
| `GET /api/calendar/account`           | Connected Google Calendar account info and selectable calendars |
| `POST /api/calendar/sources`          | Save selected Google calendar IDs to display                    |
| `POST /api/calendar/disconnect`       | Disconnect Google Calendar account                              |
| `GET /connect-apple-calendar`         | Phone-friendly HTML form for Apple ID + app-specific password   |
| `POST /api/calendar/apple/connect`    | Authenticate with Apple CalDAV                                  |
| `GET /api/calendar/apple/account`     | Connected Apple Calendar account info and selectable calendars  |
| `POST /api/calendar/apple/disconnect` | Disconnect Apple Calendar account                               |

### Full-Screen Takeovers

| Path                   | What                                                                      |
| ---------------------- | ------------------------------------------------------------------------- |
| `PUT /api/takeover`    | Mount a full-screen takeover card across screens (recipe, camera, guide)  |
| `PATCH /api/takeover`  | Update in-place state of an active takeover (step, ingredients, progress) |
| `DELETE /api/takeover` | Dismiss active takeover card                                              |

### MCP

| Path | What |
|---|---|
| `POST /mcp/` | MCP server (protocol 2026-07-28, stateless Streamable HTTP) for a voice assistant: display, takeover, timer and camera tools. Every call needs a client bearer token with the tool's scope — see [MCP.md](MCP.md) |

### Kiosk, Control & Web Interfaces

| Path                                    | What                                                                    |
| --------------------------------------- | ----------------------------------------------------------------------- |
| `GET /upload`                           | Standalone guest photo upload page (opened by photo card QR)            |
| `GET /menu`                             | Mobile companion switchboard (themes, settings, photos, alarms, controls) |
| `GET /api/menu-url`                     | Resolves the LAN menu URL for the kiosk                                 |
| `GET /manifest.json`                    | Web app manifest for iOS / Android Home Screen standalone mode          |
| `GET /apple-touch-icon.png`             | iOS home screen icon (PWA icon)                                         |
| `GET /apple-touch-icon-precomposed.png` | Precomposed iOS home screen icon fallback                               |
| `GET /settings`                         | Mobile-friendly settings sheet (redirects to `/menu#themes`)            |
| `POST /api/control/state`               | Override playback / alert states                                        |
| `POST /api/control/restart-display`     | Restart kiosk compositor/browser (local systemd or split-host SSH)      |
| `POST /api/control/restart-system`      | Reboot the kiosk machine (local systemd or split-host SSH)              |

### Media, Cameras & Voice Hooks

| Path | What |
|---|---|
| `GET /api/nowplaying/cover` | Current album art image from shairport-sync/MQTT |
| `GET /api/cams/{name}` | Cached live traffic camera JPEG |
| `GET /api/home-cams/{name}.jpg` | A home camera's latest snapshot (the home-cams card; the camera card's loading backdrop) |
| `GET /api/cameras/{name}/stream.mp4` | A home camera's live video (fMP4 relayed from go2rtc), only while that camera's card is up |
| `GET /api/now-showing` | Current on-screen items across devices (photo EXIF, quotes, daily phrase) |
| `POST /api/now-showing` | Report card item changes from screens |

### Configuration, Themes & Secrets

| Path                             | What                                                    |
| -------------------------------- | ------------------------------------------------------- |
| `GET /api/config`                | Read non-sensitive server configuration                 |
| `POST /api/config`               | Update configuration settings and broadcast view update |
| `GET /api/setup/detect-location` | Auto-detect server location via IP geolocation          |
| `POST /api/setup/complete`       | Complete first-run wizard and persist config            |
| `GET /api/themes`                | List all available palettes and surface types           |
| `POST /api/themes/apply`         | Switch active theme                                     |
| `GET /api/secrets`               | List registered secret names (values are never exposed) |
| `PUT /api/secrets/{name}`        | Store an encrypted secret value                         |
| `DELETE /api/secrets/{name}`     | Remove a stored secret                                  |

See [`OPERATIONS.md`](OPERATIONS.md) for health, metrics, logging, and failover details.

## Publishing data from outside

Any external system — Home Assistant, a cron job, another script — can push a
value into a **store**. Cards read stores through `ctx.data(...)`, so this is how
you feed a card without writing a `provider.py`.

```bash
curl -X POST http://pineda.local:8090/api/ingest/commute \
  -H 'content-type: application/json' \
  -d '{"routes":[{"label":"Work","minutes":24,"delayMinutes":6}]}'
# → 202
```

The body is stored verbatim as that store's value and every connected screen
re-renders. The store name must be alphanumeric (`-` and `_` allowed). A card
that `needs: ["provider:commute"]` becomes usable as soon as something — a
built-in provider _or_ an ingest call — publishes to `commute`.

If a write token is configured, add `-H "Authorization: Bearer <token>"`.

## Full-screen takeovers

One card can cover every screen for a while — Antigua puts the recipe it's
reading up this way. A new one replaces the old; it comes down by itself at
`expires_at`, or on `DELETE`. Kept in memory only.

```bash
curl -X PUT http://pineda.local:8090/api/takeover \
  -H 'content-type: application/json' \
  -d '{"seconds":120,"card":{"kind":"recipe","title":"Piña Coladas","source":"Food Network",
       "servings":"makes 2 drinks","total_min":5,
       "ingredients":[{"name":"","items":["1 1/2 cups ice","2 ounces white rum"]}],
       "steps":["Blend until smooth.","Pour into 2 glasses."]}}'
curl -X PATCH http://pineda.local:8090/api/takeover \
  -H 'content-type: application/json' -d '{"current_step":1}'
curl -X DELETE http://pineda.local:8090/api/takeover   # → 204, up or not
```

What's being read is optional, and shows two ways. Before the steps (`stage`
`"ingredients"`) the ingredient list fills the screen beside a preview of
step 1; once they start (`"steps"`) the step being read, `current_step`
(0-based), is drawn as large as it fits between the one before and the one
after. `stage` left out goes by `current_step`: steps once there is one.

Ingredient lines are counted across the groups, in order:
`current_ingredients` are highlighted (the line being checked, or the ones
the current step uses), `checked` are quieter, `skipped` are struck through,
and `swaps` (`[{"index": 2, "use": "coconut milk"}]`) are struck through with
the substitute after them.

```bash
curl -X PATCH http://pineda.local:8090/api/takeover \
  -H 'content-type: application/json' \
  -d '{"stage":"steps","current_step":3,"current_ingredients":[0,6]}'
```

`PATCH` changes only the fields it's sent (`null` clears one) on the card
that's up, keeping its time left. With nothing up it returns `null` and
changes nothing: it never brings back a dismissed or expired card.

`seconds` is 1–3600 (default 120). The view model carries it as `takeover`
(`card`, `shown_at`, `expires_at`); the client draws it over the dashboard and
the night clock in the theme's colours and fonts, sizing the text to fit.

An **image search collage card** (`{"kind":"image_search","query":"strawberries","images":[...],"highlight":null}`)
packs search results into an interlocking bento / Tetris mosaic grid on the screen. Each tile features an image, title, source domain, and a frosted letter badge (`[A]`, `[B]`, `[C]`, etc.) for voice interaction.
Calling `PATCH /api/takeover` with `{"highlight":"B"}` spotlights the chosen tile with a golden halo and scale animation without restarting the card's display timer:

```bash
curl -X PUT http://pineda.local:8090/api/takeover \
  -H 'content-type: application/json' \
  -d '{"seconds":120,"card":{"kind":"image_search","query":"strawberries",
       "images":[{"id":"A","url":"https://example.com/a.jpg","title":"Strawberry","source":"wikimedia.org"}]}}'
curl -X PATCH http://pineda.local:8090/api/takeover \
  -H 'content-type: application/json' -d '{"highlight":"A"}'
```

A camera card (`{"kind":"camera","camera":"front_door"}`) is different in
three ways. It inflates full screen from the bottom-right corner and shrinks
back there when it's done. Put up over another card (a recipe), it sets that
card aside and brings it back, with its time left, when the camera comes
down. And with `[cameras] ha_url` set, this server starts the camera's
livestream in Home Assistant when the card goes up and stops it the moment
the card is gone, to save the battery. Showing the same camera again only
extends it.

## MQTT

Set `[mqtt] enabled = true` (host, port, topics) in `config.toml`. The server
subscribes read-only and maps `airplaypi/track`, `airplaypi/play_start` and
`airplaypi/play_end` into the `nowPlaying` store — so the **Now playing** card
works alongside your AirPlay receiver on the same broker. `mqtt:<topic>` needs
resolve once the broker is connected.
