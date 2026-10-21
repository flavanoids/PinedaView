# SPDX-License-Identifier: Apache-2.0
"""/connect-calendar and /api/calendar/*: the parts reachable without a real
Google account — not-configured fallbacks, expired/forged state, and the
account/disconnect bookkeeping endpoints."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from pinedaview import caldav_client, google_oauth
from pinedaview.api import create_app
from pinedaview.config import load_settings
from pinedaview.runtime import build_runtime


async def test_connect_calendar_without_client_id_shows_setup_page(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/connect-calendar", follow_redirects=False)
    assert response.status_code == 200
    assert "isn't finished yet" in response.text


async def test_connect_calendar_redirects_to_google_once_configured(tmp_path: Path) -> None:
    settings = load_settings(
        overrides={
            "state_dir": tmp_path,
            "photos_dir": str(tmp_path / "photos"),
            "api": {"db_path": str(tmp_path / "pineda.db")},
            "config_file": str(tmp_path / "config.toml"),
            "calendar": {"bounce_url": "https://bounce.example/cb"},
        }
    )
    runtime = build_runtime(settings, providers=[])
    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.put("/api/secrets/google_calendar_client_id", json={"value": "cid"})
            response = await client.get("/connect-calendar", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=cid" in location
    assert "redirect_uri=https%3A%2F%2Fbounce.example%2Fcb" in location
    assert "code_challenge=" in location


async def test_oauth_finish_rejects_forged_state(client: httpx.AsyncClient) -> None:
    await client.put("/api/secrets/google_calendar_client_id", json={"value": "cid"})
    await client.put("/api/secrets/google_calendar_client_secret", json={"value": "csecret"})
    response = await client.get(
        "/api/calendar/oauth/finish", params={"code": "abc", "state": "not-real-state"}
    )
    assert response.status_code == 200
    assert "tampered" in response.text


async def test_oauth_finish_shows_denial_reason(client: httpx.AsyncClient) -> None:
    await client.put("/api/secrets/google_calendar_client_id", json={"value": "cid"})
    await client.put("/api/secrets/google_calendar_client_secret", json={"value": "csecret"})
    response = await client.get(
        "/api/calendar/oauth/finish", params={"error": "access_denied", "state": "whatever"}
    )
    assert response.status_code == 200
    assert "access_denied" in response.text


async def test_oauth_finish_handles_missing_code_or_state(client: httpx.AsyncClient) -> None:
    await client.put("/api/secrets/google_calendar_client_id", json={"value": "cid"})
    await client.put("/api/secrets/google_calendar_client_secret", json={"value": "csecret"})
    response = await client.get("/api/calendar/oauth/finish")
    assert response.status_code == 200
    assert "send back what we expected" in response.text


async def test_oauth_finish_rejects_expired_or_unknown_nonce(client: httpx.AsyncClient) -> None:
    await client.put("/api/secrets/google_calendar_client_id", json={"value": "cid"})
    await client.put("/api/secrets/google_calendar_client_secret", json={"value": "csecret"})
    state = google_oauth.encode_state(nonce="never-issued", return_url="http://x/finish")
    response = await client.get(
        "/api/calendar/oauth/finish", params={"code": "abc", "state": state}
    )
    assert response.status_code == 200
    assert "expired" in response.text


async def test_connect_calendar_refreshes_in_place_when_already_connected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revisiting /connect-calendar with a connected account should show the
    picker directly — no bounce back through Google's consent screen — so
    picking up a newly-shared calendar doesn't require a full reconnect."""
    settings = load_settings(
        overrides={
            "state_dir": tmp_path,
            "photos_dir": str(tmp_path / "photos"),
            "api": {"db_path": str(tmp_path / "pineda.db")},
            "config_file": str(tmp_path / "config.toml"),
            "calendar": {"bounce_url": "https://bounce.example/cb"},
        }
    )
    runtime = build_runtime(settings, providers=[])
    app = create_app(runtime)

    async def fake_fetch_calendar_list(_client: object, **_kwargs: object) -> list[dict[str, str]]:
        return [{"id": "shared@group.calendar.google.com", "summary": "Plant House"}]

    monkeypatch.setattr(google_oauth, "fetch_calendar_list", fake_fetch_calendar_list)

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.put("/api/secrets/google_calendar_client_id", json={"value": "cid"})
            await client.put(
                "/api/secrets/google_calendar_client_secret", json={"value": "csecret"}
            )
            await client.put(
                "/api/secrets/google_calendar_account",
                json={
                    "value": json.dumps(
                        {
                            "email": "me@example.com",
                            "access_token": "tok",
                            "refresh_token": "r",
                            "expires_at": time.time() + 3600,
                        }
                    )
                },
            )
            source = {
                "calendarId": "shared@group.calendar.google.com",
                "label": "Plant House",
                "selected": True,
            }
            await client.put("/api/cards/calendar/settings", json={"values": {"sources": [source]}})

            response = await client.get("/connect-calendar", follow_redirects=False)
    assert response.status_code == 200
    assert "Plant House" in response.text
    assert "checked" in response.text  # prior selection carried forward


async def test_calendar_account_reports_disconnected_by_default(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/calendar/account")
    assert response.status_code == 200
    assert response.json() == {"connected": False, "email": None}


async def test_calendar_account_reports_connected_email(client: httpx.AsyncClient) -> None:
    await client.put(
        "/api/secrets/google_calendar_account",
        json={"value": '{"email": "me@example.com", "access_token": "a"}'},
    )
    response = await client.get("/api/calendar/account")
    assert response.json() == {"connected": True, "email": "me@example.com"}


async def test_disconnect_clears_account_and_sources(client: httpx.AsyncClient) -> None:
    await client.put(
        "/api/secrets/google_calendar_account",
        json={"value": '{"email": "me@example.com", "access_token": "a"}'},
    )
    source = {"calendarId": "primary", "label": "Work", "selected": True}
    await client.put("/api/cards/calendar/settings", json={"values": {"sources": [source]}})
    response = await client.post("/api/calendar/disconnect")
    assert response.status_code == 204

    account = await client.get("/api/calendar/account")
    assert account.json() == {"connected": False, "email": None}
    settings = await client.get("/api/cards/calendar/settings")
    assert settings.json()["values"].get("sources", []) == []


# ── Apple / iCloud CalDAV ────────────────────────────────────────────────────


async def test_connect_apple_calendar_shows_form_when_not_connected(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/connect-apple-calendar")
    assert response.status_code == 200
    assert "Connect Apple Calendar" in response.text


async def test_apple_connect_rejects_bad_credentials(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_discover(*_args: object, **_kwargs: object) -> list[object]:
        raise caldav_client.CalDavError("Apple ID or app-specific password was rejected")

    monkeypatch.setattr(caldav_client, "discover_calendars", fake_discover)
    response = await client.post(
        "/api/calendar/apple/connect",
        data={"apple_id": "me@example.com", "password": "wrong"},
    )
    assert response.status_code == 200
    assert "rejected" in response.text
    account = await client.get("/api/calendar/apple/account")
    assert account.json()["connected"] is False


async def test_apple_connect_success_stores_account_and_shows_picker(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_discover(
        *_args: object, **_kwargs: object
    ) -> list[caldav_client.CalDavCalendar]:
        return [caldav_client.CalDavCalendar(href="https://p01/cal/plant/", name="Plant House")]

    monkeypatch.setattr(caldav_client, "discover_calendars", fake_discover)
    response = await client.post(
        "/api/calendar/apple/connect",
        data={"apple_id": "me@example.com", "password": "abcd-efgh-ijkl-mnop"},
    )
    assert response.status_code == 200
    assert "Plant House" in response.text

    account = await client.get("/api/calendar/apple/account")
    assert account.json() == {"connected": True, "apple_id": "me@example.com"}


async def test_apple_disconnect_only_drops_apple_sources(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_discover(
        *_args: object, **_kwargs: object
    ) -> list[caldav_client.CalDavCalendar]:
        return [caldav_client.CalDavCalendar(href="https://p01/cal/plant/", name="Plant House")]

    monkeypatch.setattr(caldav_client, "discover_calendars", fake_discover)
    await client.post(
        "/api/calendar/apple/connect",
        data={"apple_id": "me@example.com", "password": "abcd-efgh-ijkl-mnop"},
    )
    google_source = {
        "calendarId": "primary",
        "label": "Work",
        "selected": True,
        "type": "google",
    }
    await client.post("/api/calendar/sources", json={"sources": [google_source]})

    response = await client.post("/api/calendar/apple/disconnect")
    assert response.status_code == 204

    settings = await client.get("/api/cards/calendar/settings")
    sources = settings.json()["values"]["sources"]
    assert [s["type"] for s in sources] == ["google"]

    apple_account = await client.get("/api/calendar/apple/account")
    assert apple_account.json()["connected"] is False
