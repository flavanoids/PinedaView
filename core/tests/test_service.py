# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from pinedaview import service
from pinedaview.config import Settings


async def test_run_api_builds_the_app_and_serves(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[object] = []

    class FakeServer:
        def __init__(self, config: object) -> None:
            served.append(config)

        async def serve(self) -> None:
            served.append("served")

    monkeypatch.setattr("pinedaview.service.uvicorn.Server", FakeServer)
    await service.run_api(Settings())
    assert served[-1] == "served"
