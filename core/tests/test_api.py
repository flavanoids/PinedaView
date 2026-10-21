# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import json

import httpx

from pinedaview.runtime import Runtime


async def _pair(client: httpx.AsyncClient, name: str = "Kitchen") -> str:
    resp = await client.post("/api/devices/pair", json={"name": name})
    assert resp.status_code == 201
    device_id: str = resp.json()["id"]
    return device_id


async def test_health(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/health")).json()
    assert body["status"] == "ok"
    assert body["version"] == "v0"
    assert "weather" not in body["providers"]  # test runtime has no providers


async def test_view_unknown_device_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/view/nope")).status_code == 404


async def test_standby_adopts_a_failed_over_screen(
    client: httpx.AsyncClient, runtime: Runtime
) -> None:
    runtime.settings.api.adopt_unknown_devices = True
    assert (await client.get("/api/view/3f862842aee4086a")).status_code == 200
    ids = [d["id"] for d in (await client.get("/api/devices")).json()]
    assert ids == ["3f862842aee4086a"]
    # Only ids a server could have issued — not arbitrary strings.
    assert (await client.get("/api/view/nope")).status_code == 404


async def test_view_model_shape(client: httpx.AsyncClient, runtime: Runtime) -> None:
    runtime.stores.get_or_create("moon", stale_after_s=100).publish({"phase": 0.5})
    device_id = await _pair(client)

    vm = (await client.get(f"/api/view/{device_id}")).json()
    assert vm["version"] == "v0"
    assert vm["device_id"] == device_id
    assert vm["state"] == "idle"
    assert vm["hero"]["kind"] == "card"
    # The runtime resolves each card's needs at startup, so the default stack
    # comes back minus the cards this test gives nothing to show: no photos
    # (photo) and no MQTT feed (now-playing).
    assert {c["id"] for c in vm["cards"]} | {vm["hero"]["card"]} == {
        "clock",
        "weather",
        "radar",
        "affirmation",
        "traffic",
        "home-cams",
    }


async def test_config_round_trip(client: httpx.AsyncClient) -> None:
    before = (await client.get("/api/config")).json()
    assert before["units"] == "imperial"

    after = (await client.post("/api/config", json={"units": "metric", "theme": "ocean"})).json()
    assert after["units"] == "metric"
    assert after["theme"] == "ocean"
    assert (await client.get("/api/config")).json()["theme"] == "ocean"


async def test_theme_apply_rejects_unknown(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/themes/apply", json={"name": "warm"})).status_code == 200
    assert (await client.post("/api/themes/apply", json={"name": "nope"})).status_code == 400


async def test_control_state_and_view_reflects_it(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    assert (await client.post("/api/control/state", json={"playing": True})).status_code == 204
    assert (await client.get(f"/api/view/{device_id}")).json()["state"] == "playing"


async def test_device_patch(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    resp = await client.patch(f"/api/devices/{device_id}", json={"name": "Bedside"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Bedside"
    assert (await client.patch("/api/devices/ghost", json={"name": "x"})).status_code == 404
    assert (await client.delete(f"/api/devices/{device_id}")).status_code == 204
    assert (await client.delete("/api/devices/ghost")).status_code == 404


async def test_timers(client: httpx.AsyncClient) -> None:
    created = (await client.post("/api/timers", json={"seconds": 60, "label": "Tea"})).json()
    assert created["label"] == "Tea"
    assert len((await client.get("/api/timers")).json()) == 1
    assert (await client.delete(f"/api/timers/{created['id']}")).status_code == 204
    assert (await client.delete("/api/timers/gone")).status_code == 404


async def test_stream_endpoint_rejects_unknown_device(client: httpx.AsyncClient) -> None:
    async with client.stream("GET", "/api/stream/ghost") as response:
        assert response.status_code == 404


async def test_stream_generator_emits_snapshot_then_delta(runtime: Runtime) -> None:
    from pinedaview.api import _stream

    await runtime.devices.init()
    device = await runtime.devices.pair_device("Kitchen")

    gen = _stream(runtime, device.id)
    try:
        snapshot = _parse_event(await anext(gen))
        assert snapshot["event"] == "view"
        assert snapshot["id"] == "0"

        runtime.broadcaster.publish({"type": "config", "reason": "test"})
        await runtime.devices.update_device(device.id, brightness=0.5)
        runtime.broadcaster.publish({"type": "config", "reason": "test"})
        # The first push changed nothing, so the next event is the second one.
        delta = _parse_event(await asyncio.wait_for(anext(gen), timeout=1.0))
        assert delta["event"] == "view"
        assert delta["id"] == "1"
        assert json.loads(delta["data"])["brightness"] == 0.5
    finally:
        await gen.aclose()


async def test_stream_generator_turns_a_deleted_device_into_a_new_screen(
    runtime: Runtime,
) -> None:
    from pinedaview.api import _stream

    await runtime.devices.init()
    device = await runtime.devices.pair_device("Kitchen", kept=True)
    gen = _stream(runtime, device.id)
    try:
        await anext(gen)
        assert await runtime.devices.delete_device(device.id) is True
        runtime.broadcaster.publish({"type": "config"})
        # Its browser still holds the id: it's "New screen!" again, not stuck.
        again = _parse_event(await asyncio.wait_for(anext(gen), timeout=1.0))
        assert again["event"] == "view"
        assert json.loads(again["data"])["welcome"] is True
    finally:
        await gen.aclose()


def _parse_event(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith(":") or not line:
            continue
        key, _, value = line.partition(": ")
        fields[key] = value
    return fields
