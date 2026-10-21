# SPDX-License-Identifier: Apache-2.0
"""Standalone bridge: shairport-sync's metadata pipe → MQTT ``.../track``.

Runs as its own OS process (its own systemd unit, alongside shairport-sync)
rather than inside the API server — it just tails a local FIFO and republishes
a couple of derived fields, so it has no business sharing the server's
lifecycle. It only ever ADDS ``duration_s`` / ``started_at`` to the
``nowPlaying`` store: title/artist/album/genre and the playing/paused/cleared
state already arrive over shairport-sync's own ``publish_parsed`` MQTT topics
(see ``mqtt.py``), which this process never touches.

Why not just read those same values off MQTT? shairport-sync's own MQTT
publisher (``publish_parsed``) never carries song duration or playback
position — that data only exists on the metadata pipe, as the ``ssnc``/``prgr``
item (three RTP frame counts, sample rate 44100 Hz: start/current/end of the
current play sequence).

Pipe wire format (from shairport-sync's metadata/pipe.c): each item is

    <item><type>HEX</type><code>HEX</code><length>N</length>
    <data encoding="base64">
    ...base64...
    </data></item>

with the ``<data>`` block omitted when N is 0. ``type``/``code`` are the
big-endian uint32 of a 4-character tag (``core``, ``ssnc``, ``asal``, ``prgr``,
…) printed as bare hex, no ``0x`` prefix and no zero-padding.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import paho.mqtt.client as mqtt

from pinedaview import __version__
from pinedaview.config import MqttConfig, load_settings
from pinedaview.logging_config import configure_logging
from pinedaview.system import local_stats

logger = logging.getLogger(__name__)

STATS_EVERY_S = 60

_SAMPLE_RATE = 44100.0

# Item framing: non-greedy so back-to-back items in one read() don't merge.
_ITEM_RE = re.compile(
    r"<item>\s*<type>([0-9a-fA-F]+)</type>\s*<code>([0-9a-fA-F]+)</code>"
    r"\s*<length>(\d+)</length>\s*"
    r'(?:<data encoding="base64">\s*(.*?)\s*</data>)?\s*</item>\s*',
    re.DOTALL,
)


def _tag(hex_value: str) -> str:
    """The 4-char ASCII tag a hex-encoded uint32 like 'ssnc' decodes to."""
    n = int(hex_value, 16)
    return n.to_bytes(4, "big").decode("ascii", "replace")


@dataclass
class ParsedItem:
    kind: str  # 4-char type, e.g. "core" / "ssnc"
    code: str  # 4-char code, e.g. "asal" / "prgr"
    data: bytes


def iter_items(buf: str) -> tuple[list[ParsedItem], str]:
    """Pull every complete ``<item>`` out of `buf`; return them plus the
    unconsumed remainder (a partial item straddling two pipe reads)."""
    items: list[ParsedItem] = []
    end = 0
    for m in _ITEM_RE.finditer(buf):
        end = m.end()
        raw_b64 = m.group(4)
        data = base64.b64decode(raw_b64) if raw_b64 else b""
        items.append(ParsedItem(_tag(m.group(1)), _tag(m.group(2)), data))
    return items, buf[end:]


@dataclass
class TrackState:
    """What we've derived from the pipe since the last play session began."""

    duration_s: float | None = None
    started_at: str | None = None  # ISO 8601, UTC

    def reset(self) -> None:
        self.duration_s = None
        self.started_at = None


def apply_item(
    item: ParsedItem, state: TrackState, *, now: float | None = None
) -> dict[str, float | str] | None:
    """Fold one parsed item into `state`; return a payload to publish, if any.

    `now` is injectable (epoch seconds) so tests don't depend on wall time.
    """
    if item.kind == "ssnc" and item.code == "pend":
        state.reset()
        return None  # shairport's own play_end (native MQTT) clears the card
    if item.kind == "ssnc" and item.code in ("pfls", "pbeg"):
        # Paused, or a new session about to start — drop the stale anchor so a
        # resume without a fresh `prgr` doesn't keep counting from the old one.
        state.duration_s = None
        state.started_at = None
        return None
    if item.kind == "ssnc" and item.code == "prgr":
        text = item.data.decode("ascii", "replace").strip()
        parts = text.split("/")
        if len(parts) != 3:
            return None
        try:
            start, current, end = (int(p) for p in parts)
        except ValueError:
            return None
        if end <= start:
            return None
        duration_s = (end - start) / _SAMPLE_RATE
        elapsed_s = max(0.0, min(duration_s, (current - start) / _SAMPLE_RATE))
        started_at = datetime.fromtimestamp((now or time.time()) - elapsed_s, tz=UTC)
        state.duration_s = duration_s
        state.started_at = started_at.isoformat(timespec="seconds")
        return {"duration_s": round(duration_s, 1), "started_at": state.started_at}
    return None


class PipeTailer:
    """Reopens the FIFO on EOF — the writer (shairport-sync) closing its end
    between sessions is normal, not an error to give up on."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def lines(self) -> AsyncIterator[dict[str, float | str]]:
        state = TrackState()
        buf = ""
        while True:
            try:
                fd = await asyncio.to_thread(open, self._path, encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.warning("cannot open metadata pipe %s: %s", self._path, exc)
                await asyncio.sleep(2)
                continue
            try:
                while True:
                    chunk = await asyncio.to_thread(fd.read, 4096)
                    if not chunk:  # writer closed its end
                        break
                    buf += chunk
                    items, buf = iter_items(buf)
                    for it in items:
                        payload = apply_item(it, state)
                        if payload is not None:
                            yield payload
            finally:
                fd.close()


class TrackPublisher:
    """Thin fire-and-forget MQTT publisher — no subscribe, no retry state
    beyond what paho already does internally."""

    def __init__(self, cfg: MqttConfig) -> None:
        self._cfg = cfg
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        base = cfg.topics[0].rstrip("/#") if cfg.topics else "airplaypi"
        self._topic = f"{base}/track"
        self._stats_topic = f"{base}/stats"

    def connect(self) -> None:
        self._client.connect(self._cfg.host, self._cfg.port, 30)
        self._client.loop_start()

    def publish(self, payload: dict[str, float | str]) -> None:
        self._client.publish(self._topic, json.dumps(payload), qos=0, retain=False)

    def publish_stats(self) -> None:
        # Retained, so the server has the latest the moment it (re)connects.
        payload = local_stats().model_dump_json()
        self._client.publish(self._stats_topic, payload, qos=0, retain=True)

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()


async def run(cfg: MqttConfig, pipe_path: Path) -> None:
    publisher = TrackPublisher(cfg)
    publisher.connect()
    logger.info("airplay bridge: %s → %s:%d", pipe_path, cfg.host, cfg.port)
    stats = asyncio.create_task(_stats_loop(publisher))
    try:
        async for payload in PipeTailer(pipe_path).lines():
            publisher.publish(payload)
    finally:
        stats.cancel()
        publisher.stop()


async def _stats_loop(publisher: TrackPublisher) -> None:
    """The Pi's load, memory and disk for the menu's Device page, once a
    minute — a few /proc reads, nothing the Pi will notice."""
    while True:
        try:
            publisher.publish_stats()
        except Exception:
            logger.exception("stats publish failed")
        await asyncio.sleep(STATS_EVERY_S)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pineda-airplay-bridge",
        description="Tail shairport-sync's metadata pipe and publish duration/position to MQTT.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, metavar="PATH", help="path to a TOML config file")
    parser.add_argument(
        "--pipe",
        type=Path,
        default=Path("/tmp/shairport-sync-metadata"),
        help="shairport-sync metadata pipe path",
    )
    args = parser.parse_args(argv)

    settings = load_settings(args.config)
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    if not settings.mqtt.enabled:
        logger.error("mqtt is disabled in config — nothing to publish to")
        return 2

    try:
        asyncio.run(run(settings.mqtt, args.pipe))
    except KeyboardInterrupt:  # pragma: no cover
        logger.info("interrupted")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
