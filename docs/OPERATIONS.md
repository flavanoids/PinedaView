<!-- SPDX-License-Identifier: Apache-2.0 -->
# Running it in production

There is no screen on the server, so it tells you how it's doing three ways.

## `/status` — a page for a human

`http://<host>:8090/status` — a no-JS page: version, uptime, each health check,
and every data store with its freshness. Bookmark it.

## `GET /api/health` — a check for a machine

```json
{
  "ok": true,
  "status": "ok",
  "app_version": "1.0.0",
  "uptime_s": 4210.6,
  "providers": ["weather", "moon", "..."],
  "subscribers": 3,
  "cards_ready": 9,
  "cards_total": 12,
  "checks": {
    "database": "ok",
    "scheduler": "ok",
    "mqtt": "connected",
    "stores": "8/9 fresh",
    "stale_stores": "airQuality"
  }
}
```

Returns **503** when a check the server genuinely needs fails (the database). A
stale provider or a disconnected optional broker is reported in `checks` but
stays `200` / `ok: true`. This is the Docker `HEALTHCHECK` and what a load
balancer or `systemd` watchdog should poll.

If the MQTT broker rejects the connection outright (wrong password, not
authorized, a banned client id) rather than being merely unreachable, `mqtt`
names it: `"configured, not connected (Not authorized)"`. A plain `"configured,
not connected"` with no parenthetical means the TCP connect itself never
completed — check the host/port and any firewall between the two boxes.

## `GET /api/metrics` — Prometheus

Standard text exposition. Useful series:

| Metric | |
|---|---|
| `pineda_up` | always `1` while responding |
| `pineda_build_info{version=}` | release |
| `pineda_sse_subscribers` | connected screens |
| `pineda_providers_running` | scheduler poll loops |
| `pineda_cards_ready` / `pineda_cards_total` | |
| `pineda_mqtt_connected` | 0/1 (only if a broker is configured) |
| `pineda_store_stale{store=}` | 0/1 per store |
| `pineda_store_age_seconds{store=}` | seconds since last good value |

Scrape config:

```yaml
scrape_configs:
  - job_name: pinedaview
    static_configs: [{ targets: ["pineda.local:8090"] }]
```

## Logging & Diagnostics Strategy

PinedaView follows an **efficient, modular, and bounded** logging and diagnostic strategy designed to prevent filesystem and journal overflow on both the host server and edge kiosk screens, while ensuring rich verbosity when troubleshooting.

### Logs & Structured Output

- **Terminal & Services**: Plain text for interactive debugging; pass `--log-json` (or `PINEDA_LOG_JSON=true`) for machine-readable JSON in production systemd and Docker environments.
- **Request Tracing**: Every inbound request receives a correlation ID—returned in the `X-Request-ID` response header and stamped as `req_id` on every log record produced during that turn. Send your own `X-Request-ID` to trace a request across hosts.
- **Cross-Service MCP Traces**: MCP tool calls from Antigua (or other agents) include a W3C `traceparent` (in `_meta`). These are recorded in `/var/lib/pinedaview/mcp_audit.db` alongside execution latency (`ms`), tool name, and client identity, linking voice assistant turns directly to display actions.

```bash
journalctl -u pinedaview -f          # .deb / .rpm
docker logs -f pinedaview            # Docker
```

### Preventing Log & Journal Overflow

Wall-mounted screens and automated pollers generate continuous traffic. PinedaView uses active protections to avoid disk and journal bloat:

1. **Access Log Polling Noise Suppression**:
   Kiosk devices poll `/api/health` every 5 seconds (~17,280 requests/day per screen). In default `INFO` logging, routine `200 OK` health poll lines are filtered from the `uvicorn.access` log stream. Any non-200 responses (e.g. 500/503 errors) and all functional API endpoints (`/api/photos/...`, `/api/control/...`, `/mcp/`) continue to log normally. Set `PINEDA_LOG_LEVEL=DEBUG` when raw access logs for health probes are needed for diagnosis.
2. **Systemd Journal Sizing**:
   Bound journal growth on both server host and kiosk by configuring `/etc/systemd/journald.conf.d/pineda.conf`:
   ```ini
   [Journal]
   SystemMaxUse=500M
   RuntimeMaxUse=100M
   ```
3. **Audit Database Retention**:
   The MCP audit database (`/var/lib/pinedaview/mcp_audit.db`) maintains a rolling 30-day window (`DELETE FROM calls WHERE ts < ...`), keeping SQLite write volume small via WAL mode and batched asynchronous background commits.

## Visual Troubleshooting with Grim Screenshots

When troubleshooting a wall-mounted screen, text logs alone rarely reveal if a display has frozen, suffered WebGL context loss, rendered a blank white screen, or hit a CSS animation glitch. 

PinedaDisplay uses [grim](https://github.com/emersion/grim) on Wayland (`cage`) for safe, lightweight screen captures.

### Why Grim (Single-GPU Kiosk Safety)

On resource-constrained hardware like a Raspberry Pi, **never** use headless browser automation (Puppeteer, Playwright, or `chromium --headless`) against a live kiosk. Spawning a second Chromium process or extra GPU context contends for the single shared GPU and will freeze or crash the live compositor.

`grim` asks the `cage` compositor directly to copy its already-composited output buffer over the `wlr-screencopy` protocol:
- **Zero browser overhead**: No second browser process or DOM tree.
- **Lightweight**: Fast (~0.3s Pi CPU time for a compressed buffer copy).
- **Safe**: Non-intrusive to the running Chromium session.

### Using Grim Screenshots for Troubleshooting

1. **On-Demand Developer Capture (CLI)**:
   Grab a full-resolution PNG of what the kiosk is currently displaying:
   ```bash
   packaging/screenshot-kiosk.sh airplaypi kiosk.png
   ```
   Requires `grim` installed on the kiosk device (`sudo apt install grim`).

2. **Remote Phone Menu / API**:
   The phone menu (`/menu`) and `GET /api/control/snapshot` endpoint run `pineda-snapshot` over the dedicated SSH control key via `packaging/pineda-control-wrapper.sh`, thumbnailing the frame on the server to a lightweight ~60 KB JPEG.

3. **Pre-Restart & Crash Visual Post-Mortem**:
   Before executing a display restart (`POST /api/control/restart-display`) or system reboot (`POST /api/control/restart-system`), the server automatically captures a pre-restart diagnostic snapshot into `/var/lib/pinedaview/diagnostics/kiosk-restart-<timestamp>.jpg`.
   - Preserves what was on the screen immediately before the restart occurred (e.g., error banners, frozen clocks, or blank renderers).
   - Automatically maintains a bounded FIFO ring buffer (maximum 10 snapshots, ~1 MB total), ensuring visual post-mortems are available without filling disk space.

## Debugging on the kiosk device

The kiosk box (a Raspberry Pi in the common case) is resource-constrained on
purpose — see "Running the server on a different box" below for why. Two
rules for anything run there over SSH while chasing a problem, both learned
the hard way:

- **Bound every log query.** `journalctl` with no `--since`/`-n` walks the
  *entire* journal — on a box with days of history this can run for many
  minutes, burning real CPU on hardware you're specifically trying to keep
  light, exactly while you're trying to measure whether it's under load.
  Always pass `--since "-1 hour"` (or similar) or `-n 200`. If you do start
  an unbounded one anyway (or chain several in one shell script — killing
  the first child leaves the rest of the script running and starts the
  next), track down and kill the whole script's PID, not just the `journalctl`
  child, and confirm with `ps aux | grep journalctl` that nothing's still
  running before trusting any load measurement you take afterward.
- **Never run a second Chromium/headless-browser process** against a
  single-GPU kiosk — see "Screenshotting a kiosk" above.

## Keeping kiosk CPU load down

Two things quietly cost real CPU on a kiosk box for no benefit, both already
fixed in `packaging/pineda-kiosk.service` — worth knowing about so a future
edit doesn't undo them:

- **`/usr/bin/chromium` is a wrapper, not the binary**, on Debian/Raspberry
  Pi OS (`file /usr/bin/chromium` shows it's a shell script). It
  unconditionally injects `--force-renderer-accessibility` (rebuilds the
  full accessibility tree on every layout change — continuous cost, no
  screen reader ever attached to a kiosk) and auto-loads whatever's in
  `/usr/share/chromium/extensions` plus the profile's installed extensions
  (ad blockers etc. — dead weight against one trusted local URL). The unit
  invokes `/usr/lib/chromium/chromium` directly instead, passing the useful
  flags the wrapper would have added (`--enable-gpu-rasterization`,
  `--use-angle=gles`) explicitly plus `--disable-extensions`. Confirm it stuck: `ps aux | grep
  force-renderer-accessibility` should find nothing.
- **No `--disable-dev-shm-usage`**, even though the wrapper adds it. It moves
  Chromium's shared memory (decoded images, raster tiles) from `/dev/shm`
  (RAM) to `/tmp`, and on Raspberry Pi OS `/tmp` is on the SD card, not a
  tmpfs. On airplaypi that was ~6 MB/s of renderer writes, mostly photo
  decodes. That I/O competes with Antigua and wears out the card. Removing the flag
  took total SD writes from ~1.9 MB/s to ~0.4 MB/s (2026-09-23). The flag is
  meant for Docker's 64 MB `/dev/shm`; a Pi's is ~900 MB. Check with
  `df -h /dev/shm`: Chromium should be using tens of MB there.
- **A redundant local `pinedaview.service`** left running on a kiosk device
  after moving the server elsewhere (see "Running the server on a different
  box" below) polls every provider into stores nobody reads, for nothing.

## Kiosk cursor suppression

Wall-mounted dashboards and touch kiosks must never display an idle or wandering
mouse arrow, hand pointer, or text caret. PinedaDisplay enforces this at multiple
layers on the Raspberry Pi:

- **Application-Level CSS:** When running on a Pi (`data-platform="pi"` stamped on
  `<html>`), `:root[data-platform="pi"]:not([data-preview]) *` forces `cursor: none !important`
  across all DOM elements and pseudo-elements. Under Wayland, when the focused fullscreen
  surface sets an empty/null cursor, Chromium instructs the compositor (`cage`) to unmap
  the cursor buffer, hiding the pointer across the entire display even during touch
  interactions or mouse movement.
- **Immediate First-Paint Stamping:** An inline script in `web/index.html` inspects
  `location.search` (`?pi=1`), `localStorage` (`pineda.platformPi`), or the User-Agent
  synchronously before HTML/CSS rendering starts, preventing any initial flicker of a
  cursor during cold boots.
- **Reference Kiosk Unit:** `packaging/pineda-kiosk.service` seeds this explicitly via
  `http://<hostname>.local:8090/?pi=1`.
- **Compositor Blank Theme (Optional Safeguard):** In the rare event that an attached
  hardware driver causes Cage to display a default pointer before Chromium initializes,
  Cage respects standard Xcursor themes. Setting a transparent cursor theme (e.g. in
  `~/.icons/default/index.theme`) ensures Wayland renders transparent pixels even on
  unhandled compositor layers.

Cards cost CPU too, and one card can dominate. Measured on airplaypi (Pi 4,
2 GB, also running Antigua's audio satellite) on 2026-09-23:

| Kiosk card stack | Chromium CPU (steady state) | 1-min load avg |
|---|---|---|
| All cards, incl. radar + video | ~52% of one core | up to ~6.7 |
| Radar + video removed | ~16% of one core | ~0.8 |
| Radar back as a still image + storm tracks, no `--disable-dev-shm-usage` | ~21% of one core | ~0.8 |
| Current stack, 2026-10-14 (kiosk up 1 h 47 m) | ~10% of one core | ~0.3 |

Memory on the same sample (PSS, so shared pages count once): Chromium + cage
≈ 620 MB of the Pi's 1.8 GB, ~150 MB of it the dashboard's renderer; 940 MB
available, 67 MB of swap in use, no swapping in or out. The page's own JS is
~235 kB uncompressed, a rounding error next to that, which is why the bundle
budget is a tripwire rather than a target (CONTRIBUTING.md). Measure memory
with `awk '/^Pss:/' /proc/<pid>/smaps_rollup` over the same PIDs; repeat a day
after a kiosk restart to see whether the renderer grows.

- **Radar** was ~70% of the kiosk's CPU on its own: it steps a frame every
  130 ms with a 160 ms opacity cross-fade, so it never goes idle, and every
  frame is a tile mosaic laid out at 300% of the card. It's **off the kiosk**
  (0023). It has since been rebuilt as a still image with NEXRAD storm-track
  arrows and no loop (DECISIONS 0024).
- **Video** (YouTube) already cost ~nothing on a Pi — `allowOnPi: false`
  keeps it from ever mounting there — but it's out of every stack for now.
  The card's code stays in the repo.

The kiosk is device `3f862842aee4086a` and has its **own `card_stack`
override**, so `PATCH /api/profiles/default` does not change what it shows —
`PATCH /api/devices/3f862842aee4086a` does. Confirm with a screenshot.

To measure a change: diff `utime+stime` (fields 14+15 of `/proc/<pid>/stat`)
summed over the `chromium`/`cage` PIDs across 90–120 s. That's long enough to
cover a full card-rotation cycle, and it doesn't add a second browser.

Diagnosing load on the device itself: `cat /proc/loadavg` is a *smoothed*
metric (~1-minute decay) — it lags a recent burst of activity (a restart, a
redeploy, your own SSH commands) by a couple of minutes, so check `ps aux
--sort=-%cpu` for the instantaneous picture rather than trusting a
still-elevated load average right after doing something. See "Debugging on
the kiosk device" above for the #1 way to *add* CPU load while investigating.

## Resilience

- The client caches the last-good view model in `localStorage` and the app shell
  in a service worker — a screen keeps showing the last state through a server
  restart or a wifi drop, and the SSE stream reconnects on its own.
- Cards carry a **stale** badge when their data is old and a designed **empty**
  state when there's nothing yet; a provider failure greys a card in the picker,
  it never blanks the screen.
- Pull the server's power mid-use: when it's back, every screen reconnects and
  repopulates with no interaction.

## Keeping it on the LAN

pinedaview is a LAN appliance. It must be reachable from the LAN (and wg0),
able to fetch its data from the internet, and **never reachable from outside
the LAN**. No tunnel ingress, port-forward or reverse proxy may point at it.
Most of the API has no auth (see [SECURITY.md](../SECURITY.md)), so a public
route hands out photos, the calendar, the config backup and write access.

`pinedaview-guard.service` enforces this with its own nftables table,
`inet pinedaview_guard` (`/etc/pinedaview/guard.nft`, from
`packaging/pinedaview-guard.nft`). The .deb/.rpm installs and enables it.

- **Inbound:** `:8090` accepts loopback, `wg0` and private source addresses
  (10/8, 172.16/12, 192.168/16, fe80::/10, fc00::/7). Anything else, such as a
  router port-forward or a public IPv6 address, is dropped and logged with the
  prefix `pinedaview-guard:`.
- **Tunnels:** a tunnel reaches the app over loopback, the same way the kiosk
  and Antigua do, so the inbound rule can't tell them apart. The guard
  rejects connections to `:8090` from any process in a tunnel unit's cgroup
  instead. A drop-in (`packaging/cloudflared-pinedaview-guard.conf` →
  `/etc/systemd/system/cloudflared.service.d/pinedaview-guard.conf`) has
  systemd add cloudflared's cgroup to the `@tunnel_units` set each time it
  starts. Whatever the tunnel's ingress says, a request for the dashboard
  gets a 502. Add the same drop-in to any other tunnel or proxy unit
  (ngrok, a Tailscale Funnel proxy, nginx with a public listener).
- **Outbound:** fetching weather, news, calendars and so on is unaffected.
  Only the output rule for tunnel cgroups names `:8090`.
- **Docker:** published container ports go through DNAT and the forward
  chain, not `input`, so the guard doesn't cover the Docker install. Publish
  on the LAN address only (`-p <lan-ip>:8090:8090`) and keep tunnels off it.

Check it:

```sh
sudo nft list table inet pinedaview_guard           # rules, counters, tunnel cgroups
journalctl -k | grep pinedaview-guard               # blocked non-LAN hits
# a process in a tunnel's cgroup must get 000, your shell 200:
sudo systemd-run --quiet -p NFTSet=cgroup:inet:pinedaview_guard:tunnel_units \
    --wait --pipe curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/api/health
```

A server installed from a wheel or package built before the guard existed
doesn't have it. Copy the three `packaging/` files into place by hand
(`guard.nft` → `/etc/pinedaview/`, the `.service` →
`/etc/systemd/system/`, the cloudflared drop-in →
`/etc/systemd/system/cloudflared.service.d/pinedaview-guard.conf`), then
`systemctl daemon-reload && systemctl enable --now pinedaview-guard`.

If the port isn't 8090, change it in `guard.nft` and run
`systemctl reload pinedaview-guard`. A reload empties `@tunnel_units`, and
the unit re-adds a running cloudflared. Restart any other tunnel unit after a
reload.

## Running the server on a different box than the kiosk

The server and the screen don't have to be the same machine — see
[INSTALL.md](INSTALL.md), "One server renders the dashboard; every screen is
just a browser pointed at it." This is worth doing when the kiosk device is
resource-constrained (a Raspberry Pi also running AirPlay/shairport-sync and
other appliance duties) and a bigger always-on box is available on the same
LAN: install `pinedaview` there instead, point the kiosk's Chromium URL at
it, and the Pi goes back to only running the kiosk browser and whatever
device-local services it needs.

To move an existing install:

1. Install `pinedaview` on the new host (any method from INSTALL.md).
2. Stop the server on the kiosk device, then copy its state directory
   (photos, `pineda.db`, `secrets.key`/`secrets.enc`, `card_settings.json`,
   `affirmation_history.json`) to the new host's state dir, owned by
   whichever account runs the service there.
3. Point `[mqtt].host` in the new host's config at the kiosk device's IP if
   an MQTT broker (e.g. for Now-playing) still lives there — nothing about
   moving the *server* moves the broker or shairport-sync.
4. Update the kiosk unit ([`pineda-kiosk.service`](../packaging/pineda-kiosk.service))
   to point `ExecStart`'s Chromium URL, and `ExecStartPre`'s health-check
   curl, at the new host's LAN address instead of `localhost`/its own IP.
   Drop `After=`/`Wants=pinedaview.service` from `[Unit]` — there's no local
   unit to order against anymore.
5. Stop and disable `pinedaview.service` on the kiosk device:
   `sudo systemctl disable --now pinedaview.service`, then confirm with
   `systemctl is-enabled pinedaview.service` (expect `disabled`). **This step
   is easy to do the migration without and forget** — the kiosk works fine
   either way since its Chromium never points at the local instance, so
   nothing visibly breaks. The leftover process just sits there polling
   every provider (weather, radar, commute, …) into a store nobody reads,
   burning CPU/RAM/network calls for nothing on the box you moved the server
   *off of* to relieve. Don't rely on remembering to check for it later —
   do this step as part of the same migration, not as a follow-up.

Use a static LAN IP or a hostname both boxes can already resolve for every
cross-host reference — don't assume mDNS (`*.local`) works between them; test
`ping <name>.local` from each side first.

### Verifying which host you're actually redeploying

Once split-host, "the server" is not necessarily the box you're SSH'd into —
a kiosk device can keep an old, disabled-but-still-installed local
`pinedaview` around (see step 5 above) that responds on `localhost:8090` and
looks exactly like a working server if you don't check further. Before
rebuilding/redeploying, confirm which host the kiosk's Chromium is actually
pointed at — don't assume it's the box you're already on:

```bash
ssh <kiosk-host> 'ps aux | grep -- "-- /usr/lib/chromium\|-- /usr/bin/chromium"'
# the URL in that ExecStart / process argv is the real target
```

Rebuilding and reinstalling on the wrong host produces no error at all — the
service restarts cleanly, health checks stay green, and the kiosk simply
never shows the change. After deploying, always verify the *served* asset
hash changed before touching the kiosk:

```bash
curl -s http://<server-host>:8090/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.\(js\|css\)'
```

### Turning the kiosk's screen

The kiosk's direction (wide, tall, or either flipped over) is kept on the
kiosk itself, in `~/.config/pinedaview/rotation` (or `~/.config/pineda/rotation`), and set with
`PUT /api/control/rotation` (the phone menu's Turned row, or the voice
assistant's `screen_turn` MCP tool). It needs two pieces on the kiosk:

```bash
sudo install -m 755 packaging/pinedaview-control-wrapper.sh /usr/local/bin/pinedaview-control-wrapper.sh
sudo install -m 755 packaging/pinedaview-kiosk-launch.sh /usr/local/bin/pinedaview-kiosk-launch
```

and `pinedaview-kiosk-launch` ahead of Chromium in the unit's (or its drop-in's)
`ExecStart`: `cage -- /usr/local/bin/pinedaview-kiosk-launch /usr/lib/chromium/chromium ...`.
cage resets the output on every start; the launcher puts the saved
direction back with `wlr-randr` before the browser opens.

When a Pi kiosk changes between wide and tall it fades out and reloads, so
the Photo Clock and the cards lay out afresh. A turn within the same shape
(a flip) needs no reload.

On a Raspberry Pi 4 the display hardware can only flip 180°, so a 90° turn
is done by the GPU on every frame. Measured 2026-10-26 on a Pi 4 driving a
2048×1280 panel (Photo Clock, 3 min each, rAF timing over Chromium's
DevTools port):

| Setup | Photo swipe | Still |
|---|---|---|
| Wide, liquid glass | ~39 fps, 17% slow frames | 60 fps |
| Tall, liquid glass | ~32 fps, 52% slow frames | 60 fps |
| Tall, flat glass | ~31 fps | 60 fps |
| Tall, fade instead of swipe | ~21 fps | 60 fps |
| Tall, only the new photo sliding (tried, reverted) | ~29 fps | 60 fps |

So the gap is the turn itself, not the glass or how many layers move.

To measure again: add `--remote-debugging-port=9222` to Chromium in the
kiosk's `ExecStart` (it listens on the kiosk's 127.0.0.1 only), reach it
with `ssh -L 9223:127.0.0.1:9222 <kiosk>`, attach with Playwright's
`connect_over_cdp`, and record `requestAnimationFrame` gaps plus
`longtask` entries. Take the flag out again afterwards. Restart the kiosk
once and let it come up before restarting again: a Chromium still shutting
down can hold `systemctl restart` for the full 90 s stop timeout, with the
screen black throughout.

### Clearing the kiosk's cache after a web-client deploy

A new `web/dist` build needs the kiosk's Chromium to actually fetch it.
Two *separate* caches can each independently keep serving the old bundle,
and clearing only one of them looks like the deploy silently didn't work:

```bash
ssh <kiosk-host> '
  sudo systemctl stop pineda-kiosk.service
  rm -rf ~/.config/chromium/Default/"Service Worker" \
         ~/.cache/chromium/Default/Cache \
         ~/.cache/chromium/Default/"Code Cache"
  sudo systemctl start pineda-kiosk.service
'
```

**With failover (two upstreams in the kiosk's nginx), wait for the primary
first.** Restarting `pinedaview` on the primary makes nginx mark it down for
`fail_timeout` (10 s) and send everything to the backup. A kiosk that reloads
in that window gets the *backup's* bundle, which may be older, and its service
worker then keeps serving that bundle across further restarts. The data and
SSE stream come from the primary again, so the screen looks live but lacks
the new UI. Before clearing the kiosk's caches, wait until the kiosk sees the
primary's bundle:

```bash
want=$(curl -s http://<primary>:8090/ | grep -o 'assets/index-[^"]*js')
ssh <kiosk-host> "until curl -s 127.0.0.1:8090/ | grep -q '$want'; do sleep 2; done"
```

- `~/.config/chromium/Default/Service Worker` — the PWA's service worker
  (vite-pwa `generateSW`) and its Cache Storage precache. This is the one
  most people remember.
- `~/.cache/chromium/Default/Cache` (note: `.cache`, not `.config`) — plain
  HTTP disk cache, unrelated to the service worker. `index.html` isn't
  content-hashed like `assets/*.js`/`*.css` are, so a stale cached response
  for `/` here can keep pointing the browser at yesterday's hashed bundle
  even with an empty service-worker cache and a **fully restarted Chromium
  process** — a plain `systemctl restart` does not touch it, because it
  lives on disk, not in the process. Missing this is the single most common
  reason a verified-working fix "isn't showing up" on the kiosk.

### Split-host control

The kiosk's QR-menu **Restart display** / **Restart Raspberry Pi** buttons
(`POST /api/control/restart-display`, `POST /api/control/restart-system`,
implemented in `core/src/pinedaview/control.py`) must always act on the
*kiosk device*, never on whatever machine happens to be running
`pinedaview`. With the single-host setup they're the same box, so a plain
local `systemctl restart`/`systemctl reboot` (via the polkit rule in
`packaging/pineda-restart.rules`) is correct. Once the server moves
elsewhere, those same local commands would restart/reboot the *server's*
host instead — the `[control]` config section redirects them over SSH to
the real kiosk device instead:

```toml
[control]
host = "192.0.2.161"        # the kiosk device's LAN IP (or a hostname
                                # this host can resolve — see the mDNS note
                                # above; don't rely on an ssh_config alias,
                                # the service account won't have one)
user = \"pineda\"                 # an account on the kiosk device authorized
                                # by its polkit rule for these two actions
ssh_key = "/var/lib/pinedaview/control_ed25519"  # dedicated key, restricted
                                                  # on the kiosk side — see below
```

Leaving `[control]` unset (the default) keeps the original local-systemctl
behavior — nothing to change for a single-host install.

`pin = "123456"` under `[control]` makes the phone menu ask for those digits
before either restart, so a guest who scanned the QR can't reboot the screen
unannounced. The server checks it (`X-Control-Pin`), and five wrong tries in
a row lock restarts for a minute. It never leaves the server, but treat it as a
speed bump, not a secret.

Setting this up needs a dedicated SSH keypair, generated on the server host
and restricted on the kiosk device to *only* the two exact commands the
buttons issue — never a general-purpose login key:

```bash
# On the server host, as (or for) the account running pinedaview:
ssh-keygen -t ed25519 -N "" -f /var/lib/pinedaview/control_ed25519

# On the kiosk device, install a forced-command wrapper:
sudo install -m 755 packaging/pineda-control-wrapper.sh \
  /usr/local/bin/pineda-control-wrapper.sh

# ...and authorize the new public key restricted to that wrapper, e.g. in
# ~/.ssh/authorized_keys for the [control].user account on the kiosk device:
command="/usr/local/bin/pineda-control-wrapper.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty ssh-ed25519 AAAA...
```

The wrapper (`packaging/pineda-control-wrapper.sh`) pattern-matches
`$SSH_ORIGINAL_COMMAND` against exactly `systemctl restart --no-block
pineda-kiosk.service` and `systemctl reboot --no-block`, rejecting anything
else — so even a fully compromised server process can only ever queue those
two actions on the kiosk device, nothing more. The kiosk device's existing
polkit rule (`packaging/pineda-restart.rules`) still does the actual
privilege escalation from `[control].user` to systemd/logind; the SSH
wrapper just gets the request there from a different host.

A service account with `ProtectHome=true` (the packaged `.deb`'s `pineda`
user) has no readable `$HOME`, so `ssh` needs everything spelled out rather
than falling back to `~/.ssh/*`: `control.py` invokes it with `-F /dev/null`
and an explicit `UserKnownHostsFile` next to the key
(`<ssh_key's directory>/known_hosts`) — seed that file once with
`ssh-keyscan -H <kiosk-ip> >> /var/lib/pinedaview/known_hosts`.

## Standby server

A split-host kiosk depends on one server box. To survive that box going down,
run a second pinedaview as a warm standby and let the kiosk fail over between
them, the same pattern Antigua uses for its voice server.

- **Standby**: install pinedaview on the second box as usual, seed its state
  dir from the primary (step 2 of the move above), and set
  `[api] adopt_unknown_devices = true`. The kiosk paired with the primary, so
  without this flag the standby answers 404 for its device id.
- **Kiosk**: `scripts/install-kiosk-failover.sh user@kiosk <device-id>` sets
  up nginx on `127.0.0.1:8090`, installs `pineda-failover.sh`, and points
  Chromium at the local proxy with `?device=<id>` pinned in the URL. That way
  it's the same screen, with its own card stack, on either server. The
  watchdog polls the primary's `/api/health` every 5 s. After 2 misses it
  switches to the standby (only if the standby is healthy). After 3 hits it
  switches back. A switch reloads nginx, which cuts the SSE stream, and the
  client reconnects to the new server without a page reload. Check which
  server is live with `journalctl -u pineda-failover`.
- **Standby mode**: on the standby, also set `[standby] primary =
  "http://<primary>:8090"`. While the primary is healthy, `/menu`, `/upload`
  and `/layout` redirect there and `/api/menu-url` names it, so phones always
  change the box whose state is kept. The photo card re-asks for the menu
  address every minute, so after a failover its QR code names whichever
  server is serving. Anything saved on the standby touches
  `standby-changed` in its state dir.
- **Sync**: `scripts/sync-standby.sh`, run on the primary every minute by
  `packaging/pineda-standby-sync.{service,timer}` (install notes in the
  unit). While the primary is up it pushes everything in the state dir
  (photos with `.cache/metadata.json` and the display copies, custom themes,
  card settings, layouts, wallpaper, keys, the database) and restarts the
  standby's pinedaview when anything that matters changed, because the
  standby loads most of it at startup. If the standby has `standby-changed`,
  it pulls the standby's state back first and restarts the primary's
  pinedaview, so changes made during an outage carry over. A pull that would
  delete more than 25 files here is refused and logged. It also copies
  Antigua's camera snapshots (`PINEDA_CAMS_DIR`). Logs:
  `journalctl -u pineda-standby-sync`.
- **Alarms** live in Antigua. Set `[antigua] url` to this box's Antigua and
  `fallback_url` to the other box's: the fallback answers only while it's
  standing in for the primary, and hands its alarms (and memories and lists,
  if they changed) back when the primary returns. Whichever Antigua is in
  charge sends the alarm list to both pinedaviews, so the standby's screen
  shows them and takes over when one goes off.
- **Cameras**: the standby's `[cameras] go2rtc` should point at the
  primary's go2rtc. Live video works during a failover only while that box
  is still up (HA pushes the streams there), and new snapshots stop while
  the primary's Antigua is down.
- The **indoor-climate** card reads `ac-data-server` on the primary's box, so
  it goes stale during a failover. Every other provider polls the internet
  directly and keeps working.
