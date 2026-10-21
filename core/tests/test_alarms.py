# SPDX-License-Identifier: Apache-2.0
"""Alarms and reminders: kept by Antigua, set from the phone, shown on screen."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from pinedaview.api import _on_screen
from pinedaview.runtime import Runtime


def _antigua(runtime: Runtime, seen: list[tuple[str, str, Any]]) -> None:
    """Point the runtime at a fake Antigua that records what it's asked."""
    rows = [
        {
            "id": "a1",
            "kind": "alarm",
            "label": "gym alarm for 6:30 AM",
            "name": "gym",
            "repeat": "weekdays",
            "hour": 6,
            "minute": 30,
            "fires_at": 1.0e9,
            "speak": True,
            "enabled": True,
        }
    ]

    def handle(req: httpx.Request) -> httpx.Response:
        body: dict[str, Any] = json.loads(req.content) if req.content else {}
        seen.append((req.method, req.url.path, body or None))
        if req.method == "GET":
            return httpx.Response(200, json={"alarms": rows})
        if req.method == "POST":
            if body["time"] == "08:00":
                return httpx.Response(400, json={"error": "that time has already passed"})
            return httpx.Response(201, json={**rows[0], "id": "b2", "kind": body["kind"]})
        if req.method == "PATCH":
            return httpx.Response(200, json={**rows[0], "enabled": body["enabled"]})
        if req.url.path.endswith("/gone"):
            return httpx.Response(404, json={"error": "gone"})
        return httpx.Response(200, json={"deleted": "a1"})

    runtime.settings.antigua.url = "http://antigua.test"
    runtime.http = httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def test_the_menu_reaches_antigua_s_alarms(
    runtime: Runtime, client: httpx.AsyncClient
) -> None:
    seen: list[tuple[str, str, Any]] = []
    _antigua(runtime, seen)

    listed = (await client.get("/api/alarms")).json()
    assert listed[0]["name"] == "gym" and listed[0]["enabled"] is True

    r = await client.post(
        "/api/alarms",
        json={
            "kind": "reminder",
            "time": "18:00",
            "date": "2026-10-11",
            "message": "call mom",
        },
    )
    assert r.status_code == 201 and r.json()["kind"] == "reminder"
    assert seen[-1] == (
        "POST",
        "/alarms",
        {
            "kind": "reminder",
            "time": "18:00",
            "date": "2026-10-11",
            "message": "call mom",
            "speak": True,
        },
    )

    late = await client.post("/api/alarms", json={"kind": "alarm", "time": "08:00"})
    assert late.status_code == 400 and late.json()["detail"] == "that time has already passed"

    off = await client.patch("/api/alarms/a1", json={"enabled": False})
    assert off.json()["enabled"] is False and seen[-1][:2] == ("PATCH", "/alarms/a1")

    assert (await client.delete("/api/alarms/a1")).status_code == 204
    assert (await client.delete("/api/alarms/gone")).status_code == 404


async def test_without_antigua_alarms_say_so(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/alarms")
    assert r.status_code == 503


@pytest.mark.parametrize(
    "bad", [{"kind": "alarm", "time": "7am"}, {"kind": "nap", "time": "07:00"}]
)
async def test_a_bad_alarm_never_reaches_antigua(
    runtime: Runtime, client: httpx.AsyncClient, bad: dict[str, str]
) -> None:
    seen: list[tuple[str, str, Any]] = []
    _antigua(runtime, seen)
    assert (await client.post("/api/alarms", json=bad)).status_code == 422
    assert seen == []


async def test_mirrored_reminders_take_over_and_far_alarms_stay_off_screen(
    runtime: Runtime, client: httpx.AsyncClient
) -> None:
    soon = datetime.now(UTC) + timedelta(minutes=5)
    r = await client.put(
        "/api/timers/sync/antigua",
        json={
            "timers": [
                {"id": "r1", "label": "call mom", "kind": "reminder", "fires_at": soon.isoformat()},
                {
                    "id": "a1",
                    "label": "gym",
                    "kind": "alarm",
                    "fires_at": (soon + timedelta(days=3)).isoformat(),
                },
                {"id": "t1", "label": "pasta", "fires_at": soon.isoformat()},
            ]
        },
    )
    assert r.status_code == 204

    shown = _on_screen(runtime.timers.list())
    assert sorted(t.kind for t in shown) == ["reminder", "timer"]  # gym is 3 days off

    runtime.timers._fire_due(soon + timedelta(seconds=1))
    up = (await client.get("/api/takeover")).json()
    assert up["card"]["kind"] == "alarm" and up["card"]["label"] == "Call mom"


async def test_turning_an_alarm_off_stops_the_speaker(
    runtime: Runtime, client: httpx.AsyncClient
) -> None:
    sent: list[tuple[str, dict[str, Any]]] = []

    class _Bridge:
        def publish(self, topic: str, payload: dict[str, Any]) -> bool:
            sent.append((topic, payload))
            return True

        async def stop(self) -> None:
            pass

    runtime.mqtt = _Bridge()  # type: ignore[assignment]
    await client.post("/api/timers", json={"seconds": 5, "label": "Wake up", "kind": "alarm"})
    runtime.timers._fire_due(datetime.now(UTC) + timedelta(seconds=10))
    assert (await client.delete("/api/takeover")).status_code == 204
    assert sent == [("antigua/alarm_stop", {})]

    assert (await client.delete("/api/takeover")).status_code == 204  # nothing up: quiet
    assert sent == [("antigua/alarm_stop", {})]


async def test_the_fallback_answers_when_the_primary_antigua_hands_off(
    runtime: Runtime, client: httpx.AsyncClient
) -> None:
    asked: list[str] = []

    def handle(req: httpx.Request) -> httpx.Response:
        asked.append(req.url.host)
        if req.url.host == "primary.test":
            return httpx.Response(503, json={"error": "down"})
        return httpx.Response(200, json={"alarms": []})

    runtime.settings.antigua.url = "http://primary.test"
    runtime.settings.antigua.fallback_url = "http://fallback.test"
    runtime.http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    assert (await client.get("/api/alarms")).json() == []
    assert asked == ["primary.test", "fallback.test"]
