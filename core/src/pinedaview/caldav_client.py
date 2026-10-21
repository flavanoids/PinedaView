# SPDX-License-Identifier: Apache-2.0
"""Minimal iCloud CalDAV client — just enough to discover an account's
calendars and pull events out of one, over HTTP Basic auth with an
app-specific password (Apple blocks the real account password for any
third-party client).

Hand-rolled with ``httpx`` + the stdlib XML parser rather than the ``caldav``
package: that library pulls in ``lxml``/``requests``/``vobject`` and is built
synchronous, neither of which fits this project's dependency philosophy or its
async provider model. The protocol itself is small — principal discovery,
calendar-home-set, then a PROPFIND/REPORT per calendar — well documented, and
not worth a heavy dependency for.

iCloud quirk: the well-known entry point ``https://caldav.icloud.com/``
redirects (307) to a per-account host (``pNN-caldav.icloud.com``) on the very
first request — every call below passes through that with
``follow_redirects=True`` and resolves later relative hrefs against the
*response's* final URL, not the request URL, so everything after stays
pinned to the right host automatically.
"""

from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

_BASE_URL = "https://caldav.icloud.com/"

_NS = {
    "d": "DAV:",
    "c": "urn:ietf:params:xml:ns:caldav",
    "cs": "http://calendarserver.org/ns/",
    "ical": "http://apple.com/ns/ical/",
}

_HEADERS_D0 = {"Depth": "0", "Content-Type": "application/xml; charset=utf-8"}
_HEADERS_D1 = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}

_PRINCIPAL_BODY = b"""<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
  <D:prop><D:current-user-principal/></D:prop>
</D:propfind>"""

_HOME_SET_BODY = b"""<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><C:calendar-home-set/></D:prop>
</D:propfind>"""

_CALENDAR_LIST_BODY = b"""<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"
            xmlns:CS="http://calendarserver.org/ns/" xmlns:I="http://apple.com/ns/ical/">
  <D:prop>
    <D:resourcetype/>
    <D:displayname/>
    <CS:getctag/>
    <I:calendar-color/>
  </D:prop>
</D:propfind>"""


class CalDavError(RuntimeError):
    """Discovery or a fetch failed — bad credentials, unreachable, or iCloud
    responded in a shape we didn't expect."""


@dataclass(frozen=True)
class CalDavCalendar:
    href: str
    """Absolute URL — resolved against the per-account host, ready to reuse
    directly in a later REPORT without re-discovering anything."""
    name: str
    color: str | None = None
    """The colour the owner picked in Apple Calendar, ``#RRGGBBAA`` — valid
    CSS as-is, so a shared calendar looks the same here as on their phone."""


def _ok_propstat(response_el: ET.Element) -> ET.Element | None:
    """The ``<D:propstat>`` whose status is 200 — a multistatus response can
    carry several (e.g. one 200 with found props, one 404 with the rest)."""
    for propstat in response_el.findall("d:propstat", _NS):
        status = propstat.findtext("d:status", default="", namespaces=_NS)
        if " 200 " in f" {status} ":
            return propstat
    return None


def _text(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    return el.findtext(path, namespaces=_NS)


async def _propfind(
    client: httpx.AsyncClient, url: str, *, auth: httpx.BasicAuth, body: bytes, depth: str
) -> tuple[ET.Element, str]:
    headers = _HEADERS_D0 if depth == "0" else _HEADERS_D1
    try:
        response = await client.request(
            "PROPFIND", url, auth=auth, headers=headers, content=body, follow_redirects=True
        )
    except httpx.HTTPError as exc:
        raise CalDavError(f"could not reach iCloud: {exc}") from exc
    if response.status_code == 401:
        raise CalDavError("Apple ID or app-specific password was rejected")
    if response.status_code != 207:
        raise CalDavError(f"unexpected response ({response.status_code}) from {url}")
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise CalDavError(f"unreadable response from {url}: {exc}") from exc
    return root, str(response.url)


async def discover_calendars(
    client: httpx.AsyncClient, *, apple_id: str, app_specific_password: str
) -> list[CalDavCalendar]:
    """Every VEVENT-capable calendar visible to this account — owned and
    shared-with-you alike; iCloud lists both as children of the same
    calendar-home-set collection."""
    auth = httpx.BasicAuth(apple_id, app_specific_password)

    root, resolved_url = await _propfind(
        client, _BASE_URL, auth=auth, body=_PRINCIPAL_BODY, depth="0"
    )
    response_el = root.find("d:response", _NS)
    propstat = _ok_propstat(response_el) if response_el is not None else None
    principal_href = _text(propstat, "d:prop/d:current-user-principal/d:href")
    if not principal_href:
        raise CalDavError("iCloud didn't return an account principal")
    principal_url = urllib.parse.urljoin(resolved_url, principal_href)

    root, resolved_url = await _propfind(
        client, principal_url, auth=auth, body=_HOME_SET_BODY, depth="0"
    )
    response_el = root.find("d:response", _NS)
    propstat = _ok_propstat(response_el) if response_el is not None else None
    home_href = _text(propstat, "d:prop/c:calendar-home-set/d:href")
    if not home_href:
        raise CalDavError("iCloud didn't return a calendar home")
    home_url = urllib.parse.urljoin(resolved_url, home_href)

    root, resolved_url = await _propfind(
        client, home_url, auth=auth, body=_CALENDAR_LIST_BODY, depth="1"
    )
    calendars: list[CalDavCalendar] = []
    for response_el in root.findall("d:response", _NS):
        propstat = _ok_propstat(response_el)
        if propstat is None:
            continue
        is_calendar = propstat.find("d:prop/d:resourcetype/c:calendar", _NS) is not None
        if not is_calendar:
            continue
        href = response_el.findtext("d:href", namespaces=_NS)
        if not href:
            continue
        name = _text(propstat, "d:prop/d:displayname") or href
        color = (_text(propstat, "d:prop/ical:calendar-color") or "").strip() or None
        calendars.append(
            CalDavCalendar(href=urllib.parse.urljoin(resolved_url, href), name=name, color=color)
        )
    return calendars


def _caldav_time(when: datetime) -> str:
    return when.strftime("%Y%m%dT%H%M%SZ")


def _event_query_body(time_min: datetime, time_max: datetime) -> bytes:
    start, end = _caldav_time(time_min), _caldav_time(time_max)
    return f"""<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><C:calendar-data/></D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="{start}" end="{end}"/>
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>""".encode()


async def fetch_event_blobs(
    client: httpx.AsyncClient,
    *,
    calendar_href: str,
    apple_id: str,
    app_specific_password: str,
    time_min: datetime,
    time_max: datetime,
) -> list[str]:
    """Raw iCalendar text, one ``BEGIN:VCALENDAR...END:VCALENDAR`` blob per
    matching resource — parse with :mod:`icalendar` (a wrapped ``VEVENT``
    series comes back as the master event, so recurrence still needs
    ``recurring_ical_events`` to expand it)."""
    auth = httpx.BasicAuth(apple_id, app_specific_password)
    body = _event_query_body(time_min, time_max)
    try:
        response = await client.request(
            "REPORT",
            calendar_href,
            auth=auth,
            headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
            content=body,
        )
    except httpx.HTTPError as exc:
        raise CalDavError(f"could not reach iCloud: {exc}") from exc
    if response.status_code != 207:
        raise CalDavError(f"event query failed ({response.status_code})")
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise CalDavError(f"unreadable event response: {exc}") from exc

    blobs: list[str] = []
    for response_el in root.findall("d:response", _NS):
        propstat = _ok_propstat(response_el)
        data = _text(propstat, "d:prop/c:calendar-data")
        if data:
            blobs.append(data)
    return blobs


def as_dict(calendars: list[CalDavCalendar]) -> list[dict[str, Any]]:
    """Shaped to match what :func:`pinedaview.connect_page.render_picker`
    expects — the same ``id``/``summary`` keys Google's calendarList uses —
    so the picker page stays backend-agnostic."""
    return [{"id": c.href, "summary": c.name, "backgroundColor": c.color} for c in calendars]
