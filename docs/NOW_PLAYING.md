<!-- SPDX-License-Identifier: Apache-2.0 -->
# Now Playing (AirPlay via shairport-sync)

The **Now playing** card shows the current AirPlay track — album art, title,
artist, album, year — and becomes the full-screen hero while music is playing.
It reads a read-only MQTT feed, so PinedaView can run on a different box
from the AirPlay receiver and just watch the same broker.

## 1. Point the server at the broker

`config.toml` (or `PINEDA_MQTT__*` env vars):

```toml
[mqtt]
enabled = true
host = "192.0.2.161"   # the machine running shairport-sync + an MQTT broker
port = 1883
topics = ["airplaypi/#"]  # the default; matches the shairport-sync topic below
```

Add the **Now playing** card to a screen in Settings → Cards & layout. It stays
greyed until the broker connects (`GET /api/health` → `checks.mqtt`).

On the Night / Photo Clock (no dashboard showing), the same feed drives a
small glass card in the bottom-right corner — art, title, artist — only
while a track is actually playing.

## 2. Turn on shairport-sync's MQTT publisher

In `shairport-sync.conf` on the AirPlay box:

```conf
metadata = {
    enabled = "yes";
    include_cover_art = "yes";   // required for album art
};

mqtt = {
    enabled = "yes";
    hostname = "127.0.0.1";
    port = 1883;
    topic = "airplaypi";         // → airplaypi/title, airplaypi/cover, …
    publish_parsed = "yes";      // title / artist / album / genre / year
    publish_cover = "yes";       // the album art JPEG on airplaypi/cover
};
```

Restart shairport-sync. That's it — the card fills in within a second of the
next track change.

## What the bridge understands

| Topic | Used for |
|---|---|
| `…/title` `…/artist` `…/album` `…/genre` `…/year` (or `song*` variants) | the text |
| `…/client_name` | the casting device ("Living Room Speaker") shown above the title — only sent when the source names itself |
| `…/cover` (raw JPEG/PNG, or base64) | album art — held in memory, served at `GET /api/nowplaying/cover` |
| `…/playing` `…/active` (`0` / `1`) | play / pause state (authoritative within a session) |
| `…/play_start` `…/play_resume` | switches to the Now-playing hero |
| `…/play_flush` | paused — keeps the track visible, drops the hero |
| `…/play_end` | session over — clears the card and the art entirely (title, artist, cover — everything), so a stopped cast never lingers on screen |
| `…/track` (JSON `{title, artist, album, duration_s, position_s, started_at, playing}`) | a combined feed from a custom bridge — optional; enables the progress bar |
| `…/loading` (JSON `{stage, title?, artist?, text?}`, stage `finding` → `starting` → `done` \| `failed` \| `cancel`) | Antigua getting something ready for this speaker: the card shows a loading panel (easing % bar, seconds waited, a friendlier line the longer it takes) until the AirPlay session starts, `done` arrives, or 2 minutes pass; `failed` shows its `text` for 10 s |

**Retained play-state messages are ignored** — not just `play_*`, but the
plain `playing`/`active` topics too. A broker typically retains *every*
shairport-sync topic (confirm with `mosquitto_sub -t 'airplaypi/#' -v
--retained-only`), and every MQTT reconnect (which includes every
`pinedaview` restart) gets them replayed as if they'd just happened. If
`playing`/`active` weren't skipped too, a days-old `playing=1` from the last
real session would resurrect that old track as "now playing" — with a
*fresh* timestamp, so it wouldn't even show as stale — on every single
server restart. (This actually happened; see `mqtt.py`'s
`_PLAY_STATE_TOPICS` retain check and its regression test
`test_retained_playing_topic_is_ignored`.) The retained **parsed fields**
(title/artist/album/…) and cover art are still kept, so the card shows the
last known track after a restart — just correctly labelled "Paused" rather
than claiming it's live, since `NowPlaying.svelte` only treats an explicit
`playing: true` as playing (not merely "not `false`").

`play_start`/`play_end`/`play_flush`/`play_resume` are shairport-sync's own
parsed MQTT topics — they fire the instant a session begins, ends, or pauses,
independent of the bridge below, so play/pause state and the "Nothing playing"
reset are already as fast as the AirPlay session itself.

## Just the text, no art?

Album art needs `publish_cover = "yes"` in the shairport-sync `mqtt {}` block —
it defaults to `"no"` because the binary JPEGs add load to the broker. With it
off you still get title / artist / album / genre; the card just has no cover.

## Song duration and a progress bar

shairport-sync's own parsed MQTT never carries song duration or playback
position — that data only exists on its **metadata pipe** (`metadata.pipe_name`
in `shairport-sync.conf`), as the `ssnc`/`prgr` item (three RTP timestamps:
start/current/end of the play sequence, at 44100 samples/sec).

`pineda-airplay-bridge` (installed alongside `pinedaview` — same wheel, its
own console script) tails that pipe and republishes just the derived fields to
`…/track`: `duration_s`, plus `started_at` (an ISO wall-clock timestamp anchor,
computed once per `prgr` event) rather than a raw `position_s` that would need
resending every second. The client counts up from `started_at` locally on its
own clock — the same "server sends a target, client ticks it" split the
Countdown/Timer cards already use — so the progress bar advances smoothly
without a stream of position updates. It never touches title/artist/playing —
those already arrive over shairport-sync's own topics above.

Run it as its own systemd unit next to `shairport-sync` and `pinedaview`
(see `packaging/pineda-airplay-bridge.service`):

```
pineda-airplay-bridge --config /path/to/config.toml
```

It reads the same `[mqtt]` config block as the server (to know which broker
and topic prefix to publish to) and defaults to
`/tmp/shairport-sync-metadata` for the pipe path (override with `--pipe`).
