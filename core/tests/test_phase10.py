# SPDX-License-Identifier: Apache-2.0
"""Phase 10 — hardening: deep health, metrics, status page, correlation ids,
the admin surface split."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager

from pinedaview.config import MqttConfig, Settings, load_settings
from pinedaview.mqtt import MqttBridge
from pinedaview.runtime import Runtime, build_runtime


async def test_health_is_deep(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/health")).json()
    assert body["ok"] is True
    assert body["checks"]["database"] == "ok"
    assert "stores" in body["checks"]
    assert body["uptime_s"] >= 0


async def test_health_503_when_the_database_is_broken(
    client: httpx.AsyncClient, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom() -> list[object]:
        raise RuntimeError("disk gone")

    monkeypatch.setattr(runtime.devices, "profiles", boom)
    res = await client.get("/api/health")
    assert res.status_code == 503
    assert res.json()["ok"] is False
    assert "disk gone" in res.json()["checks"]["database"]


async def test_health_surfaces_a_rejected_mqtt_connect(
    client: httpx.AsyncClient, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = MqttBridge(MqttConfig(enabled=True), runtime.stores)
    bridge.last_error = "Not authorized"
    monkeypatch.setattr(runtime, "mqtt", bridge)
    body = (await client.get("/api/health")).json()
    assert body["checks"]["mqtt"] == "configured, not connected (Not authorized)"


async def test_metrics_are_prometheus_text(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/metrics")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert "pineda_up 1" in res.text
    assert 'pineda_build_info{version="' in res.text
    assert "pineda_sse_subscribers " in res.text


async def test_status_page_renders(client: httpx.AsyncClient) -> None:
    res = await client.get("/status")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "PinedaDisplay Web" in res.text


async def test_every_response_carries_a_correlation_id(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/health")
    assert len(res.headers["x-request-id"]) >= 8
    supplied = await client.get("/api/health", headers={"x-request-id": "abc123"})
    assert supplied.headers["x-request-id"] == "abc123"


@pytest_asyncio.fixture
async def admin_settings(tmp_path: Path) -> Settings:
    return load_settings(
        overrides={
            "state_dir": str(tmp_path),
            "photos_dir": str(tmp_path / "photos"),
            "api": {"db_path": str(tmp_path / "p.db"), "admin_token": "sekret"},
            "config_file": str(tmp_path / "config.toml"),
        }
    )


@pytest_asyncio.fixture
async def admin_client(admin_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    from pinedaview.api import create_app

    app = create_app(build_runtime(admin_settings, providers=[]))
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


async def test_admin_token_gates_the_admin_surface(admin_client: httpx.AsyncClient) -> None:
    # public surface: open
    assert (await admin_client.get("/api/health")).status_code == 200
    assert (await admin_client.get("/api/themes")).status_code == 200
    # admin surface: closed without the token, even on a GET
    assert (await admin_client.get("/api/secrets")).status_code == 401
    assert (await admin_client.get("/api/config")).status_code == 401
    # with the token: allowed
    ok = await admin_client.get("/api/secrets", headers={"authorization": "Bearer sekret"})
    assert ok.status_code == 200
