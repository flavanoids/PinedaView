# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pinedaview.config import MqttConfig
from pinedaview.mqtt import MqttBridge, _decode_image, _track_json
from pinedaview.runtime import build_runtime
from pinedaview.secrets import SecretStore
from pinedaview.stores import StoreRegistry

# ── encrypted secret store ───────────────────────────────────────────────────


def test_secrets_are_encrypted_on_disk(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    store.set("google_maps", "AIza-super-secret")

    blob = (tmp_path / "secrets.enc").read_bytes()
    assert b"AIza-super-secret" not in blob  # not plaintext
    assert (tmp_path / "secrets.key").exists()

    # a fresh instance with the same keyfile reads it back
    assert SecretStore(tmp_path).get("google_maps") == "AIza-super-secret"


def test_secret_names_only_no_values(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    store.set("a", "1")
    store.set("b", "2")
    assert store.names() == ["a", "b"]
    assert store.delete("a") is True
    assert store.names() == ["b"]


def test_corrupt_secrets_file_is_survivable(tmp_path: Path) -> None:
    (tmp_path / "secrets.enc").write_bytes(b"not fernet")
    assert SecretStore(tmp_path).names() == []


# ── mqtt bridge (message handling only — no broker) ──────────────────────────


def test_track_fields_filters_to_known_keys() -> None:
    raw = {"title": "T", "artist": "A", "junk": 1, "position_s": 5}
    assert _track_json(raw) == {"title": "T", "artist": "A", "position_s": 5}


def test_mqtt_maps_shairport_parsed_fields_and_cover() -> None:
    stores = StoreRegistry()
    bridge = MqttBridge(MqttConfig(enabled=True), stores)

    bridge._handle("airplaypi/artist", "Miles Davis")
    bridge._handle("airplaypi/album", "Kind of Blue")
    bridge._handle("airplaypi/title", "So What")
    bridge._handle("airplaypi/genre", "--")  # placeholder → not stored
    bridge._handle("airplaypi/client_name", "Living Room Speaker")
    bridge._handle_cover(b"\xff\xd8\xff" + b"\x00" * 500)

    value = _now_playing(stores)
    assert value["artist"] == "Miles Davis"
    assert value["album"] == "Kind of Blue"
    assert value["title"] == "So What"
    assert "genre" not in value
    assert value["source"] == "Living Room Speaker"
    assert value["coverRev"] == 1
    cover = bridge.cover()
    assert cover is not None and cover.startswith(b"\xff\xd8\xff")

    bridge._handle("airplaypi/play_end", "")
    assert bridge.cover() is None
    assert "source" not in _now_playing(stores)  # a new cast names itself afresh


def test_mqtt_playing_topic_sets_pause_state() -> None:
    stores = StoreRegistry()
    playing: list[bool] = []
    bridge = MqttBridge(MqttConfig(enabled=True), stores, on_playing=playing.append)

    bridge._handle("airplaypi/title", "Song")
    bridge._handle("airplaypi/playing", "1")
    assert _now_playing(stores)["playing"] is True
    bridge._handle("airplaypi/playing", "0")
    assert _now_playing(stores)["playing"] is False
    assert playing == [True, False]


def test_pause_keeps_the_track_but_stop_clears_it() -> None:
    stores = StoreRegistry()
    bridge = MqttBridge(MqttConfig(enabled=True), stores)
    bridge._handle("airplaypi/title", "So What")
    bridge._handle("airplaypi/play_flush", "")  # pause
    assert _now_playing(stores) == {"title": "So What", "playing": False}
    bridge._handle("airplaypi/play_end", "")  # session over
    assert _now_playing(stores) == {"playing": False}


def test_connect_re_resolves_cards() -> None:
    stores = StoreRegistry()
    calls: list[int] = []
    bridge = MqttBridge(MqttConfig(enabled=True), stores, on_ready=lambda: calls.append(1))
    bridge._notify_ready()
    assert calls == [1]


class _ReasonCode:
    def __init__(self, is_failure: bool) -> None:
        self.is_failure = is_failure


class _SubscribingClient:
    def __init__(self) -> None:
        self.subscribed: list[str] = []

    def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)


def test_on_connect_marks_connected_on_a_successful_reason_code() -> None:
    stores = StoreRegistry()
    bridge = MqttBridge(MqttConfig(enabled=True), stores)
    client = _SubscribingClient()
    bridge._on_connect(client, None, None, _ReasonCode(is_failure=False))
    assert bridge.connected is True
    assert client.subscribed == ["airplaypi/#"]


def test_on_connect_stays_disconnected_on_a_rejected_reason_code() -> None:
    """A broker that refuses the CONNECT (bad credentials, not authorized, a
    banned client id) still invokes ``on_connect`` — this is what stops that
    from being misreported as a live connection."""
    stores = StoreRegistry()
    bridge = MqttBridge(MqttConfig(enabled=True), stores)
    client = _SubscribingClient()
    bridge._on_connect(client, None, None, _ReasonCode(is_failure=True))
    assert bridge.connected is False
    assert client.subscribed == []


def test_retained_session_events_are_ignored() -> None:
    stores = StoreRegistry()
    bridge = MqttBridge(MqttConfig(enabled=True), stores)

    class _Msg:
        def __init__(self, topic: str, payload: bytes, retain: bool) -> None:
            self.topic, self.payload, self.retain = topic, payload, retain

    bridge._loop = None  # _bounce is a no-op without a loop; call handlers inline
    bridge._handle("airplaypi/title", "Live Track")
    # a stale retained "play_end" must not wipe the live track
    bridge._on_message(None, None, _Msg("airplaypi/play_end", b"--", retain=True))
    assert _now_playing(stores)["title"] == "Live Track"


def test_retained_playing_topic_is_ignored() -> None:
    # A broker holds "playing"/"active" retained too, not just the session
    # events — every MQTT reconnect (e.g. a server restart) replays it, and
    # without this check it resurrects a days-old track as "now playing"
    # with a fresh timestamp.
    stores = StoreRegistry()
    bridge = MqttBridge(MqttConfig(enabled=True), stores)

    class _Msg:
        def __init__(self, topic: str, payload: bytes, retain: bool) -> None:
            self.topic, self.payload, self.retain = topic, payload, retain

    bridge._loop = None
    bridge._on_message(None, None, _Msg("airplaypi/playing", b"1", retain=True))
    # skipped before ever touching the store — it was never even created
    assert stores.get("nowPlaying") is None


def test_decode_image_passes_raw_and_unwraps_base64() -> None:
    import base64

    jpeg = b"\xff\xd8\xff" + b"abc"
    assert _decode_image(jpeg) == jpeg
    assert _decode_image(base64.b64encode(jpeg)) == jpeg


def _now_playing(stores: StoreRegistry) -> dict[str, object]:
    store = stores.get("nowPlaying")
    assert store is not None
    snap = store.snapshot()
    assert snap is not None
    return dict(snap.value)


def test_mqtt_handle_maps_track_and_playstate() -> None:
    stores = StoreRegistry()
    playing: list[bool] = []
    bridge = MqttBridge(MqttConfig(enabled=True), stores, on_playing=playing.append)

    bridge._handle("airplaypi/track", json.dumps({"title": "Song", "artist": "Band"}))
    bridge._handle("airplaypi/play_start", "")
    bridge._handle("airplaypi/track/progress", json.dumps({"position_s": 42, "playing": True}))

    value = _now_playing(stores)
    assert value["title"] == "Song"
    assert value["position_s"] == 42
    assert value["playing"] is True
    assert playing == [True, True]

    bridge._handle("airplaypi/play_end", "")
    assert _now_playing(stores)["playing"] is False
    assert playing[-1] is False


# ── external ingest + write token ───────────────────────────────────────────


async def test_ingest_publishes_to_a_store(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/ingest/commute", json={"routes": [{"label": "Work", "minutes": 21}]}
    )
    assert resp.status_code == 202
    stores = (await client.get("/api/debug/stores")).json()["stores"]
    assert stores["commute"]["value"]["routes"][0]["minutes"] == 21


async def test_ingest_rejects_a_bad_store_name(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/ingest/../etc", json={})).status_code in (400, 404, 405)


async def test_write_token_gates_writes(tmp_path: Path) -> None:
    from asgi_lifespan import LifespanManager

    from pinedaview.api import create_app
    from pinedaview.config import load_settings

    settings = load_settings(
        overrides={
            "state_dir": str(tmp_path),
            "api": {"db_path": str(tmp_path / "d.db"), "write_token": "sekret"},
            "config_file": str(tmp_path / "config.toml"),
        }
    )
    app = create_app(build_runtime(settings, providers=[]))
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            assert (await c.get("/api/health")).status_code == 200  # reads are open
            assert (await c.post("/api/devices/pair", json={"name": "x"})).status_code == 401
            ok = await c.post(
                "/api/devices/pair", json={"name": "x"}, headers={"Authorization": "Bearer sekret"}
            )
            assert ok.status_code == 201


# ── commute card readiness via a secret ─────────────────────────────────────


async def test_commute_provider_starts_when_key_added(tmp_path: Path) -> None:
    # "commute" ships in Settings.disabled_cards by default (config.py) — it
    # polls the billed Google Directions API. Opt it back in explicitly to
    # exercise the secret-gating behaviour underneath that default.
    from asgi_lifespan import LifespanManager

    from pinedaview.api import create_app
    from pinedaview.config import load_settings

    settings = load_settings(
        overrides={
            "state_dir": str(tmp_path),
            "photos_dir": str(tmp_path / "photos"),
            "location": {"query": "Houston"},
            "api": {"db_path": str(tmp_path / "pineda.db")},
            "config_file": str(tmp_path / "config.toml"),
            "disabled_cards": [],
        }
    )
    runtime = build_runtime(settings, providers=[])
    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cards = {c["id"]: c for c in (await client.get("/api/cards")).json()}
            assert cards["commute"]["status"] == "blocked"

            await client.put("/api/secrets/google_maps", json={"value": "k"})
            cards = {c["id"]: c for c in (await client.get("/api/cards")).json()}
            assert cards["commute"]["status"] == "ready"


def test_now_playing_card_needs_mqtt() -> None:
    from pinedaview.cards.loader import load_manifests

    manifest = load_manifests()["now-playing"]
    assert manifest.needs == ["mqtt:airplaypi/track"]


@pytest.mark.parametrize("enabled", [False, True])
def test_runtime_builds_mqtt_only_when_enabled(tmp_path: Path, enabled: bool) -> None:
    from pinedaview.config import load_settings

    settings = load_settings(
        overrides={
            "state_dir": str(tmp_path),
            "api": {"db_path": str(tmp_path / "d.db")},
            "mqtt": {"enabled": enabled},
        }
    )
    runtime = build_runtime(settings, providers=[])
    assert (runtime.mqtt is not None) is enabled


async def test_cover_endpoint_serves_the_bridge_bytes(tmp_path: Path) -> None:
    from asgi_lifespan import LifespanManager

    from pinedaview.api import create_app
    from pinedaview.config import load_settings

    settings = load_settings(
        overrides={
            "state_dir": str(tmp_path),
            "photos_dir": str(tmp_path / "photos"),
            "api": {"db_path": str(tmp_path / "d.db")},
            "config_file": str(tmp_path / "config.toml"),
            "mqtt": {"enabled": True},
        }
    )
    runtime = build_runtime(settings, providers=[])
    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            assert (await http.get("/api/nowplaying/cover")).status_code == 404
            assert runtime.mqtt is not None
            runtime.mqtt._cover = b"\xff\xd8\xff" + b"\x00" * 200
            res = await http.get("/api/nowplaying/cover")
            assert res.status_code == 200
            assert res.headers["content-type"] == "image/jpeg"


def test_antigua_loading_shows_until_airplay_starts() -> None:
    # Antigua reports finding → starting while Apple Music and AirPlay spin up;
    # the card takes the screen for it, and the real session start ends it.
    stores = StoreRegistry()
    playing: list[bool] = []
    bridge = MqttBridge(MqttConfig(enabled=True), stores, on_playing=playing.append)
    bridge._loop = None
    bridge._handle("airplaypi/title", "Old Song")
    bridge._handle(
        "airplaypi/loading", '{"stage": "finding", "text": "Looking up \\u201chalo\\u201d"}'
    )
    first = _now_playing(stores)["loading"]
    assert isinstance(first, dict) and first["stage"] == "finding" and playing[-1] is True
    bridge._handle(
        "airplaypi/loading", '{"stage": "starting", "title": "Halo", "artist": "Beyonce"}'
    )
    loading = _now_playing(stores)["loading"]
    assert isinstance(loading, dict)
    assert loading["title"] == "Halo" and loading["since"] == first["since"]
    # the old session ending (MA replacing it) keeps the panel up
    bridge._handle("airplaypi/play_end", "--")
    assert "loading" in _now_playing(stores) and playing[-1] is True
    bridge._handle("airplaypi/play_start", "--")
    assert "loading" not in _now_playing(stores) and playing[-1] is True


def test_antigua_loading_done_without_airplay_goes_back_to_idle() -> None:
    stores = StoreRegistry()
    playing: list[bool] = []
    bridge = MqttBridge(MqttConfig(enabled=True), stores, on_playing=playing.append)
    bridge._loop = None
    bridge._handle("airplaypi/loading", '{"stage": "starting", "title": "Halo"}')
    bridge._handle("airplaypi/loading", '{"stage": "failed", "text": "Apple Music is slow"}')
    loading = _now_playing(stores)["loading"]
    assert isinstance(loading, dict) and loading["text"] == "Apple Music is slow"
    bridge._handle("airplaypi/loading", '{"stage": "done"}')
    assert "loading" not in _now_playing(stores) and playing[-1] is False
