# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from pinedaview.config import Settings, load_settings
from pinedaview.setup import _config_document, detect_location, write_config


def test_setup_incomplete_by_default() -> None:
    assert Settings().setup_complete is False


def test_load_settings_marks_complete_when_a_config_file_exists(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('units = "metric"\n')
    assert load_settings(cfg).setup_complete is True


def test_write_config_round_trips(tmp_path: Path) -> None:
    settings = Settings(
        units="metric",
        theme="ocean",
        location={"query": "Berlin", "label": "Home", "latitude": 52.5, "longitude": 13.4},
        countdown={"enabled": True, "start": "06:30", "end": "07:00"},
    )
    path = tmp_path / "config.toml"
    write_config(settings, path)
    assert settings.setup_complete is True

    reloaded = load_settings(path)
    assert reloaded.units == "metric"
    assert reloaded.theme == "ocean"
    assert reloaded.location.query == "Berlin"
    assert reloaded.location.latitude == pytest.approx(52.5)
    assert reloaded.countdown.enabled is True
    assert reloaded.setup_complete is True


def test_config_document_omits_disabled_countdown() -> None:
    doc = _config_document(Settings())
    assert "countdown" not in doc
    assert doc["setup_complete"] is True


async def test_detect_location_parses_ip_api() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "success",
                "city": "Austin",
                "regionName": "Texas",
                "country": "USA",
                "lat": 30.27,
                "lon": -97.74,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        found = await detect_location(client)
    assert found is not None
    assert found.label == "Austin, Texas"
    assert found.query == "30.27,-97.74"


async def test_detect_location_handles_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "fail"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await detect_location(client) is None


async def test_api_setup_flow(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/config")).json()["setup_complete"] is False
    done = await client.post("/api/setup/complete")
    assert done.status_code == 200
    assert done.json()["setup_complete"] is True
    # detect-location returns null in tests (no real network via ASGITransport)
    resp = await client.get("/api/setup/detect-location")
    assert resp.status_code == 200
