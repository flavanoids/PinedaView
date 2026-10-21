# SPDX-License-Identifier: Apache-2.0
"""Settings → Connect: every outside service the display talks to, whether
it's hooked up, and the forms that hook it up.

An install that was set up by hand (``config.toml``, secrets PUT over the
API) shows as connected here as-is — this reads the same settings the rest of
the server runs on. What it writes goes to the secret store (accounts) or
``connections.json`` (this machine's addresses, see
:mod:`pinedaview.connections`); ``config.toml`` is never rewritten.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from pinedaview import caldav_client, google_oauth
from pinedaview.api import (
    RuntimeDep,
    _broadcast_view_change,
    _existing_calendar_selection,
)
from pinedaview.calendar_links import (
    CalendarLink,
    CalendarLinkError,
    calendar_name,
    dump_links,
    fetch_link,
    load_links,
    new_link_id,
    normalize_url,
)
from pinedaview.connections import save_connection
from pinedaview.runtime import Runtime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connect")

_CHECK_TIMEOUT = 3.0
"""A reachability check sits between Settings opening and showing its rows;
anything slower than this is as good as down."""


class ConnectionStatus(BaseModel):
    id: str
    name: str
    group: Literal["calendars", "home", "music", "maps"]
    connected: bool
    detail: str | None = None
    """Who or where it's connected to: an account, a host, a count."""
    problem: str | None = None
    """Set up, but not working right now — and why."""
    values: dict[str, Any] = Field(default_factory=dict)
    """The current non-secret settings, to prefill the form."""
    available: bool = True
    """False when it can't be connected from here yet (Google before its
    one-time Cloud setup)."""


class CalendarChoice(BaseModel):
    id: str
    name: str
    color: str | None = None
    selected: bool = False


class AppleCalendarConnect(BaseModel):
    apple_id: str
    password: str


class CalendarLinkAdd(BaseModel):
    url: str
    label: str | None = None


class HomeAssistantConnect(BaseModel):
    url: str
    token: str


class MqttConnect(BaseModel):
    host: str
    port: int = Field(1883, ge=1, le=65535)


class AntiguaConnect(BaseModel):
    url: str
    fallback_url: str | None = None


class CamerasConnect(BaseModel):
    go2rtc: str


def _json_secret(runtime: Runtime, name: str) -> dict[str, Any]:
    raw = runtime.secrets.get(name)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _base(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


def _changed(runtime: Runtime) -> None:
    runtime.resolve_cards()
    _broadcast_view_change(runtime, "secret")


# ── checks ───────────────────────────────────────────────────────────────────


async def _reach(http: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
    try:
        return await http.get(url, timeout=_CHECK_TIMEOUT, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"Couldn't reach {url}: {exc}") from exc


async def _home_assistant_info(http: httpx.AsyncClient, url: str, token: str) -> dict[str, Any]:
    res = await _reach(http, f"{url}/api/config", headers={"Authorization": f"Bearer {token}"})
    if res.status_code == 401:
        raise HTTPException(status_code=400, detail="Home Assistant didn't accept that token.")
    if res.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Home Assistant answered {res.status_code}.")
    try:
        info: dict[str, Any] = res.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="That isn't a Home Assistant.") from exc
    return info


async def _antigua_check(http: httpx.AsyncClient, url: str) -> None:
    res = await _reach(http, f"{url}/alarms")
    # 503 is Antigua saying its fallback has the alarms — it's there.
    if res.status_code not in (200, 503):
        raise HTTPException(status_code=400, detail=f"Antigua answered {res.status_code}.")


async def _go2rtc_streams(http: httpx.AsyncClient, url: str) -> int:
    res = await _reach(http, f"{url}/api/streams")
    if res.status_code != 200:
        raise HTTPException(status_code=400, detail=f"go2rtc answered {res.status_code}.")
    try:
        return len(res.json())
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="That isn't a go2rtc server.") from None


async def _problem(check: Any) -> str | None:
    try:
        await check
    except HTTPException as exc:
        return str(exc.detail)
    return None


async def _no_problem() -> None:
    return None


# ── status ───────────────────────────────────────────────────────────────────


async def _statuses(runtime: Runtime) -> list[ConnectionStatus]:
    settings = runtime.settings
    secrets = runtime.secrets
    http = runtime.http
    sources = runtime.card_settings.get("calendar", {}).get("sources", [])

    def shown(kind: str) -> int:
        return sum(
            1
            for s in sources
            if isinstance(s, dict) and s.get("selected") and s.get("type", "google") == kind
        )

    apple = _json_secret(runtime, "apple_calendar_account")
    google = _json_secret(runtime, "google_calendar_account")
    google_ready = bool(
        secrets.get("google_calendar_client_id")
        and secrets.get("google_calendar_client_secret")
        and settings.calendar.bounce_url
    )
    links = load_links(secrets.get("calendar_links"))
    hass = _json_secret(runtime, "home_assistant")
    antigua = settings.antigua
    cams = settings.cameras
    mqtt_cfg = settings.mqtt

    hass_check = (
        _problem(_home_assistant_info(http, hass["url"], hass["token"]))
        if hass.get("url") and hass.get("token")
        else _no_problem()
    )
    antigua_check = _problem(_antigua_check(http, antigua.url)) if antigua.url else _no_problem()
    cams_check = _problem(_go2rtc_streams(http, cams.go2rtc)) if cams.streams else _no_problem()
    hass_problem, antigua_problem, cams_problem = await asyncio.gather(
        hass_check, antigua_check, cams_check
    )

    mqtt_problem = None
    if mqtt_cfg.enabled and runtime.mqtt is not None and not runtime.mqtt.connected:
        mqtt_problem = runtime.mqtt.last_error or "Not connected yet."

    def calendars_detail(account: str | None, count: int) -> str | None:
        if not account:
            return None
        return f"{account}, {count} shown" if count else f"{account}, none shown yet"

    return [
        ConnectionStatus(
            id="apple-calendar",
            name="Apple Calendar",
            group="calendars",
            connected=bool(apple),
            detail=calendars_detail(apple.get("appleId"), shown("apple")),
        ),
        ConnectionStatus(
            id="google-calendar",
            name="Google Calendar",
            group="calendars",
            connected=bool(google),
            detail=calendars_detail(google.get("email"), shown("google")),
            available=google_ready or bool(google),
        ),
        ConnectionStatus(
            id="calendar-links",
            name="Calendar links",
            group="calendars",
            connected=bool(links),
            detail=", ".join(link.label for link in links.values()) or None,
        ),
        ConnectionStatus(
            id="home-assistant",
            name="Home Assistant",
            group="home",
            connected=bool(hass),
            detail=hass.get("location_name") or hass.get("url"),
            problem=hass_problem,
            values={"url": hass.get("url")},
        ),
        ConnectionStatus(
            id="antigua",
            name="Antigua",
            group="home",
            connected=bool(antigua.url),
            detail=antigua.url,
            problem=antigua_problem,
            values={"url": antigua.url, "fallback_url": antigua.fallback_url},
        ),
        ConnectionStatus(
            id="cameras",
            name="Cameras",
            group="home",
            connected=bool(cams.streams),
            detail=(
                f"{len(cams.streams)} {'camera' if len(cams.streams) == 1 else 'cameras'}"
                f" through {cams.go2rtc}"
                if cams.streams
                else None
            ),
            problem=cams_problem,
            values={"go2rtc": cams.go2rtc},
        ),
        ConnectionStatus(
            id="airplay",
            name="AirPlay now playing",
            group="music",
            connected=mqtt_cfg.enabled,
            detail=f"{mqtt_cfg.host}:{mqtt_cfg.port}" if mqtt_cfg.enabled else None,
            problem=mqtt_problem,
            values={"host": mqtt_cfg.host, "port": mqtt_cfg.port},
        ),
        ConnectionStatus(
            id="google-maps",
            name="Google Maps",
            group="maps",
            connected=secrets.get("google_maps") is not None,
        ),
    ]


@router.get("")
async def list_connections(runtime: RuntimeDep) -> list[ConnectionStatus]:
    return await _statuses(runtime)


# ── calendars ────────────────────────────────────────────────────────────────


def _choices(runtime: Runtime, calendars: list[dict[str, Any]]) -> list[CalendarChoice]:
    selection = _existing_calendar_selection(runtime)
    return [
        CalendarChoice(
            id=str(c["id"]),
            name=str(c.get("summary") or c["id"]),
            color=c.get("backgroundColor"),
            selected=selection.get(str(c["id"]), False),
        )
        for c in calendars
    ]


async def _apple_calendars(runtime: Runtime, apple_id: str, password: str) -> list[CalendarChoice]:
    try:
        found = await caldav_client.discover_calendars(
            runtime.http, apple_id=apple_id, app_specific_password=password
        )
    except caldav_client.CalDavError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _choices(runtime, caldav_client.as_dict(found))


@router.put("/apple-calendar")
async def connect_apple_calendar(
    body: AppleCalendarConnect, runtime: RuntimeDep
) -> list[CalendarChoice]:
    choices = await _apple_calendars(runtime, body.apple_id.strip(), body.password.strip())
    runtime.secrets.set(
        "apple_calendar_account",
        json.dumps({"appleId": body.apple_id.strip(), "password": body.password.strip()}),
    )
    _changed(runtime)
    return choices


@router.get("/apple-calendar/calendars")
async def apple_calendar_choices(runtime: RuntimeDep) -> list[CalendarChoice]:
    account = _json_secret(runtime, "apple_calendar_account")
    if not account:
        raise HTTPException(status_code=404, detail="Apple Calendar isn't connected.")
    return await _apple_calendars(runtime, account["appleId"], account["password"])


@router.get("/google-calendar/calendars")
async def google_calendar_choices(runtime: RuntimeDep) -> list[CalendarChoice]:
    account = _json_secret(runtime, "google_calendar_account")
    client_id = runtime.secrets.get("google_calendar_client_id")
    client_secret = runtime.secrets.get("google_calendar_client_secret")
    if not account or not client_id or not client_secret:
        raise HTTPException(status_code=404, detail="Google Calendar isn't connected.")
    try:
        tokens = await google_oauth.ensure_fresh(
            runtime.http, account=account, client_id=client_id, client_secret=client_secret
        )
        calendars = await google_oauth.fetch_calendar_list(
            runtime.http, access_token=tokens.access_token
        )
    except google_oauth.OAuthError as exc:
        raise HTTPException(
            status_code=400, detail="Google stopped accepting this connection. Connect again."
        ) from exc
    if tokens.access_token != account.get("access_token"):
        runtime.secrets.set("google_calendar_account", json.dumps({**account, **tokens.as_dict()}))
    return _choices(runtime, calendars)


@router.get("/calendar-links")
async def list_calendar_links(runtime: RuntimeDep) -> list[CalendarChoice]:
    links = load_links(runtime.secrets.get("calendar_links"))
    return _choices(
        runtime,
        [{"id": k, "summary": v.label, "backgroundColor": v.color} for k, v in links.items()],
    )


@router.post("/calendar-links")
async def add_calendar_link(body: CalendarLinkAdd, runtime: RuntimeDep) -> CalendarChoice:
    url = normalize_url(body.url)
    if not url.startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Paste the whole link, starting https://")
    try:
        blob = await fetch_link(runtime.http, url)
    except CalendarLinkError as exc:
        raise HTTPException(status_code=400, detail=f"That link didn't work: {exc}.") from exc
    links = load_links(runtime.secrets.get("calendar_links"))
    label = (body.label or "").strip() or calendar_name(blob) or "Calendar"
    link = CalendarLink(id=new_link_id(), label=label, url=url)
    links[link.id] = link
    runtime.secrets.set("calendar_links", dump_links(links))
    # A link you just pasted is one you want to see.
    calendar = runtime.card_settings.setdefault("calendar", {})
    calendar["sources"] = [
        *calendar.get("sources", []),
        {"calendarId": link.id, "label": label, "color": None, "selected": True, "type": "ics"},
    ]
    runtime.save_card_settings()
    _changed(runtime)
    return CalendarChoice(id=link.id, name=label, selected=True)


@router.delete("/calendar-links/{link_id}", status_code=204)
async def remove_calendar_link(link_id: str, runtime: RuntimeDep) -> Response:
    links = load_links(runtime.secrets.get("calendar_links"))
    if links.pop(link_id, None) is None:
        raise HTTPException(status_code=404, detail="No such calendar link.")
    if links:
        runtime.secrets.set("calendar_links", dump_links(links))
    else:
        runtime.secrets.delete("calendar_links")
    calendar = runtime.card_settings.setdefault("calendar", {})
    calendar["sources"] = [
        s
        for s in calendar.get("sources", [])
        if not (isinstance(s, dict) and s.get("calendarId") == link_id)
    ]
    runtime.save_card_settings()
    _changed(runtime)
    return Response(status_code=204)


# ── home ─────────────────────────────────────────────────────────────────────


@router.put("/home-assistant", status_code=204)
async def connect_home_assistant(body: HomeAssistantConnect, runtime: RuntimeDep) -> Response:
    url = _base(body.url)
    token = body.token.strip()
    info = await _home_assistant_info(runtime.http, url, token)
    runtime.secrets.set(
        "home_assistant",
        json.dumps({"url": url, "token": token, "location_name": info.get("location_name")}),
    )
    _changed(runtime)
    return Response(status_code=204)


@router.delete("/home-assistant", status_code=204)
async def disconnect_home_assistant(runtime: RuntimeDep) -> Response:
    runtime.secrets.delete("home_assistant")
    _changed(runtime)
    return Response(status_code=204)


@router.put("/antigua", status_code=204)
async def connect_antigua(body: AntiguaConnect, runtime: RuntimeDep) -> Response:
    url = _base(body.url)
    await _antigua_check(runtime.http, url)
    fallback = _base(body.fallback_url) if body.fallback_url and body.fallback_url.strip() else None
    save_connection(runtime.settings, "antigua", {"url": url, "fallback_url": fallback})
    _changed(runtime)
    return Response(status_code=204)


@router.delete("/antigua", status_code=204)
async def disconnect_antigua(runtime: RuntimeDep) -> Response:
    save_connection(runtime.settings, "antigua", {"url": None, "fallback_url": None})
    _changed(runtime)
    return Response(status_code=204)


@router.put("/cameras", status_code=204)
async def connect_cameras(body: CamerasConnect, runtime: RuntimeDep) -> Response:
    url = _base(body.go2rtc)
    await _go2rtc_streams(runtime.http, url)
    save_connection(runtime.settings, "cameras", {"go2rtc": url})
    _changed(runtime)
    return Response(status_code=204)


# ── music ────────────────────────────────────────────────────────────────────


@router.put("/airplay", status_code=204)
async def connect_airplay(body: MqttConnect, runtime: RuntimeDep) -> Response:
    host = body.host.strip()
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, body.port), _CHECK_TIMEOUT
        )
    except (OSError, TimeoutError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Nothing answered at {host}:{body.port}."
        ) from exc
    writer.close()
    save_connection(runtime.settings, "mqtt", {"enabled": True, "host": host, "port": body.port})
    await runtime.reconnect_mqtt()
    _changed(runtime)
    return Response(status_code=204)


@router.delete("/airplay", status_code=204)
async def disconnect_airplay(runtime: RuntimeDep) -> Response:
    save_connection(runtime.settings, "mqtt", {"enabled": False})
    await runtime.reconnect_mqtt()
    _changed(runtime)
    return Response(status_code=204)
