# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from pinedaview.config import Settings
from pinedaview.registry import Device, Profile
from pinedaview.state import DisplayState
from pinedaview.stores import StoreRegistry
from pinedaview.view import build_view_model


def _alternate(device: Device) -> bool:
    vm = build_view_model(
        device=device,
        profile=Profile(id="p", name="p"),
        settings=Settings(),
        stores=StoreRegistry(),
        state=DisplayState.IDLE,
    )
    return vm.alternate


def test_alternate_is_off_until_switched_on() -> None:
    def device(**fields: object) -> Device:
        return Device(id="d", name="d", profile_id="p", paired_at=datetime.now(UTC), **fields)

    assert _alternate(device()) is False
    assert _alternate(device(alternate=True)) is True


async def test_alternate_round_trips_through_a_patch(client: httpx.AsyncClient) -> None:
    pair = await client.post("/api/devices/pair", json={"name": "Kitchen"})
    url = f"/api/devices/{pair.json()['id']}"
    assert (await client.patch(url, json={"alternate": True})).json()["alternate"] is True
    assert (await client.patch(url, json={"alternate": False})).json()["alternate"] is False
