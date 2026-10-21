<!-- SPDX-License-Identifier: Apache-2.0 -->
# Installing PinedaView

One server renders the dashboard; every screen is just a browser pointed at it.
Install the server on any always-on Linux box on your network — a Raspberry Pi, a
NAS, an old laptop, even one of the tablets acting as both server and screen.

After any install, open `http://<server-host>:8090` and the **setup wizard**
runs. Nothing needs a config file by hand.

---

## Docker (recommended)

```bash
mkdir pinedaview && cd pinedaview
curl -sSLO https://raw.githubusercontent.com/flavanoids/PinedaView/main/docker-compose.yml
docker compose up -d
```

The image is multi-arch (`linux/amd64`, `linux/arm64`), runs as a non-root user,
and keeps photos, the database and config in `./data` and `./config`.

Single-container form:

```bash
docker run -d --name pinedaview -p 8090:8090 \
  -v "$PWD/data:/data" -v "$PWD/config:/etc/pinedaview" \
  ghcr.io/flavanoids/pinedaview:latest
```

## Debian / Ubuntu / Raspberry Pi OS (.deb)

```bash
curl -sSL https://raw.githubusercontent.com/flavanoids/PinedaView/main/scripts/install.sh | sh
```

or manually:

```bash
curl -sSLO https://github.com/flavanoids/PinedaView/releases/latest/download/pinedaview_<version>_arm64.deb
sudo apt install ./pinedaview_<version>_arm64.deb
sudo systemctl start pinedaview
```

Creates a `pineda` system user, a systemd unit (enabled on install), state in
`/var/lib/pinedaview`, and config in `/etc/pinedaview/config.toml`. It also
enables `pinedaview-guard`, which keeps `:8090` on the LAN and away from
tunnels ([OPERATIONS.md](OPERATIONS.md#keeping-it-on-the-lan)).

## Fedora / RHEL / openSUSE (.rpm)

```bash
sudo dnf install ./pinedaview-<version>.aarch64.rpm
sudo systemctl start pinedaview
```

## pipx (any distro, Python 3.11+)

```bash
pipx install pinedaview
pinedaview serve
```

The PyPI package bundles the web client. You supply the service manager — a user
systemd unit, `tmux`, whatever.

## From source (development)

```bash
git clone https://github.com/flavanoids/PinedaView
cd PinedaView
pnpm install
sh scripts/stage-web.sh          # build + bundle the client once
uv run --project core pinedaview serve
# or run the client with hot reload in a second terminal:
pnpm --filter @pinedaview/client dev
```

---

## Configuration

Every setting has a default; the wizard writes the rest. If you do want a file,
values are read in this order (**earlier wins**):

1. CLI flags — `pinedaview serve --port 9000 --location "90210"`
2. Environment — `PINEDA_*`, nested with `__`
   (`PINEDA_API__PORT=9000`, `PINEDA_LOCATION__QUERY=90210`)
3. `.env` in the working directory
4. A TOML config file:
   `$PINEDA_CONFIG_FILE` → `./config.toml` → `/etc/pinedaview/config.toml`
5. Built-in defaults

Start from [`core/config.example.toml`](../core/config.example.toml).

| Setting / Env | Purpose |
|---|---|
| `theme` / `PINEDA_THEME` | Color palette (`blush` default, `quiet_canvas`, `liquid_glass`, `warm`, `ocean`, etc.) |
| `disabled_cards` / `PINEDA_DISABLED_CARDS` | List of card IDs to disable (default `["commute", "phrase"]`) |
| `state_dir` / `PINEDA_STATE_DIR` | Database, secrets, affirmation history, wallpaper |
| `photos_dir` / `PINEDA_PHOTOS_DIR` | Uploaded photos directory |
| `cards_dir` / `PINEDA_CARDS_DIR` | Custom card folders (additive to built-ins) |
| `themes_dir` / `PINEDA_THEMES_DIR` | Custom theme files (.toml or .json, additive to built-ins) |
| `api.write_token` / `PINEDA_API__WRITE_TOKEN` | Require `Authorization: Bearer` on mutations |
| `api.admin_token` / `PINEDA_API__ADMIN_TOKEN` | Require bearer token on admin surface (reads and writes) |
| `api.adopt_unknown_devices` / `PINEDA_API__ADOPT_UNKNOWN_DEVICES` | Auto-adopt unrecognized screen IDs (for standby failover servers) |
| `[mqtt]` | Broker connection for Now-playing card — see [API.md](API.md#mqtt) |
| `[calendar]` | `bounce_url` — Google OAuth bounce redirect page, see [Calendar](#calendar-google--apple) |
| `[cameras]` | Home cameras via go2rtc and Home Assistant (`streams`, `titles`, `entities`, `ha_url`, `ha_token_file`) — the home-cams card and the full-screen camera card |
| `[mcp]` | MCP server at `/mcp` (`enabled`, `allowed_hosts`, `profile`, `clients.<name>.token_sha256` / `scopes`) — see [MCP.md](MCP.md) |
| `[control]` | Split-host kiosk remote restart (`host`, `user`, `ssh_key`) — see [OPERATIONS.md](OPERATIONS.md#split-host-control) |

## Adding screens

On each phone or tablet, open `http://<server-host>:8090` and **Add to Home
Screen** for a fullscreen PWA. Assign it a profile in Settings › Devices so each
screen shows its own card stack. Keep the screen awake with the device's own
"stay on while charging" / kiosk setting. New devices default to a **locked**
layout (no drag-to-rearrange), and the card grid stretches to fill the screen
instead of leaving a scrollable gap.

The client also detects a Raspberry Pi from its Chromium user agent and floors
it to the **Lite** motion tier automatically — no setup needed. This drops the
Liquid Glass backdrop blur, sheen and specular-rim effects entirely (not just
their intensity) and swaps photo transitions to an instant cut, since a Pi's
GPU can't back the numbers `hardwareConcurrency`/`deviceMemory` alone would
suggest. Settings › Accessibility can still override the tier per device.

### Wall-mounted / touchless kiosk

For a screen with no touch input (a Pi driving a wall-mounted panel, e.g.), run
a Wayland compositor and Chromium full-screen instead of a browser session:
[`packaging/pineda-kiosk.service`](../packaging/pineda-kiosk.service) is a
reference systemd unit (`cage` + `chromium --kiosk`) that waits for the local
server to answer before launching. Install manually per device — hardware, GPU
driver, and the local user vary too much to package generically:

```bash
sudo install -m 644 packaging/pineda-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pineda-kiosk.service
```

Adjust `User`/`Group` and `XDG_RUNTIME_DIR`'s uid in the unit to match the
target account first. On a large panel (a 2560px kiosk display, not a small
tablet), the hero and heading type scale and the Now-playing cover art size up
proportionally rather than clamping at small-screen sizes.

Point the unit's Chromium URL at the device's **LAN-reachable** hostname or
address with `?pi=1` (e.g. `http://<hostname>.local:8090/?pi=1`) — not `localhost`.
The `?pi=1` parameter seeds kiosk provisioning immediately on boot, ensuring the motion
tier is floored to lite, expensive glass shaders are bypassed, and mouse or touch
cursors are completely hidden (`cursor: none !important`). The app builds its own share
links (the photo-upload QR, "add another screen") from `location.origin`, so query
parameters do not leak into phones scanning the QR, whereas loading via `localhost` would
bake a URL that only resolves on the Pi itself.

This URL doesn't have to point at a server running on the same device — see
[OPERATIONS.md § Running the server on a different box than the
kiosk](OPERATIONS.md#running-the-server-on-a-different-box-than-the-kiosk)
for offloading `pinedaview` itself to a bigger always-on machine while this
Pi stays display-only.

#### Restart controls

Scanning the photo card's QR opens a small menu (`/menu`) with **Restart
display** and **Restart Raspberry Pi** buttons, backed by
`POST /api/control/restart-display` (restarts `pineda-kiosk.service`) and
`POST /api/control/restart-system` (`systemctl reboot`). A hardened service
account (`NoNewPrivileges=true`, as in the packaged `.deb`'s dedicated
`pineda` user) can't use `sudo` — it reaches systemd over D-Bus instead,
authorized by a polkit rule:

```bash
sudo install -m 644 packaging/pinedaview-restart.rules \
  /etc/polkit-1/rules.d/49-pinedaview.rules
sudo systemctl restart polkit
```

The rule authorizes both `pineda` (the packaged account) and `kiosk` (a
manual single-Pi setup running the server under the dedicated kiosk login, as
`pinedaview-kiosk.service` does) — edit it if your server runs as a different
account.

Without this rule the two buttons still appear but fail with a 500. The .deb
package installs the rule automatically when `/etc/polkit-1/rules.d` exists.

This assumes the server and the kiosk are the same device. When the server
runs elsewhere (see above), these buttons need
[`[control]`](OPERATIONS.md#split-host-control) configured instead, so they
still reach the actual kiosk device over SSH rather than acting on the
server's own host.

## Calendar (Google & Apple)

The calendar card connects entirely from a phone — no config file, no SSH.
While nothing is connected the card shows a QR pointing at `/connect-calendar`
(Google) and `/connect-apple-calendar` (Apple); either page also works typed
in directly. Both are additive: connecting one doesn't disturb the other,
saving one backend's calendar selection never touches the other's, and
disconnecting removes only that backend's account and calendars.

### Google

Google requires an HTTPS redirect URI for anything other than `localhost` — a
bare LAN device has neither. `calendar.bounce_url` is where Google redirects
to after consent. Point it at a tiny static page hosted anywhere with HTTPS.
Its only job is forwarding the `?code=&state=` query string it receives to
this server's own LAN address. The `state` value already carries that
address, so the page needs no per-install configuration, and the redirect
happens in your browser, which is on the LAN. Nothing in this project builds
or hosts that page for you; it's a few lines of HTML with a
`window.location` redirect. Don't expose the app itself over a tunnel or
reverse proxy for this. pinedaview must never be reachable from outside the
LAN, and `pinedaview-guard` blocks tunnels from reaching it
([OPERATIONS.md](OPERATIONS.md#keeping-it-on-the-lan)).

1. **console.cloud.google.com** → create/pick a project.
2. **APIs & Services → Library** → enable **Google Calendar API**.
3. **APIs & Services → OAuth consent screen** → External, Testing is fine for
   personal use → add your own Google account under **Test users** (a
   Testing-mode app rejects every account not on this list) → under
   **Scopes**, add `.../auth/calendar.readonly`.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID** →
   type **Web application** → under **Authorized redirect URIs**, add the
   exact URL `bounce_url` will be set to, e.g.
   `https://your-domain/api/calendar/oauth/finish`.
5. Copy the **Client ID** and **Client Secret**, then set them as secrets on
   the server (`PUT /api/secrets/google_calendar_client_id` and
   `_client_secret` — from Settings once a UI exists for it, or `curl`) and
   set `calendar.bounce_url` to the same URL from step 4
   (`PINEDA_CALENDAR__BOUNCE_URL`, or `[calendar]` in `config.toml`).

Testing mode caps things at ~100 explicitly-added accounts and never expires;
nothing here requires "publishing" the app.

### Apple / iCloud

No OAuth exists for iCloud calendars — `/connect-apple-calendar` is a plain
form asking for your Apple ID and an **app-specific password** (not your real
one; Apple blocks that for third-party clients). Generate one at
**appleid.apple.com → Sign-In and Security → App-Specific Passwords**, paste
both into the form, and it lists every calendar the account can see —
including ones privately shared with you — to pick from. No bounce page, no
Google Cloud project, no config file.

## Upgrading

- **Docker:** `docker compose pull && docker compose up -d`
- **.deb/.rpm:** install the new package; `config.toml` is kept (`noreplace`)
- **pipx:** `pipx upgrade pinedaview`

The running version shows at the bottom of the Settings sheet and at
`GET /api/health` (`app_version`).

## Troubleshooting

- **Wizard won't load / blank page** — check `GET /api/health` returns JSON. If it
  does, the client bundle is missing; use the Docker image or a release package
  rather than a bare `pip install` from a checkout.
- **Screens don't update** — the live channel is SSE over plain HTTP. A reverse
  proxy must not buffer `text/event-stream` (`proxy_buffering off` in nginx).
- **PWA install / wake-lock greyed out** — browsers require HTTPS. Put the server
  behind Tailscale, or a local reverse proxy with a real certificate.
- **Logs** — `journalctl -u pinedaview -f`, or `docker logs -f pinedaview`.
