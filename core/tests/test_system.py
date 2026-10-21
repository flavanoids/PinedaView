# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from pinedaview.config import MqttConfig
from pinedaview.mqtt import MqttBridge
from pinedaview.runtime import Runtime
from pinedaview.stores import StoreRegistry
from pinedaview.system import local_stats


def test_local_stats_reads_this_machine(tmp_path: Path) -> None:
    s = local_stats(tmp_path)
    assert s.cores >= 1 and s.load1 >= 0
    assert 0 < s.disk_free_gb <= s.disk_total_gb


def test_bridge_keeps_the_screens_stats() -> None:
    bridge = MqttBridge(MqttConfig(enabled=True), StoreRegistry())

    class _Msg:
        def __init__(self, topic: str, payload: bytes) -> None:
            self.topic, self.payload, self.retain = topic, payload, True

    bridge._on_message(None, None, _Msg("airplaypi/stats", b"not json"))
    assert bridge.screen_stats is None
    payload = local_stats().model_dump_json().encode()
    bridge._on_message(None, None, _Msg("airplaypi/stats", payload))
    assert bridge.screen_stats is not None and bridge.screen_stats.cores >= 1


async def test_system_endpoint(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/system")).json()
    assert body["server"]["cores"] >= 1
    assert body["screen"] is None


async def test_screen_reports_its_look(client: httpx.AsyncClient) -> None:
    device_id = (await client.post("/api/devices/pair", json={"name": "Kiosk"})).json()["id"]
    shown = (await client.get("/api/now-showing", params={"device_id": device_id})).json()
    assert shown["look"] is None
    look = {"device_id": device_id, "clock_face": "contour", "pi": True, "scale": 1.65}
    assert (await client.post("/api/now-showing/look", json=look)).status_code == 204
    shown = (await client.get("/api/now-showing", params={"device_id": device_id})).json()
    assert shown["look"] == {"clock_face": "contour", "pi": True, "scale": 1.65}


async def test_an_alarm_takes_over_when_it_goes_off(
    runtime: Runtime, client: httpx.AsyncClient
) -> None:
    r = await client.post("/api/timers", json={"seconds": 60, "label": "Wake up", "kind": "alarm"})
    assert r.json()["kind"] == "alarm"
    plain = await client.post("/api/timers", json={"seconds": 30, "label": "Pasta"})
    assert plain.json()["kind"] == "timer"

    runtime.timers._fire_due(datetime.now(UTC) + timedelta(seconds=40))
    assert (await client.get("/api/takeover")).json() is None  # a plain timer doesn't
    runtime.timers._fire_due(datetime.now(UTC) + timedelta(seconds=90))
    up = (await client.get("/api/takeover")).json()
    assert up["card"]["kind"] == "alarm" and up["card"]["label"] == "Wake up"
