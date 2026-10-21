# SPDX-License-Identifier: Apache-2.0
"""CalendarProvider: source selection, event shaping, and the "not connected
yet" fallback. Token refresh needs a real httpx client (it calls Google
directly, not ctx.fetch_json), so it's covered in test_google_oauth.py's pure
unit tests instead of here."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from pinedaview.config import Settings
from pinedaview.providers.base import ProviderContext
from pinedaview.providers.calendar import CalendarProvider
from pinedaview.secrets import SecretStore
from pinedaview.stores import StoreRegistry

from .conftest import FakeContext

_EVENTS_RESPONSE = {
    "items": [
        {
            "id": "evt-2",
            "summary": "Dentist",
            "start": {"dateTime": "2026-09-12T15:00:00-05:00"},
            "end": {"dateTime": "2026-09-12T15:30:00-05:00"},
        },
        {
            "id": "evt-1",
            "summary": "Team standup",
            "start": {"dateTime": "2026-09-11T09:00:00-05:00"},
            "end": {"dateTime": "2026-09-11T09:15:00-05:00"},
        },
        {
            "id": "evt-cancelled",
            "status": "cancelled",
            "start": {"dateTime": "2026-09-11T10:00:00-05:00"},
        },
    ]
}


def _connected_secrets(tmp_path: Path) -> SecretStore:
    secrets = SecretStore(tmp_path)
    secrets.set("google_calendar_client_id", "cid")
    secrets.set("google_calendar_client_secret", "csecret")
    secrets.set(
        "google_calendar_account",
        json.dumps(
            {
                "email": "me@example.com",
                "access_token": "fresh-token",
                "refresh_token": "r",
                "expires_at": time.time() + 3600,
            }
        ),
    )
    return secrets


async def test_calendar_not_connected_returns_none(settings: Settings) -> None:
    ctx = FakeContext(settings, secrets=SecretStore(settings.state_dir))
    assert await CalendarProvider().poll(ctx) is None


async def test_calendar_no_selected_sources_returns_empty(
    settings: Settings, tmp_path: Path
) -> None:
    secrets = _connected_secrets(tmp_path)
    ctx = FakeContext(settings, secrets=secrets, card_settings={"calendar": {"sources": []}})
    value = await CalendarProvider().poll(ctx)
    assert value is not None
    assert value["events"] == []


async def test_calendar_fetches_and_sorts_selected_sources(
    settings: Settings, tmp_path: Path
) -> None:
    secrets = _connected_secrets(tmp_path)
    ctx = FakeContext(
        settings,
        secrets=secrets,
        responses=[_EVENTS_RESPONSE],
        card_settings={
            "calendar": {
                "sources": [
                    {
                        "calendarId": "primary",
                        "label": "Work",
                        "color": "#7986cb",
                        "selected": True,
                    },
                    {
                        "calendarId": "other@group.calendar.google.com",
                        "label": "Family",
                        "selected": False,
                    },
                ]
            }
        },
    )
    value = await CalendarProvider().poll(ctx)
    assert value is not None
    # cancelled event dropped, remaining two sorted by start time
    titles = [e["title"] for e in value["events"]]
    assert titles == ["Team standup", "Dentist"]
    assert all(e["calendar"] == "Work" for e in value["events"])
    # only the selected calendar was queried
    assert len(ctx.requested_urls) == 1
    assert "primary" in ctx.requested_urls[0]


# ── Apple / iCloud CalDAV ────────────────────────────────────────────────────

# Tomorrow, so the event is always still ahead of the provider's window.
_TOMORROW = time.strftime("%Y%m%d", time.gmtime(time.time() + 86400))
_APPLE_EVENTS_XML = b"""<?xml version="1.0"?>
<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:response>
    <D:href>/123/calendars/plant/water.ics</D:href>
    <D:propstat>
      <D:prop><C:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:water-ferns
SUMMARY:Water the ferns
DTSTART:{day}T140000Z
DTEND:{day}T143000Z
END:VEVENT
END:VCALENDAR
</C:calendar-data></D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>"""


async def test_calendar_fetches_apple_source(settings: Settings, tmp_path: Path) -> None:
    secrets = SecretStore(tmp_path)
    secrets.set(
        "apple_calendar_account",
        json.dumps({"appleId": "me@icloud.com", "password": "abcd-efgh-ijkl-mnop"}),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "REPORT"
        return httpx.Response(207, content=_APPLE_EVENTS_XML.replace(b"{day}", _TOMORROW.encode()))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ProviderContext(
            settings,
            StoreRegistry(),
            secrets=secrets,
            card_settings={
                "calendar": {
                    "sources": [
                        {
                            "calendarId": "https://p01/cal/plant/",
                            "label": "Plant House",
                            "selected": True,
                            "type": "apple",
                        }
                    ]
                }
            },
            client=http_client,
        )
        value = await CalendarProvider().poll(ctx)

    assert value is not None
    assert [e["title"] for e in value["events"]] == ["Water the ferns"]
    assert value["events"][0]["calendar"] == "Plant House"
    assert value["events"][0]["allDay"] is False


async def test_calendar_apple_source_skipped_when_not_connected(
    settings: Settings, tmp_path: Path
) -> None:
    """Apple-type sources selected but no Apple account connected: skip them,
    don't error — same tolerance as an unreachable Google calendar."""
    secrets = SecretStore(tmp_path)
    ctx = FakeContext(
        settings,
        secrets=secrets,
        card_settings={
            "calendar": {
                "sources": [
                    {
                        "calendarId": "https://p01/cal/plant/",
                        "label": "Plant House",
                        "selected": True,
                        "type": "apple",
                    }
                ]
            }
        },
    )
    # No Google or Apple account connected at all — "not connected yet".
    assert await CalendarProvider().poll(ctx) is None


async def test_calendar_passes_view_and_drops_declined(settings: Settings, tmp_path: Path) -> None:
    response = {
        "items": [
            *_EVENTS_RESPONSE["items"][:2],
            {
                "id": "evt-declined",
                "summary": "Skipped",
                "start": {"dateTime": "2026-09-11T11:00:00-05:00"},
                "end": {"dateTime": "2026-09-11T12:00:00-05:00"},
                "attendees": [{"self": True, "responseStatus": "declined"}],
            },
        ]
    }
    sources = [{"calendarId": "primary", "label": "Work", "selected": True}]
    ctx = FakeContext(
        settings,
        secrets=_connected_secrets(tmp_path),
        responses=[response],
        card_settings={"calendar": {"sources": sources, "view": "next12h"}},
    )
    value = await CalendarProvider().poll(ctx)
    assert value is not None
    assert value["view"] == "next12h"
    assert "Skipped" not in [e["title"] for e in value["events"]]


async def test_calendar_unknown_view_falls_back_to_week(settings: Settings, tmp_path: Path) -> None:
    ctx = FakeContext(
        settings,
        secrets=_connected_secrets(tmp_path),
        card_settings={"calendar": {"sources": [], "view": "month"}},
    )
    value = await CalendarProvider().poll(ctx)
    assert value is not None
    assert value["view"] == "week"


async def test_calendar_reads_a_calendar_link(settings: Settings, tmp_path: Path) -> None:
    """A Proton-style share link: plain iCalendar over HTTPS."""
    secrets = SecretStore(tmp_path)
    url = "https://calendar.proton.me/api/calendar/v1/url/abc/calendar.ics"
    secrets.set("calendar_links", json.dumps([{"id": "link-1", "label": "Proton", "url": url}]))
    ics = (
        _APPLE_EVENTS_XML.replace(b"{day}", _TOMORROW.encode())
        .decode()
        .split("<C:calendar-data>")[1]
        .split("</C:calendar-data>")[0]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == url
        return httpx.Response(200, text=ics)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ProviderContext(
            settings,
            StoreRegistry(),
            secrets=secrets,
            card_settings={
                "calendar": {
                    "sources": [
                        {"calendarId": "link-1", "label": "Proton", "selected": True, "type": "ics"}
                    ]
                }
            },
            client=http_client,
        )
        value = await CalendarProvider().poll(ctx)

    assert value is not None
    assert [e["title"] for e in value["events"]] == ["Water the ferns"]
    assert value["events"][0]["calendar"] == "Proton"
