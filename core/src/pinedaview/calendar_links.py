# SPDX-License-Identifier: Apache-2.0
"""Calendar links — a read-only iCalendar feed at a URL.

The one way out of a calendar that has no API: Proton Calendar's "Share via
link", Outlook's published calendars, a school or team schedule. The URL is
the credential (whoever has it can read the calendar), so the list lives in
the secret store as ``calendar_links``, never in plain config.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass

import httpx
import icalendar

_MAX_BYTES = 5_000_000
"""A family calendar's whole history is a few hundred KB; past this it's not
a calendar, or not one worth parsing every 15 minutes."""


class CalendarLinkError(RuntimeError):
    """The link didn't answer, or what came back isn't a calendar."""


@dataclass(frozen=True)
class CalendarLink:
    id: str
    label: str
    url: str
    color: str | None = None


def load_links(raw: str | None) -> dict[str, CalendarLink]:
    if not raw:
        return {}
    try:
        items = json.loads(raw)
        return {i["id"]: CalendarLink(**i) for i in items if isinstance(i, dict)}
    except (ValueError, TypeError, KeyError):
        return {}


def dump_links(links: dict[str, CalendarLink]) -> str:
    return json.dumps([asdict(link) for link in links.values()])


def new_link_id() -> str:
    return f"link-{secrets.token_hex(4)}"


def normalize_url(url: str) -> str:
    """Calendar apps hand these out as ``webcal://`` — the same feed over
    HTTPS, named so a click opens a calendar app instead of a download."""
    url = url.strip()
    if url.lower().startswith("webcal://"):
        return "https://" + url[len("webcal://") :]
    return url


async def fetch_link(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise CalendarLinkError(f"couldn't reach it: {exc}") from exc
    if response.status_code != 200:
        raise CalendarLinkError(f"it answered {response.status_code}")
    if len(response.content) > _MAX_BYTES:
        raise CalendarLinkError("it's too large to be a calendar")
    text = response.text
    if "BEGIN:VCALENDAR" not in text[:2000]:
        raise CalendarLinkError("that link isn't a calendar feed")
    return text


def calendar_name(blob: str) -> str | None:
    """The feed's own name (``X-WR-CALNAME``), to label it without asking."""
    try:
        name = icalendar.Calendar.from_ical(blob).get("X-WR-CALNAME")
    except ValueError:
        return None
    return str(name).strip() or None if name else None
