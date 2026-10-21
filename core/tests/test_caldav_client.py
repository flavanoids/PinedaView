# SPDX-License-Identifier: Apache-2.0
"""caldav_client against a mocked iCloud, including the redirect to a
per-account host — the one hop that's easy to get wrong, since relative hrefs
after it must resolve against the *response's* final URL, not caldav.icloud.com."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from pinedaview import caldav_client

_PRINCIPAL_XML = b"""<?xml version="1.0"?>
<D:multistatus xmlns:D="DAV:">
  <D:response>
    <D:href>/</D:href>
    <D:propstat>
      <D:prop><D:current-user-principal><D:href>/123456/principal/</D:href></D:current-user-principal></D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>"""

_HOME_SET_XML = b"""<?xml version="1.0"?>
<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:response>
    <D:href>/123456/principal/</D:href>
    <D:propstat>
      <D:prop><C:calendar-home-set><D:href>/123456/calendars/</D:href></C:calendar-home-set></D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>"""

_CALENDAR_LIST_XML = b"""<?xml version="1.0"?>
<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"
               xmlns:I="http://apple.com/ns/ical/">
  <D:response>
    <D:href>/123456/calendars/plant-house/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/><C:calendar/></D:resourcetype>
        <D:displayname>Plant House</D:displayname>
        <I:calendar-color>#63DA38FF</I:calendar-color>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
  <D:response>
    <D:href>/123456/calendars/inbox/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/></D:resourcetype>
        <D:displayname>inbox</D:displayname>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>"""

_EVENTS_XML = b"""<?xml version="1.0"?>
<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:response>
    <D:href>/123456/calendars/plant-house/water.ics</D:href>
    <D:propstat>
      <D:prop><C:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:water-the-ferns
SUMMARY:Water the ferns
DTSTART:20260912T140000Z
DTEND:20260912T143000Z
END:VEVENT
END:VCALENDAR
</C:calendar-data></D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>"""


def _discovery_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    path = request.url.path
    if host == "caldav.icloud.com":
        return httpx.Response(301, headers={"Location": "https://p01-caldav.icloud.com/"})
    assert host == "p01-caldav.icloud.com"
    if path == "/":
        return httpx.Response(207, content=_PRINCIPAL_XML)
    if path == "/123456/principal/":
        return httpx.Response(207, content=_HOME_SET_XML)
    if path == "/123456/calendars/":
        return httpx.Response(207, content=_CALENDAR_LIST_XML)
    raise AssertionError(f"unexpected request to {request.url}")


async def test_discover_calendars_resolves_through_redirect() -> None:
    transport = httpx.MockTransport(_discovery_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        calendars = await caldav_client.discover_calendars(
            client, apple_id="me@example.com", app_specific_password="abcd-efgh-ijkl-mnop"
        )
    assert len(calendars) == 1  # "inbox" has no C:calendar resourcetype — excluded
    assert calendars[0].name == "Plant House"
    assert calendars[0].href == "https://p01-caldav.icloud.com/123456/calendars/plant-house/"
    assert calendars[0].color == "#63DA38FF"


async def test_discover_calendars_bad_password_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(caldav_client.CalDavError, match="rejected"):
            await caldav_client.discover_calendars(
                client, apple_id="me@example.com", app_specific_password="wrong"
            )


async def test_fetch_event_blobs_returns_raw_ics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "REPORT"
        return httpx.Response(207, content=_EVENTS_XML)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        blobs = await caldav_client.fetch_event_blobs(
            client,
            calendar_href="https://p01-caldav.icloud.com/123456/calendars/plant-house/",
            apple_id="me@example.com",
            app_specific_password="abcd-efgh-ijkl-mnop",
            time_min=datetime(2026, 9, 1, tzinfo=UTC),
            time_max=datetime(2026, 9, 30, tzinfo=UTC),
        )
    assert len(blobs) == 1
    assert "Water the ferns" in blobs[0]
