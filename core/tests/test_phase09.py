# SPDX-License-Identifier: Apache-2.0
"""Phase 09 — packaging & release: bundled web client, version surfacing,
config discovery."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager

from pinedaview import __version__, config, webroot
from pinedaview.runtime import Runtime


@pytest.fixture
def bundled_web(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "webroot"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Pineda</title>")
    (root / "assets" / "app.js").write_text("console.log('hi')")
    (root / "sw.js").write_text("self.skipWaiting()")
    # Reached through a symlink, as on a box where /opt links elsewhere: the
    # resolved file path must still count as inside the webroot.
    link = tmp_path / "linked"
    link.symlink_to(tmp_path)
    monkeypatch.setattr(webroot, "webroot_dir", lambda: link / "webroot")
    return root


@pytest_asyncio.fixture
async def web_client(
    runtime: Runtime,
    bundled_web: Path,  # noqa: ARG001 - fixture stages the webroot dir
) -> AsyncIterator[httpx.AsyncClient]:
    from pinedaview.api import create_app

    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


async def test_health_reports_the_release_version(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/health")).json()
    assert body["app_version"] == __version__
    assert body["version"] == "v0"  # the wire protocol, unchanged


async def test_bundled_client_is_served_at_the_root(web_client: httpx.AsyncClient) -> None:
    res = await web_client.get("/")
    assert res.status_code == 200
    assert "Pineda" in res.text


async def test_unknown_route_falls_back_to_index(web_client: httpx.AsyncClient) -> None:
    res = await web_client.get("/settings/devices")
    assert res.status_code == 200
    assert "<!doctype html>" in res.text.lower()


async def test_real_asset_is_served(web_client: httpx.AsyncClient) -> None:
    res = await web_client.get("/assets/app.js")
    assert res.status_code == 200
    assert "console.log" in res.text


async def test_top_level_file_is_served(web_client: httpx.AsyncClient) -> None:
    # Not the index fallback: a service worker served as HTML never updates.
    res = await web_client.get("/sw.js")
    assert res.status_code == 200
    assert res.text == "self.skipWaiting()"


async def test_api_paths_never_hit_the_spa_fallback(web_client: httpx.AsyncClient) -> None:
    assert (await web_client.get("/api/nope")).status_code == 404


async def test_api_only_when_no_client_bundled(client: httpx.AsyncClient) -> None:
    # the default `client` fixture has no bundled web dir
    assert (await client.get("/api/health")).status_code == 200


def test_config_discovery_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "custom.toml"
    cfg.write_text('theme = "midnight"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PINEDA_CONFIG_FILE", str(cfg))
    assert config._discover_config() == cfg


def test_config_discovery_falls_back_to_etc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PINEDA_CONFIG_FILE", raising=False)
    system = tmp_path / "etc-config.toml"
    system.write_text('theme = "midnight"\n')
    monkeypatch.setattr(config, "_SYSTEM_CONFIG", system)
    assert config._discover_config() == system


def test_env_beats_the_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('theme = "from_file"\nunits = "metric"\n')
    monkeypatch.setenv("PINEDA_THEME", "from_env")
    settings = config.load_settings(cfg)
    assert settings.theme == "from_env"  # env wins
    assert settings.units == "metric"  # file fills the rest
