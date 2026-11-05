# SPDX-License-Identifier: Apache-2.0
"""The MCP server at /mcp (docs/MCP.md): stateless 2026-07-28 calls, the
token and scope gate, and the display and camera tools."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager

from pinedaview.api import create_app
from pinedaview.config import Settings, load_settings
from pinedaview.mcp_server import token_hash
from pinedaview.runtime import Runtime, build_runtime

TOKEN = "test-token-antigua"
READER = "test-token-reader"
ALL = ["display:read", "display:write", "system", "camera:view"]

_RECIPE = {
    "title": "Piña Coladas",
    "ingredients": [{"items": ["ice", "pineapple juice"]}],
    "steps": ["Blend.", "Pour.", "Serve."],
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings(
        overrides={
            "state_dir": tmp_path,
            "photos_dir": str(tmp_path / "photos"),
            "location": {"query": "Houston"},
            "api": {"db_path": str(tmp_path / "pineda.db")},
            "config_file": str(tmp_path / "config.toml"),
            "cameras": {
                "streams": {"front_door": "T8210", "garage": "T8170"},
                "titles": {"front_door": "Front door"},
            },
            "mcp": {
                "allowed_hosts": ["testserver"],
                "clients": {
                    "antigua": {"token_sha256": token_hash(TOKEN), "scopes": ALL},
                    "reader": {"token_sha256": token_hash(READER), "scopes": ["display:read"]},
                },
            },
        }
    )


@pytest_asyncio.fixture
async def runtime(settings: Settings) -> Runtime:
    return build_runtime(settings, providers=[])


@pytest_asyncio.fixture
async def client(runtime: Runtime) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c


_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
    "traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
}


async def rpc(
    c: httpx.AsyncClient,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    token: str | None = TOKEN,
    name: str | None = None,
) -> httpx.Response:
    headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": method,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if name:
        headers["Mcp-Name"] = name
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {**(params or {}), "_meta": _META},
    }
    return await c.post("/mcp/", headers=headers, json=body)


async def call(
    c: httpx.AsyncClient, tool: str, args: dict[str, Any] | None = None, **kw: Any
) -> dict[str, Any]:
    r = await rpc(c, "tools/call", {"name": tool, "arguments": args or {}}, name=tool, **kw)
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()["result"]
    return result


async def test_discover_and_list_need_only_a_token(client: httpx.AsyncClient) -> None:
    assert (await rpc(client, "server/discover", token=None)).status_code == 401
    assert (await rpc(client, "server/discover", token="wrong")).status_code == 401
    found = (await rpc(client, "server/discover")).json()["result"]
    assert "2026-07-28" in found["supportedVersions"]
    listed = (await rpc(client, "tools/list", token=READER)).json()["result"]
    names = [t["name"] for t in listed["tools"]]
    assert {"display_status", "theme_set", "camera_show", "takeover_update"} <= set(names)
    assert listed["ttlMs"] == 3_600_000
    show = next(t for t in listed["tools"] if t["name"] == "camera_show")
    assert show["inputSchema"]["properties"]["camera"]["enum"] == ["front_door", "garage"]
    assert show["_meta"]["io.pineda/llm"] is True


async def test_scopes_are_checked_before_the_call(client: httpx.AsyncClient) -> None:
    assert (await call(client, "display_status", token=READER))["isError"] is False
    r = await rpc(
        client,
        "tools/call",
        {"name": "theme_set", "arguments": {"name": "ocean"}},
        token=READER,
        name="theme_set",
    )
    assert r.status_code == 403
    # A header naming a tool the token may call can't smuggle in another.
    r = await rpc(
        client,
        "tools/call",
        {"name": "theme_set", "arguments": {"name": "ocean"}},
        token=READER,
        name="display_status",
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == -32020
    r = await rpc(client, "tools/call", {"name": "nope", "arguments": {}}, name="nope")
    assert r.status_code == 403  # unknown tools have no scope


async def test_theme_set_matches_what_was_said(client: httpx.AsyncClient) -> None:
    listed = (await call(client, "themes_list"))["structuredContent"]["result"]
    target = next(t for t in listed if t["name"] == "ocean")
    done = (await call(client, "theme_set", {"name": target["label"].lower()}))["structuredContent"]
    assert done == {"theme": "ocean", "label": target["label"], "changed": True}
    again = (await call(client, "theme_set", {"name": "ocean"}))["structuredContent"]
    assert again["changed"] is False
    assert (await call(client, "display_status"))["structuredContent"]["theme"] == "ocean"
    bad = await call(client, "theme_set", {"name": "plaid"})
    assert bad["isError"] is True
    assert bad["structuredContent"]["error"] == "unknown_theme"


async def test_takeover_tools(client: httpx.AsyncClient) -> None:
    shown = (await call(client, "takeover_show", {"card": _RECIPE, "seconds": 120}))[
        "structuredContent"
    ]
    assert shown["card"]["title"] == "Piña Coladas"
    moved = (await call(client, "takeover_update", {"change": {"current_step": 1}}))[
        "structuredContent"
    ]["result"]
    assert moved["card"]["current_step"] == 1
    status = (await call(client, "display_status"))["structuredContent"]
    assert status["takeover"]["kind"] == "recipe"
    assert (await call(client, "takeover_clear"))["structuredContent"] == {"was": "recipe"}
    assert (await call(client, "takeover_clear"))["structuredContent"] == {"was": None}


async def test_a_camera_covers_a_recipe_and_gives_it_back(
    client: httpx.AsyncClient, runtime: Runtime
) -> None:
    await call(client, "takeover_show", {"card": _RECIPE, "seconds": 120})
    await call(client, "takeover_update", {"change": {"current_step": 1}})
    cam = await call(client, "camera_show", {"camera": "front_door", "seconds": 30})
    assert cam["structuredContent"]["title"] == "Front door"
    assert cam["structuredContent"]["restores"] is True
    first = runtime.takeover.current()
    assert first is not None and first.card.kind == "camera"
    # Still reading along under the camera: the step follows.
    await call(client, "takeover_update", {"change": {"current_step": 2}})
    # Asked again: more time, same card (the screen doesn't replay the opening).
    await call(client, "camera_show", {"camera": "front_door", "seconds": 60})
    again = runtime.takeover.current()
    assert again is not None and again.shown_at == first.shown_at
    assert again.expires_at > first.expires_at
    assert (await call(client, "camera_stop"))["structuredContent"] == {"stopped": True}
    back = runtime.takeover.current()
    assert back is not None and back.card.kind == "recipe"
    assert back.card.current_step == 2
    assert 115 < (back.expires_at - back.shown_at).total_seconds() <= 120
    bad = await call(client, "camera_show", {"camera": "attic"})
    assert bad["isError"] is True


async def test_the_camera_ends_on_its_own(runtime: Runtime) -> None:
    from datetime import UTC, datetime, timedelta

    from pinedaview.takeover import CameraTakeover, RecipeTakeover

    t = runtime.takeover
    t.show(RecipeTakeover.model_validate(_RECIPE), 120)
    t.show(CameraTakeover(kind="camera", camera="front_door"), 30)
    t._expire(datetime.now(UTC) + timedelta(seconds=31))
    back = t.current()
    assert back is not None and back.card.kind == "recipe"
    t.clear()
    t.show(CameraTakeover(kind="camera", camera="front_door"), 30)
    t._expire(datetime.now(UTC) + timedelta(seconds=31))
    assert t.current() is None


async def test_display_tools_are_fast(client: httpx.AsyncClient) -> None:
    for _ in range(5):
        await call(client, "display_status")
    times = []
    for _ in range(50):
        start = time.perf_counter()
        await call(client, "display_status")
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    # p50, in-process. The budget is docs/MCP.md's 8 ms; loopback here measures
    # 1-2.4 ms, shared CI runners ~6.5 ms, so 5 ms only failed on slow hardware.
    assert times[len(times) // 2] < 8, times


async def test_every_call_is_audited(client: httpx.AsyncClient, settings: Settings) -> None:
    import sqlite3

    await call(client, "display_status")
    client._transport.app.state.mcp.audit.flush()  # type: ignore[attr-defined]
    with sqlite3.connect(settings.state_dir / "mcp_audit.db") as db:
        row = db.execute(
            "SELECT client, tool, ok, trace FROM calls WHERE tool = 'display_status'"
        ).fetchone()
    assert row == ("antigua", "display_status", 1, _META["traceparent"])


async def test_screen_turn(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from pinedaview import mcp_server

    at = {"now": "normal"}
    monkeypatch.setattr(mcp_server, "rotation", lambda _control: at["now"])
    monkeypatch.setattr(mcp_server, "rotate", lambda _control, turn: at.update(now=turn))

    done = (await call(client, "screen_turn", {"to": "tall"}))["structuredContent"]
    assert done == {"rotation": "90", "changed": True}
    again = (await call(client, "screen_turn", {"to": "tall"}))["structuredContent"]
    assert again == {"rotation": "90", "changed": False}
    flipped = (await call(client, "screen_turn", {"to": "flip"}))["structuredContent"]
    assert flipped["rotation"] == "270"
    back = (await call(client, "screen_turn", {"to": "turn"}))["structuredContent"]
    assert back["rotation"] == "normal"
