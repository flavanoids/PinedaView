# SPDX-License-Identifier: Apache-2.0
"""Optional MQTT bridge.

Subscribes read-only to a broker (typically the one PinedaDisplay/shairport-sync
already publishes to) and maps ``airplaypi/*`` messages into the ``nowPlaying``
store. paho runs its own network thread; messages are bounced onto the event
loop before touching any store.

Understands three shapes of feed:

* a combined ``<topic>/track`` JSON blob (from a bridge), plus
  ``<topic>/track/progress``;
* shairport-sync's ``publish_parsed`` fields — ``<topic>/{title,artist,album,
  genre,…}`` — one value per message;
* shairport-sync's ``publish_cover`` — the raw JPEG of the album art on
  ``<topic>/cover``. It is held in memory and served by ``GET
  /api/nowplaying/cover``; the store carries a ``coverRev`` the client pins to.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt

from pinedaview.config import MqttConfig
from pinedaview.stores import StoreRegistry
from pinedaview.system import HostStats

logger = logging.getLogger(__name__)

_STORE = "nowPlaying"
_STALE_AFTER_S = 30.0
_EMPTY = {"", "--", "unknown"}

_COVER_SUFFIXES = {"cover", "coverart", "cover-art", "artwork"}
_SESSION_EVENTS = {"play_start", "play_end", "play_flush", "play_resume"}
_PLAY_STATE_TOPICS = _SESSION_EVENTS | {"playing", "active", "loading"}
# Antigua's "getting that ready" reports (``<topic>/loading``): how long one
# may sit unanswered before it's dropped, and how long a failure stays up.
_LOADING_TTL_S = 120.0
_FAILED_SHOW_S = 10.0
_LOADING_STAGES = {"finding", "starting"}
_PARSED_FIELDS = {
    "title": "title",
    "songtitle": "title",
    "artist": "artist",
    "songartist": "artist",
    "album": "album",
    "songalbum": "album",
    "genre": "genre",
    "songgenre": "genre",
    "year": "year",
    "songyear": "year",
    # The sending device's own name ("Living Room Speaker") — shairport-sync only
    # publishes it when the source supplies one, so a nameless cast simply
    # leaves the field off.
    "client_name": "source",
}
_TRACK_FIELDS = ("title", "artist", "album", "genre", "year", "source")


class MqttBridge:
    def __init__(
        self,
        cfg: MqttConfig,
        stores: StoreRegistry,
        *,
        on_playing: Callable[[bool], None] | None = None,
        on_ready: Callable[[], None] | None = None,
    ) -> None:
        self._cfg = cfg
        self._stores = stores
        self._on_playing = on_playing
        # Called (on the event loop) when the broker connects, so card readiness
        # can be re-resolved — the bridge connects well after startup.
        self.on_ready = on_ready
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: mqtt.Client | None = None
        self.connected = False
        self.last_error: str | None = None
        """Why the broker isn't connected — a failed TCP connect or a rejected
        CONNECT reason code — cleared on a successful connect. Surfaced at
        ``GET /api/health`` so a wrong password or a banned client id doesn't
        just look like "not connected yet"."""
        self._cover: bytes | None = None
        self._cover_rev = 0
        self.screen_stats: HostStats | None = None
        self._live = False
        """Whether the AirPlay session itself is playing — what the screen
        goes back to when a loading report ends without one starting."""
        self._loading_since: str | None = None
        self._loading_timer: asyncio.TimerHandle | None = None
        """The screen's Pi, as its bridge last reported (``<topic>/stats``)."""

    async def start(self) -> None:
        if not self._cfg.enabled:
            return
        self._loop = asyncio.get_running_loop()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        # reconnect_delay_set + connect_async hands retrying to paho's network
        # thread (loop_start, below) instead of a single blocking attempt here.
        # The broker (shairport-sync's Pi) routinely isn't reachable yet at our
        # own boot — a plain connect() that fails once left the bridge dead
        # for good until the whole service was restarted, silently dropping
        # now-playing (and, via Stage.svelte's trailing-span fill, stretching
        # whatever card ended up last in the grid).
        client.reconnect_delay_set(min_delay=1, max_delay=60)
        try:
            client.connect_async(self._cfg.host, self._cfg.port, 30)
        except OSError as exc:
            self.last_error = str(exc)
            logger.warning("mqtt connect failed (%s:%d): %s", self._cfg.host, self._cfg.port, exc)
            return
        client.loop_start()
        self._client = client
        logger.info("mqtt bridge → %s:%d", self._cfg.host, self._cfg.port)

    async def stop(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            with contextlib.suppress(Exception):
                self._client.disconnect()
            self._client = None
        self.connected = False

    def cover(self) -> bytes | None:
        """The album art for the current track, or None."""
        return self._cover

    # ── paho callbacks (network thread) ──────────────────────────────────────

    def _on_connect(
        self, client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, *_a: Any
    ) -> None:
        # A rejected CONNECT (bad credentials, not authorized, …) still invokes
        # this callback — checking the reason code, not just that we got here,
        # is what keeps a refused connection from reporting "connected".
        if getattr(reason_code, "is_failure", False):
            self.last_error = str(reason_code)
            logger.warning("mqtt connect rejected by broker: %s", reason_code)
            self.connected = False
            return
        self.last_error = None
        self.connected = True
        for topic in self._cfg.topics:
            client.subscribe(topic)
        self._bounce(self._notify_ready)

    def _on_disconnect(self, *_a: Any) -> None:
        self.connected = False

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
        suffix = msg.topic.rsplit("/", 1)[-1].lower()
        # A retained play-state message (session event, or a plain "playing"/
        # "active" topic) is stale — it's from the *last* time music played,
        # broker-held so a fresh subscriber (every MQTT reconnect, e.g. every
        # server restart) gets it replayed as if it just happened. Without
        # this, a retained `playing=1` from days ago resurrects an old track
        # as "now playing" on every reconnect, stamped with a fresh
        # timestamp that makes it look live.
        if msg.retain and suffix in _PLAY_STATE_TOPICS:
            return
        if suffix in _COVER_SUFFIXES:
            data = bytes(msg.payload)
            self._bounce(lambda: self._handle_cover(data))
            return
        payload = msg.payload.decode("utf-8", "replace")
        if suffix == "stats":
            with contextlib.suppress(ValueError):
                self.screen_stats = HostStats.model_validate_json(payload)
            return
        self._bounce(lambda: self._handle(msg.topic, payload))

    def _bounce(self, fn: Callable[[], None]) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(fn)

    # ── loop thread ──────────────────────────────────────────────────────────

    def _notify_ready(self) -> None:
        self._stores.notify(_STORE)
        if self.on_ready is not None:
            self.on_ready()

    def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        """Send one message to the broker (e.g. ``antigua/alarm_stop``);
        False when it isn't connected."""
        if self._client is None or not self.connected:
            return False
        self._client.publish(topic, json.dumps(payload))
        return True

    def _store(self) -> Any:
        return self._stores.get_or_create(_STORE, stale_after_s=_STALE_AFTER_S)

    def _current(self) -> dict[str, Any]:
        snap = self._store().snapshot()
        return dict(snap.value) if snap and isinstance(snap.value, dict) else {}

    def _publish(self, value: dict[str, Any]) -> None:
        self._store().publish(value)
        self._stores.notify(_STORE)

    def _handle_cover(self, data: bytes) -> None:
        data = _decode_image(data)
        if len(data) < 100:  # empty payload / placeholder
            return
        self._cover = data
        self._cover_rev += 1
        self._publish({**self._current(), "coverRev": self._cover_rev})

    def _handle(self, topic: str, payload: str) -> None:
        suffix = topic.rsplit("/", 1)[-1].lower()
        if suffix == "loading":
            self._handle_loading(payload)
        elif suffix in _PLAY_STATE_TOPICS:
            self._handle_play_state(suffix, payload)
        elif suffix in _PARSED_FIELDS:
            self._handle_parsed_field(_PARSED_FIELDS[suffix], payload)
        elif suffix in ("track", "progress"):
            self._handle_track_json(payload)

    def _handle_loading(self, payload: str) -> None:
        """Antigua starting something on this speaker: ``{stage, text?,
        title?, artist?}`` with stage finding → starting → done | failed.
        The card shows it as a loading panel until the music actually plays."""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return
        stage = data.get("stage") if isinstance(data, dict) else None
        if stage in _LOADING_STAGES:
            now = datetime.now(UTC).isoformat()
            self._loading_since = self._loading_since or now
            loading = {
                "stage": stage,
                "since": self._loading_since,  # the whole wait, for the elapsed text
                "stageAt": now,  # this stage, for the bar's easing
                **{k: str(data[k]) for k in ("text", "title", "artist") if data.get(k)},
            }
            self._set_playing(True)  # the Now Playing card takes the screen
            self._publish({**self._current(), "loading": loading})
            self._expire_loading(_LOADING_TTL_S)
        elif stage == "failed":
            loading = {"stage": "failed", "since": self._loading_since or "", "stageAt": ""}
            if data.get("text"):
                loading["text"] = str(data["text"])
            self._set_playing(True)
            self._publish({**self._current(), "loading": loading})
            self._expire_loading(_FAILED_SHOW_S)
        elif stage in ("done", "cancel"):
            self._clear_loading()

    def _expire_loading(self, after_s: float) -> None:
        if self._loading_timer is not None:
            self._loading_timer.cancel()
        self._loading_timer = (
            self._loop.call_later(after_s, self._clear_loading) if self._loop else None
        )

    def _clear_loading(self) -> None:
        if self._loading_timer is not None:
            self._loading_timer.cancel()
            self._loading_timer = None
        self._loading_since = None
        current = self._current()
        if "loading" not in current:
            return
        current.pop("loading")
        self._set_playing(self._live)
        self._publish(current)

    def _handle_play_state(self, suffix: str, payload: str) -> None:
        live = suffix in ("play_start", "play_resume") or (
            suffix in ("playing", "active") and payload.strip() in ("1", "true", "yes")
        )
        if suffix != "active":  # "active" stays 1 through a pause
            self._live = live
        if live:  # it's playing: whatever was loading has arrived
            self._loading_since = None
            if self._loading_timer is not None:
                self._loading_timer.cancel()
                self._loading_timer = None
        # A session ending while Antigua is still getting the next thing ready
        # (a replaced song ends the old one) keeps the loading panel up.
        loading = self._current().get("loading") if self._loading_since else None
        if suffix == "play_end":  # the session is over — clear the card
            self._set_playing(loading is not None)
            self._cover = None
            self._publish({"playing": False, **({"loading": loading} if loading else {})})
        elif suffix == "play_flush":  # paused — keep the track, just stop
            self._set_playing(loading is not None)
            self._publish({**self._current(), "playing": False})
        elif suffix in ("play_start", "play_resume"):
            self._set_playing(True)
            self._publish({**self._drop_loading(), "playing": True})
        else:  # a plain "playing" / "active" topic — value is "0" / "1"
            playing = payload.strip() in ("1", "true", "yes")
            self._set_playing(playing or loading is not None)
            if playing or suffix == "playing":
                current = self._drop_loading() if playing else self._current()
                self._publish({**current, "playing": playing})

    def _drop_loading(self) -> dict[str, Any]:
        current = self._current()
        current.pop("loading", None)
        return current

    def _handle_parsed_field(self, field: str, payload: str) -> None:
        value = payload.strip()
        merged = {**self._current()}
        if value and value.lower() not in _EMPTY:
            merged[field] = value
        else:
            merged.pop(field, None)
        self._publish(merged)

    def _handle_track_json(self, payload: str) -> None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return
        self._publish({**self._current(), **_track_json(data)})
        if "playing" in data:
            self._set_playing(bool(data["playing"]))

    def _set_playing(self, playing: bool) -> None:
        if self._on_playing is not None:
            self._on_playing(playing)


def _decode_image(data: bytes) -> bytes:
    """Some shairport-sync builds base64 the cover payload; most send raw bytes."""
    if data[:2] == b"\xff\xd8" or data[:8] == b"\x89PNG\r\n\x1a\n":
        return data
    with contextlib.suppress(binascii.Error, ValueError):
        return base64.b64decode(data, validate=True)
    return data


def _track_json(data: dict[str, Any]) -> dict[str, Any]:
    keep = (*_TRACK_FIELDS, "duration_s", "position_s", "started_at", "playing")
    return {k: data[k] for k in keep if k in data}
