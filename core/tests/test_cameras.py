# SPDX-License-Identifier: Apache-2.0
"""A battery camera streams only while its card is up (pinedaview.cameras)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from pinedaview.broadcast import Broadcaster
from pinedaview.cameras import CameraService
from pinedaview.config import CamerasConfig
from pinedaview.takeover import CameraTakeover, RecipeTakeover, TakeoverService


async def test_the_stream_follows_the_card(tmp_path: Path) -> None:
    (tmp_path / "ha.env").write_text("HA_TOKEN=secret\n")
    calls: list[tuple[str, str, str]] = []

    def ha(request: httpx.Request) -> httpx.Response:
        calls.append(
            (
                request.url.path.rsplit("/", 1)[1],
                json.loads(request.content)["entity_id"],
                request.headers["authorization"],
            )
        )
        return httpx.Response(200, json=[])

    cfg = CamerasConfig(
        streams={"front_door": "T8210", "garage": "T8170"},
        entities={"front_door": "camera.doorbell", "garage": "camera.garage"},
        ha_url="http://ha",
        ha_token_file=tmp_path / "ha.env",
    )
    takeover = TakeoverService(Broadcaster())
    async with httpx.AsyncClient(transport=httpx.MockTransport(ha)) as http:
        cams = CameraService(cfg, takeover, http)
        task = asyncio.create_task(cams.run())

        async def settle() -> None:
            for _ in range(20):
                await asyncio.sleep(0.01)

        takeover.show(RecipeTakeover(title="Soup", ingredients=[], steps=[]), 120)
        await settle()
        assert calls == []  # not a camera

        cams.show("front_door", 30)
        await asyncio.wait_for(cams.started("front_door"), 1)  # the video waits for it
        assert calls == [("start_p2p_livestream", "camera.doorbell", "Bearer secret")]
        assert cams.live == "front_door"

        cams.show("garage", 30)  # one camera replaces the other
        await settle()
        assert calls[1:] == [
            ("stop_p2p_livestream", "camera.doorbell", "Bearer secret"),
            ("start_p2p_livestream", "camera.garage", "Bearer secret"),
        ]

        assert takeover.release()  # the soup comes back; the garage stops
        await settle()
        assert calls[-1][:2] == ("stop_p2p_livestream", "camera.garage")
        assert cams.live is None
        up = takeover.current()
        assert up is not None and up.card.kind == "recipe"

        takeover.show(CameraTakeover(kind="camera", camera="front_door"), 30)  # via REST, say
        await settle()
        takeover.clear()
        await settle()
        assert [c[0] for c in calls[-2:]] == ["start_p2p_livestream", "stop_p2p_livestream"]

        # With a pip, both start together (one wake, not two in a row).
        del calls[:]
        cams.show("front_door", 30, pip="garage")
        await asyncio.wait_for(cams.started("front_door"), 1)
        await asyncio.wait_for(cams.started("garage"), 1)
        assert sorted(c[:2] for c in calls) == [
            ("start_p2p_livestream", "camera.doorbell"),
            ("start_p2p_livestream", "camera.garage"),
        ]
        assert cams.live == "front_door"
        task.cancel()


def test_without_home_assistant_it_leaves_streams_alone() -> None:
    takeover = TakeoverService(Broadcaster())
    cams = CameraService(CamerasConfig(streams={"front_door": "T"}), takeover, httpx.AsyncClient())
    assert not cams.drives_streams
    assert cams.status() == [
        {"name": "front_door", "title": "Front door", "battery": None, "showing": False}
    ]
