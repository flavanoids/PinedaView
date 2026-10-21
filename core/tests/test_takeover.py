# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from pinedaview.broadcast import Broadcaster
from pinedaview.runtime import Runtime
from pinedaview.takeover import IngredientGroup, RecipeTakeover, TakeoverService

_CARD = {
    "title": "Piña Coladas",
    "source": "Food Network",
    "servings": "makes 2 drinks",
    "ingredients": [{"items": ["1 1/2 cups ice", "2 ounces pineapple juice"]}],
    "steps": ["Blend until smooth.", "Pour into 2 glasses."],
}


async def _pair(client: httpx.AsyncClient) -> str:
    device_id: str = (await client.post("/api/devices/pair", json={"name": "Kiosk"})).json()["id"]
    return device_id


async def test_show_lands_in_the_view_and_clears(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    assert (await client.get(f"/api/view/{device_id}")).json()["takeover"] is None

    shown = await client.put("/api/takeover", json={"card": _CARD, "seconds": 120})
    assert shown.status_code == 200
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["takeover"]["card"]["title"] == "Piña Coladas"
    assert view["takeover"]["card"]["kind"] == "recipe"
    assert (await client.get("/api/takeover")).json()["card"]["steps"][1] == "Pour into 2 glasses."

    assert (await client.delete("/api/takeover")).status_code == 204
    assert (await client.get(f"/api/view/{device_id}")).json()["takeover"] is None
    assert (await client.delete("/api/takeover")).status_code == 204  # idempotent


async def test_update_moves_the_highlight_but_never_reshows(client: httpx.AsyncClient) -> None:
    assert (await client.patch("/api/takeover", json={"current_step": 1})).json() is None
    shown = (await client.put("/api/takeover", json={"card": _CARD, "seconds": 120})).json()
    assert shown["card"]["current_step"] is None
    moved = (await client.patch("/api/takeover", json={"current_step": 1})).json()
    assert moved["card"]["current_step"] == 1
    assert moved["expires_at"] == shown["expires_at"]  # no extra time
    assert (await client.patch("/api/takeover", json={"current_step": -1})).status_code == 422
    await client.delete("/api/takeover")
    assert (await client.patch("/api/takeover", json={"current_step": 0})).json() is None
    assert (await client.get("/api/takeover")).json() is None


async def test_update_changes_only_what_it_sends(client: httpx.AsyncClient) -> None:
    card = {**_CARD, "current_step": 0, "skipped": [1]}
    await client.put("/api/takeover", json={"card": card, "seconds": 120})
    moved = (
        await client.patch(
            "/api/takeover",
            json={
                "stage": "steps",
                "current_ingredients": [0, 1],
                "swaps": [{"index": 0, "use": "crushed ice"}],
            },
        )
    ).json()["card"]
    assert moved["current_step"] == 0  # not sent, kept
    assert moved["skipped"] == [1]
    assert moved["stage"] == "steps"
    assert moved["current_ingredients"] == [0, 1]
    assert moved["swaps"] == [{"index": 0, "use": "crushed ice"}]
    stepped = (await client.patch("/api/takeover", json={"current_step": 1})).json()["card"]
    assert stepped["current_ingredients"] == [0, 1]  # a step alone leaves the highlight
    cleared = (
        await client.patch(
            "/api/takeover",
            json={
                "current_step": None,
                "current_ingredients": None,
            },
        )
    ).json()["card"]
    assert cleared["current_step"] is None
    assert cleared["current_ingredients"] == []
    assert (await client.patch("/api/takeover", json={"checked": [-1]})).status_code == 422
    assert (await client.patch("/api/takeover", json={"stage": "dessert"})).status_code == 422
    await client.delete("/api/takeover")


async def test_a_howto_card_carries_its_caution(client: httpx.AsyncClient) -> None:
    card = {**_CARD, "kind": "howto", "caution": "Heads up: this involves a ladder."}
    shown = (await client.put("/api/takeover", json={"card": card, "seconds": 60})).json()
    assert shown["card"]["kind"] == "howto"
    assert shown["card"]["caution"] == "Heads up: this involves a ladder."
    assert (
        await client.put("/api/takeover", json={"card": {**_CARD, "kind": "poem"}})
    ).status_code == 422
    await client.delete("/api/takeover")


async def test_bad_durations_are_refused(client: httpx.AsyncClient) -> None:
    for seconds in (0, -5, 99999):
        resp = await client.put("/api/takeover", json={"card": _CARD, "seconds": seconds})
        assert resp.status_code == 422


def _card() -> RecipeTakeover:
    return RecipeTakeover(
        title="Tea", ingredients=[IngredientGroup(items=["tea"])], steps=["Steep."]
    )


def test_expires_and_broadcasts() -> None:
    bus = Broadcaster()
    svc = TakeoverService(bus)
    with bus.subscription() as queue:
        shown = svc.show(_card(), 120)
        assert svc.current() is shown
        assert queue.get_nowait() == {"type": "takeover", "action": "show"}
        # Past its time it's gone at once, even before the tick clears it.
        later = shown.expires_at + timedelta(seconds=1)
        assert svc.current(later) is None
        svc._expire(later)
        assert queue.get_nowait() == {"type": "takeover", "action": "clear"}
        assert svc.current() is None


def test_a_new_one_replaces_the_old() -> None:
    svc = TakeoverService(Broadcaster())
    svc.show(_card(), 120)
    newer = svc.show(_card().model_copy(update={"title": "Coffee"}), 30)
    assert svc.current() is newer
    assert newer.expires_at - datetime.now(UTC) <= timedelta(seconds=30)


_CAMERA = {
    "kind": "camera",
    "camera": "front_door",
    "title": "Front door",
    "caption": "Identifying…",
}


async def test_a_camera_card_names_who_it_is(client: httpx.AsyncClient, runtime: Runtime) -> None:
    assert (await client.put("/api/takeover", json={"card": _CAMERA})).status_code == 422
    runtime.settings.cameras.streams["front_door"] = "T8210P00203706DA"
    shown = (await client.put("/api/takeover", json={"card": _CAMERA, "seconds": 45})).json()
    assert shown["card"]["kind"] == "camera"
    named = (await client.patch("/api/takeover", json={"caption": "Maria Pineda"})).json()
    assert named["card"]["caption"] == "Maria Pineda"
    assert named["card"]["title"] == "Front door"  # not sent, kept
    stepped = (await client.patch("/api/takeover", json={"current_step": 2})).json()
    assert "current_step" not in stepped["card"]  # a recipe's field, ignored
    assert stepped["card"]["caption"] == "Maria Pineda"
    await client.delete("/api/takeover")


async def test_camera_video_plays_only_while_its_card_is_up(
    client: httpx.AsyncClient, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime.settings.cameras.streams["front_door"] = "T8210P00203706DA"
    asked: list[str] = []

    def go2rtc(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(
            200, content=b"\x00\x00\x00\x18ftypmp42", headers={"content-type": "video/mp4"}
        )

    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(go2rtc), **kw)
    )

    url = "/api/cameras/front_door/stream.mp4"
    assert (await client.get(url)).status_code == 404  # nothing up
    await client.put("/api/takeover", json={"card": _CARD})
    assert (await client.get(url)).status_code == 404  # a recipe, not this camera
    await client.put("/api/takeover", json={"card": _CAMERA})
    assert (await client.get("/api/cameras/garage/stream.mp4")).status_code == 404
    video = await client.get(url)
    assert video.status_code == 200
    assert video.headers["content-type"] == "video/mp4"
    assert video.content.endswith(b"ftypmp42")
    assert asked == ["http://127.0.0.1:1984/api/stream.mp4?src=T8210P00203706DA"]
    await client.delete("/api/takeover")
    assert (await client.get(url)).status_code == 404


async def test_image_search_takeover_and_highlight(client: httpx.AsyncClient) -> None:
    card = {
        "kind": "image_search",
        "query": "strawberries",
        "images": [
            {"id": "A", "url": "https://example.com/a.jpg", "title": "Strawberry A"},
            {"id": "B", "url": "https://example.com/b.jpg", "title": "Strawberry B"},
        ],
    }
    shown = await client.put("/api/takeover", json={"card": card, "seconds": 120})
    assert shown.status_code == 200
    data = shown.json()
    assert data["card"]["kind"] == "image_search"
    assert data["card"]["query"] == "strawberries"
    assert len(data["card"]["images"]) == 2
    assert data["card"]["highlight"] is None

    # Highlight "B"
    patched = await client.patch("/api/takeover", json={"highlight": "B"})
    assert patched.status_code == 200
    assert patched.json()["card"]["highlight"] == "B"

    # Recipe fields sent to image search card are ignored
    stepped = await client.patch("/api/takeover", json={"current_step": 3})
    assert stepped.json()["card"]["highlight"] == "B"
    assert "current_step" not in stepped.json()["card"]

    await client.delete("/api/takeover")
