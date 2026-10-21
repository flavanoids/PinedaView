# SPDX-License-Identifier: Apache-2.0
"""Calendar — Google Calendar API and/or Apple iCloud CalDAV, whichever
accounts are connected.

Each needs its own connected account (``secret:google_calendar_account``,
written by the OAuth handshake in :mod:`pinedaview.api`; or
``secret:apple_calendar_account``, written by the CalDAV form) and at least
one selected calendar in the card's own settings (``sources`` — a list of
``{calendarId, label, color, selected, type}`` picked at connect time, same
shape as Commute's stops, ``type`` distinguishing which backend a source
belongs to). Neither backend is required — a display can run Google-only,
Apple-only, or both, and a per-source ``type`` field means one save never
touches the other backend's entries (see ``set_calendar_sources`` in api.py)."""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

import icalendar
import recurring_ical_events

from pinedaview import caldav_client, google_oauth
from pinedaview.calendar_links import CalendarLink, CalendarLinkError, fetch_link, load_links
from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError

logger = logging.getLogger(__name__)

_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
_VIEWS = ("next12h", "today", "week")
# One window covers every view: a day back so "today" can still show this
# morning's already-finished events (the server doesn't know the display's
# midnight — the card cuts the window in local time), eight ahead so "week"
# reaches the end of its seventh day in any timezone.
_LOOKBACK = timedelta(days=1)
_LOOKAHEAD = timedelta(days=8)
_MAX_EVENTS_PER_CALENDAR = 50


def _google_event_view(
    raw: dict[str, Any], *, source_label: str, source_color: str | None
) -> dict[str, Any]:
    start = raw.get("start", {})
    end = raw.get("end", {})
    all_day = "date" in start
    return {
        "id": raw.get("id", ""),
        "title": raw.get("summary") or "(untitled)",
        "start": start.get("date") or start.get("dateTime"),
        "end": end.get("date") or end.get("dateTime"),
        "allDay": all_day,
        "location": raw.get("location"),
        "calendar": source_label,
        "color": source_color,
        "declined": any(
            a.get("self") and a.get("responseStatus") == "declined"
            for a in raw.get("attendees", [])
        ),
    }


def _ics_datetime(value: Any) -> tuple[str, bool]:
    """``(iso_string, all_day)`` from an icalendar DTSTART/DTEND's ``.dt`` —
    a ``date`` for an all-day event, a ``datetime`` otherwise."""
    if isinstance(value, datetime):
        return value.isoformat(), False
    return value.isoformat(), True


def _apple_event_view(
    vevent: Any, *, source_label: str, source_color: str | None
) -> dict[str, Any]:
    start, all_day = _ics_datetime(vevent["DTSTART"].dt)
    end = start
    if "DTEND" in vevent:
        end, _ = _ics_datetime(vevent["DTEND"].dt)
    return {
        "id": str(vevent.get("UID", "")),
        "title": str(vevent.get("SUMMARY") or "(untitled)"),
        "start": start,
        "end": end,
        "allDay": all_day,
        "location": str(vevent["LOCATION"]) if "LOCATION" in vevent else None,
        "calendar": source_label,
        "color": source_color,
        "declined": str(vevent.get("STATUS", "")).upper() == "CANCELLED",
    }


def _ics_events(
    blobs: list[str], source: dict[str, Any], *, time_min: datetime, time_max: datetime
) -> list[dict[str, Any]]:
    """Every occurrence inside the window, recurrences expanded, from raw
    iCalendar text — iCloud's CalDAV and a calendar link both hand us this."""
    events = []
    for blob in blobs:
        try:
            calendar = icalendar.Calendar.from_ical(blob)
            occurrences = recurring_ical_events.of(calendar).between(time_min, time_max)
        except (ValueError, KeyError) as exc:
            logger.warning("calendar %s: unreadable event: %s", source["calendarId"], exc)
            continue
        for vevent in occurrences:
            events.append(
                _apple_event_view(
                    vevent,
                    source_label=source.get("label") or source["calendarId"],
                    source_color=source.get("color"),
                )
            )
    return events


def _apple_credentials(ctx: ProviderContext) -> tuple[str | None, str | None]:
    """``(apple_id, app_specific_password)`` from the stored account, or
    ``(None, None)`` when there isn't a usable one."""
    raw = ctx.secret("apple_calendar_account")
    if not raw:
        return None, None
    try:
        account = json.loads(raw)
        return str(account["appleId"]), str(account["password"])
    except (ValueError, KeyError):
        logger.warning("apple_calendar_account secret is malformed")
        return None, None


class CalendarProvider(Provider):
    key = "calendar"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return cfg.calendar_interval_s

    async def _valid_google_tokens(
        self, ctx: ProviderContext, *, account_raw: str, client_id: str, client_secret: str
    ) -> google_oauth.TokenSet:
        """The stored token set, refreshed (and persisted back) if expired."""
        try:
            account = json.loads(account_raw)
            current = google_oauth.TokenSet.from_dict(account)
        except (ValueError, KeyError) as exc:
            raise ProviderError(f"bad stored account token: {exc}") from exc
        if not current.expired:
            return current

        client = ctx.http_client
        if client is None:
            raise ProviderError("no http client available to refresh token")
        try:
            tokens = await google_oauth.ensure_fresh(
                client, account=account, client_id=client_id, client_secret=client_secret
            )
        except google_oauth.OAuthError as exc:
            raise ProviderError(f"token refresh failed: {exc}") from exc
        if tokens.access_token != account.get("access_token"):
            ctx.set_secret("google_calendar_account", json.dumps({**account, **tokens.as_dict()}))
        return tokens

    async def _google_events(
        self,
        ctx: ProviderContext,
        source: dict[str, Any],
        tokens: google_oauth.TokenSet,
        *,
        time_min: str,
        time_max: str,
    ) -> list[dict[str, Any]]:
        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": str(_MAX_EVENTS_PER_CALENDAR),
        }
        query = urllib.parse.urlencode(params)
        calendar_path = urllib.parse.quote(source["calendarId"], safe="")
        full_url = f"{_EVENTS_URL.format(calendar_id=calendar_path)}?{query}"
        try:
            response = await ctx.fetch_json(
                full_url,
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                allow_hosts=["www.googleapis.com"],
            )
        except ProviderError:
            logger.warning("calendar %s: fetch failed, skipping this poll", source["calendarId"])
            return []
        events = []
        for raw in response.get("items", []) if isinstance(response, dict) else []:
            if raw.get("status") == "cancelled":
                continue
            events.append(
                _google_event_view(
                    raw,
                    source_label=source.get("label") or source["calendarId"],
                    source_color=source.get("color"),
                )
            )
        return events

    async def _apple_events(
        self,
        ctx: ProviderContext,
        source: dict[str, Any],
        *,
        apple_id: str,
        password: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[dict[str, Any]]:
        client = ctx.http_client
        if client is None:
            raise ProviderError("no http client available for CalDAV")
        try:
            blobs = await caldav_client.fetch_event_blobs(
                client,
                calendar_href=source["calendarId"],
                apple_id=apple_id,
                app_specific_password=password,
                time_min=time_min,
                time_max=time_max,
            )
        except caldav_client.CalDavError as exc:
            logger.warning("apple calendar %s: fetch failed: %s", source["calendarId"], exc)
            return []
        return _ics_events(blobs, source, time_min=time_min, time_max=time_max)

    async def _link_events(
        self,
        ctx: ProviderContext,
        source: dict[str, Any],
        links: dict[str, CalendarLink],
        *,
        time_min: datetime,
        time_max: datetime,
    ) -> list[dict[str, Any]]:
        link = links.get(source["calendarId"])
        client = ctx.http_client
        if link is None or client is None:
            return []
        try:
            blob = await fetch_link(client, link.url)
        except CalendarLinkError as exc:
            logger.warning("calendar link %s: %s", link.label, exc)
            return []
        return _ics_events([blob], source, time_min=time_min, time_max=time_max)

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        google_account_raw = ctx.secret("google_calendar_account")
        google_client_id = ctx.secret("google_calendar_client_id")
        google_client_secret = ctx.secret("google_calendar_client_secret")
        google_ready = bool(google_account_raw and google_client_id and google_client_secret)

        apple_id, apple_password = _apple_credentials(ctx)
        apple_ready = apple_id is not None and apple_password is not None

        links = load_links(ctx.secret("calendar_links"))
        if not google_ready and not apple_ready and not links:
            return None  # nothing connected yet

        sources = [
            s
            for s in (ctx.card_setting("calendar", "sources") or [])
            if isinstance(s, dict) and s.get("selected") and s.get("calendarId")
        ]
        view = ctx.card_setting("calendar", "view")
        meta = {
            "view": view if view in _VIEWS else "week",
            "maxEvents": int(ctx.card_setting("calendar", "maxEvents") or 6),
        }
        now = datetime.now(UTC)
        if not sources:
            return {"events": [], "asOf": now.isoformat(), **meta}

        time_min_dt = now - _LOOKBACK
        time_max_dt = now + _LOOKAHEAD
        time_min = time_min_dt.replace(microsecond=0).isoformat()
        time_max = time_max_dt.replace(microsecond=0).isoformat()

        google_tokens: google_oauth.TokenSet | None = None
        events: list[dict[str, Any]] = []
        for source in sources:
            source_type = source.get("type", "google")
            if source_type == "ics":
                events.extend(
                    await self._link_events(
                        ctx, source, links, time_min=time_min_dt, time_max=time_max_dt
                    )
                )
            elif source_type == "apple":
                if not apple_ready:
                    continue
                assert apple_id is not None and apple_password is not None
                events.extend(
                    await self._apple_events(
                        ctx,
                        source,
                        apple_id=apple_id,
                        password=apple_password,
                        time_min=time_min_dt,
                        time_max=time_max_dt,
                    )
                )
            else:
                if not google_ready:
                    continue
                if google_tokens is None:
                    assert google_account_raw and google_client_id and google_client_secret
                    google_tokens = await self._valid_google_tokens(
                        ctx,
                        account_raw=google_account_raw,
                        client_id=google_client_id,
                        client_secret=google_client_secret,
                    )
                events.extend(
                    await self._google_events(
                        ctx, source, google_tokens, time_min=time_min, time_max=time_max
                    )
                )

        if not ctx.card_setting("calendar", "showDeclined"):
            events = [e for e in events if not e["declined"]]
        events.sort(key=lambda e: e["start"] or "")
        return {"events": events, "asOf": now.isoformat(), **meta}
