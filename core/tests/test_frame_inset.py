# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import httpx


async def test_frame_inset_reaches_the_view_and_is_bounded(client: httpx.AsyncClient) -> None:
    device_id = str((await client.post("/api/devices/pair", json={"name": "Frame"})).json()["id"])
    url = f"/api/devices/{device_id}"
    assert (await client.get(f"/api/view/{device_id}")).json()["frame_inset"] == 0
    assert (await client.patch(url, json={"frame_inset": 10})).status_code == 200
    assert (await client.get(f"/api/view/{device_id}")).json()["frame_inset"] == 10
    assert (await client.patch(url, json={"frame_inset": 21})).status_code == 422
    assert (await client.patch(url, json={"frame_inset": 0})).status_code == 200
    assert (await client.get(f"/api/view/{device_id}")).json()["frame_inset"] == 0
