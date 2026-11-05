# SPDX-License-Identifier: Apache-2.0
"""The HTTP + SSE API.

Everything a client needs: the per-device view model, a live stream of it, and
the handful of writes a remote makes (config, theme, playback, timers, pairing).
The pydantic models here and in :mod:`pinedaview.view` are the frozen v0 wire
contract — see ``docs/DECISIONS.md`` 0009.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import secrets
import time
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from pydantic import BaseModel, Field
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pinedaview import __version__, alarms, caldav_client, google_oauth
from pinedaview.alarms import Alarm, AlarmRequest, AlarmSwitch, AntiguaError
from pinedaview.cards.manifest import Setting, Slots
from pinedaview.config import Units, load_settings
from pinedaview.connect_page import (
    render_apple_form,
    render_error,
    render_not_configured,
    render_picker,
)
from pinedaview.control import (
    ControlError,
    PinGate,
    restart_display,
    restart_system,
    rotate,
    rotation,
    snapshot,
)
from pinedaview.household import DateStyle, GuestUploads, HouseholdPrefs, TimeFormat
from pinedaview.image_proxy import ImageFetchError, Size
from pinedaview.logging_config import request_id
from pinedaview.mcp_server import build_mcp, mcp_app
from pinedaview.menu_page import MENU_HTML
from pinedaview.now_showing import NowShowingReport, ScreenLook, ScreenLookReport
from pinedaview.observability import health_report, render_metrics, render_status_page
from pinedaview.photos import DuplicatePhotoError, Photo, TooLongError
from pinedaview.providers.news import NEWS_CACHE
from pinedaview.providers.news import valid_id as valid_news_id
from pinedaview.providers.traffic_cams import CAM_CACHE, valid_file
from pinedaview.recipes import RecipeBox, RecipeFavorite, RecipeShown
from pinedaview.registry import (
    SCREEN_COLOURS,
    CircleStack,
    Device,
    Grid,
    GridItem,
    LayoutSnapshot,
    Pace,
    PhotoClock,
    PhotoFit,
    PhotoOrderSetting,
    Popups,
    Profile,
)
from pinedaview.runtime import Runtime, build_runtime
from pinedaview.setup import detect_location, write_config
from pinedaview.standby import PAGES as STANDBY_PAGES
from pinedaview.standby import Standby, is_saving_write
from pinedaview.state import DisplayState
from pinedaview.system import HostStats, local_stats
from pinedaview.takeover import (
    AlarmTakeover,
    CameraTakeover,
    PictureCard,
    Takeover,
    TakeoverRequest,
    TakeoverUpdate,
)
from pinedaview.themes import (
    FONTS,
    CustomColours,
    FontSetting,
    Theme,
    all_themes,
    custom_rev,
    custom_theme,
    find_theme,
    load_file_themes,
    set_custom_themes,
    set_file_themes,
)
from pinedaview.timers import SyncedTimer, Timer
from pinedaview.updates import UpdateStatus, get_update_status, run_update
from pinedaview.upload_page import UPLOAD_HTML
from pinedaview.view import PROTOCOL_VERSION, ViewModel, build_view_model
from pinedaview.webroot import mount_web, webroot_dir

logger = logging.getLogger(__name__)

_HEARTBEAT_SECONDS = 15.0

# Fire-and-forget tasks (photo cutouts), held so they aren't garbage-collected.
_background: set[asyncio.Task[None]] = set()


# ── request / response models ────────────────────────────────────────────────


class Health(BaseModel):
    status: str = "ok"
    version: str = PROTOCOL_VERSION
    """The frozen wire-protocol version (see DECISIONS 0009), not the release."""
    app_version: str
    """The running server's release version (SemVer)."""
    providers: list[str]
    subscribers: int
    cards_ready: int
    cards_total: int
    ok: bool = True
    """False when a deep check failed (the database). A degraded server still
    answers 200 on the shallow fields; ``GET /api/health`` returns 503."""
    uptime_s: float = 0.0
    checks: dict[str, str] = Field(default_factory=dict)


class CardView(BaseModel):
    id: str
    name: str
    description: str
    status: Literal["ready", "blocked"]
    reason: str | None
    provides: list[str]
    needs: list[str]
    slots: Slots
    settings: dict[str, Setting]
    tier_min: str
    has_provider: bool
    detail: bool


class CardSettings(BaseModel):
    values: dict[str, Any]


class SecretList(BaseModel):
    names: list[str]


class SecretValue(BaseModel):
    value: str


class CalendarSource(BaseModel):
    calendarId: str
    label: str
    color: str | None = None
    selected: bool = False
    type: Literal["google", "apple", "ics"] = "google"


class CalendarSourcesUpdate(BaseModel):
    sources: list[CalendarSource]


class CalendarAccountView(BaseModel):
    connected: bool
    email: str | None = None


class AppleCalendarAccountView(BaseModel):
    connected: bool
    apple_id: str | None = None


HHMM = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
"""A local wall-clock time, "07:30"."""
OptionalHHMM = Annotated[str, Field(pattern=r"^(([01]\d|2[0-3]):[0-5]\d)?$")]
"""A time, or "" to clear it."""
HexColour = Annotated[str, Field(pattern=r"^(#[0-9a-fA-F]{6})?$")]
ClockTint = Annotated[str, Field(pattern=r"^(auto|#[0-9a-fA-F]{6})?$")]
"""``#rrggbb``, or "" to clear it."""


class ConfigView(BaseModel):
    units: Units
    theme: str
    location_query: str
    location_label: str | None
    countdown_enabled: bool
    countdown_start: str
    countdown_end: str
    setup_complete: bool
    time_format: TimeFormat = "12h"
    date_style: DateStyle = "long"
    guest_uploads: GuestUploads = "open"


class DetectedLocationView(BaseModel):
    label: str
    query: str
    latitude: float | None
    longitude: float | None


class ConfigUpdate(BaseModel):
    units: Units | None = None
    theme: str | None = None
    location_query: str | None = None
    location_label: str | None = None
    countdown_enabled: bool | None = None
    countdown_start: HHMM | None = None
    countdown_end: HHMM | None = None
    time_format: TimeFormat | None = None
    date_style: DateStyle | None = None
    guest_uploads: GuestUploads | None = None


class ThemeList(BaseModel):
    current: str
    themes: list[Theme]


class SystemView(BaseModel):
    server: HostStats
    screen: HostStats | None = None
    """The screen's Pi, from its last MQTT report; None until one arrives."""


class ThemeApply(BaseModel):
    name: str


class PhotoOrder(BaseModel):
    names: list[str]


class PairRequest(BaseModel):
    name: str = "New screen"
    viewport_w: int | None = None
    viewport_h: int | None = None
    kind: str | None = Field(default=None, max_length=40)
    """What the browser is ("iPad", "Android tablet", …; web lib/device)."""


Shows = Literal["photo", "cameras", "cards", "mix"]
"""What a screen shows, as the phone menu's Screens page offers it."""


class KeepRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    colour: str
    shows: Shows


class ShowsRequest(BaseModel):
    shows: Shows


class ReplaceRequest(BaseModel):
    old: str
    """The kept screen this one is the same tablet as."""


class ScreenView(Device):
    """A device as the phone menu lists it."""

    online: bool = False
    home: bool = False
    """The kiosk (``[control] screen``): set up already, never removed."""


# Mirrors FACES in web/src/lib/clockface.svelte.ts; "" clears the push.
ClockFaceSetting = Literal[
    "",
    "stack",
    "words",
    "poster",
    "flip",
    "seg",
    "analog",
    "contour",
    "bulge",
    "qlock",
]


class DeviceUpdate(BaseModel):
    name: str | None = None
    profile_id: str | None = None
    tier: str | None = None
    card_stack: list[str] | None = None
    layout: str | None = None
    locked: bool | None = None
    follow: str | None = None
    brightness: float | None = Field(default=None, ge=0.1, le=1.0)
    blackout_start: OptionalHHMM | None = None
    blackout_end: OptionalHHMM | None = None
    hero_card: str | None = None
    cards_off: list[str] | None = None
    night_clock: bool | None = None
    night_clock_hold: bool | None = None
    alternate: bool | None = None
    night_clock_font: FontSetting | None = None
    """The night clock's typeface, or "" for its own."""
    night_clock_color: HexColour | None = None
    """The night clock's colour, or "" for its own."""
    night_clock_photo: bool | None = None
    night_clock_tint: ClockTint | None = None
    """The Photo Clock's glass tint: #rrggbb, "auto", or "" for clear."""
    photo_clock: PhotoClock | None = None
    """The Photo Clock's font, size and glass, all at once."""
    night_weeknight_start: HHMM | None = None
    night_weekend_start: HHMM | None = None
    night_end: HHMM | None = None
    night_weekend_end: OptionalHHMM | None = None
    """When the dashboard comes back at the weekend, or "" for night_end."""
    peek_s: int | None = Field(default=None, ge=10, le=600)
    dim_start: OptionalHHMM | None = None
    dim_end: OptionalHHMM | None = None
    dim_level: float | None = Field(default=None, ge=0.1, le=1.0)
    shape: Literal["rect", "circle"] | None = None
    circle_stack: CircleStack | None = None
    """The round face's cards in slot order, or [] for the default."""
    frame_inset: int | None = Field(default=None, ge=0, le=20)
    dynamic_shuffle: bool | None = None
    shuffle_hold_s: int | None = Field(default=None, ge=5, le=300)
    ambient_cycle_m: int | None = Field(default=None, ge=1, le=120)
    popups: Popups | None = None


class RotationBody(BaseModel):
    """The kiosk screen's direction: "normal", or the picture turned 90,
    180 or 270 degrees (wlr-randr's names)."""

    rotation: Literal["normal", "90", "180", "270"]


class ViewportUpdate(BaseModel):
    w: int = Field(ge=100, le=10000)
    h: int = Field(ge=100, le=10000)


class GridUpdate(BaseModel):
    grid: Grid | None
    """The new hand-placed layout, or null to go back to the automatic one."""


class ProfileUpdate(BaseModel):
    name: str | None = None
    layout: str | None = None
    theme: str | None = None
    card_stack: list[str] | None = None
    hero_card: str | None = None
    clock_face: ClockFaceSetting | None = None
    """One of the SPA's clock faces, or "" to stop pushing one."""
    animated_background: bool | None = None
    font: FontSetting | None = None
    """The typeface for everything but the clock, or "" for the theme's own."""
    pace: Pace | None = None
    photo_hold_s: int | None = Field(default=None, ge=5, le=3600)
    photo_order: PhotoOrderSetting | None = None
    photo_fit: PhotoFit | None = None
    night_theme: str | None = None
    """A theme name, "off" to keep the day theme, or "" for the theme's own."""
    accent: HexColour | None = None
    wallpaper_everywhere: bool | None = None
    hide_words: list[Annotated[str, Field(min_length=1, max_length=60)]] | None = Field(
        default=None, max_length=50
    )
    dynamic_shuffle: bool | None = None
    shuffle_hold_s: int | None = Field(default=None, ge=5, le=300)
    ambient_cycle_m: int | None = Field(default=None, ge=1, le=120)


class ResetRequest(BaseModel):
    section: ResetSection
    profile_id: str | None = None
    device_id: str | None = None


class CopyScreenRequest(BaseModel):
    source: str
    """The screen whose settings to copy onto this one."""


class Backup(BaseModel):
    """Everything Settings can change, as one file — photos, keys and the
    server's own config.toml aside."""

    format: Literal["pineda-settings"] = "pineda-settings"
    version: Literal[1] = 1
    exported_at: datetime
    app_version: str
    config: ConfigUpdate
    profiles: list[Profile]
    devices: list[Device]
    card_settings: dict[str, dict[str, Any]]
    custom_themes: list[Theme]


class RestoreSummary(BaseModel):
    profiles: int
    screens: int
    skipped_screens: int
    """Screens in the file this server has never paired with."""


class ProfileCreate(BaseModel):
    name: str
    copy_from: str | None = None


class StateRequest(BaseModel):
    playing: bool | None = None
    forced: DisplayState | None = None


class TimerRequest(BaseModel):
    seconds: float = Field(gt=0)
    label: str = "Timer"
    kind: Literal["timer", "alarm"] = "timer"
    name: str | None = Field(default=None, max_length=60)


class TimerSync(BaseModel):
    timers: list[SyncedTimer]


class ShownPhoto(BaseModel):
    name: str
    since: datetime
    taken_local: str | None
    """The camera's own clock (EXIF), as naive ISO local time — no zone is
    known, so don't convert it. None when the photo has no EXIF date."""


class ShownQuote(BaseModel):
    text: str
    author: str | None
    year: int | None
    since: datetime


class DailyPhrase(BaseModel):
    english: str
    spanish: str | None
    pron: str | None
    note: str | None


class NowShowingView(BaseModel):
    photo: ShownPhoto | None
    quote: ShownQuote | None
    phrase: DailyPhrase | None
    look: ScreenLook | None = None
    """How the named screen draws itself (its own clock face, Pi mode, text
    scale), when it has said; None without a device_id."""


# ── helpers ──────────────────────────────────────────────────────────────────


def get_runtime(request: Request) -> Runtime:
    runtime: Runtime = request.app.state.runtime
    return runtime


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]


def _tidy_words(words: list[str]) -> list[str]:
    """Trimmed, de-duplicated (case-blind), in the order given."""
    seen: set[str] = set()
    kept: list[str] = []
    for word in (w.strip() for w in words):
        if word and word.lower() not in seen:
            seen.add(word.lower())
            kept.append(word)
    return kept


# What "Reset to defaults" puts back, per Settings section. Location, the
# theme, names and layouts are never touched — only the preferences.
_RESET_PROFILE: dict[str, tuple[str, ...]] = {
    "appearance": (
        "font",
        "animated_background",
        "accent",
        "night_theme",
        "wallpaper_everywhere",
        "clock_face",
    ),
    "cards": (
        "pace",
        "hero_card",
        "hide_words",
        "dynamic_shuffle",
        "shuffle_hold_s",
        "ambient_cycle_m",
    ),
    "photos": ("photo_hold_s", "photo_order", "photo_fit"),
}
_RESET_DEVICE: dict[str, tuple[str, ...]] = {
    "cards": (
        "cards_off",
        "hero_card",
        "dynamic_shuffle",
        "shuffle_hold_s",
        "ambient_cycle_m",
    ),
    "night": (
        "night_clock",
        "night_clock_hold",
        "alternate",
        "night_clock_font",
        "night_clock_color",
        "night_clock_photo",
        "night_clock_tint",
        "photo_clock",
        "night_weeknight_start",
        "night_weekend_start",
        "night_end",
        "night_weekend_end",
        "peek_s",
        "dim_start",
        "dim_end",
        "dim_level",
        "blackout_start",
        "blackout_end",
    ),
}
_RESET_HOUSEHOLD: dict[str, tuple[str, ...]] = {
    "time": ("time_format", "date_style"),
    "photos": ("guest_uploads",),
}
ResetSection = Literal["appearance", "time", "cards", "photos", "night"]

# A screen's own settings that "Copy from another screen" carries over —
# not its name, lock, mirror target, or anything the browser reports.
_COPYABLE_DEVICE = (
    "profile_id",
    "card_stack",
    "layout",
    "brightness",
    "blackout_start",
    "blackout_end",
    "hero_card",
    "cards_off",
    "night_clock",
    "night_clock_hold",
    "alternate",
    "night_clock_font",
    "night_clock_color",
    "night_clock_photo",
    "night_clock_tint",
    "photo_clock",
    "night_weeknight_start",
    "night_weekend_start",
    "night_end",
    "night_weekend_end",
    "peek_s",
    "dim_start",
    "dim_end",
    "dim_level",
    "shape",
    "circle_stack",
    "dynamic_shuffle",
    "shuffle_hold_s",
    "ambient_cycle_m",
)


def _defaults(model: type[BaseModel], fields: tuple[str, ...]) -> dict[str, Any]:
    """Each field's default, with None spelled "" (the registry's "clear")."""
    out: dict[str, Any] = {}
    for name in fields:
        value = model.model_fields[name].get_default(call_default_factory=True)
        out[name] = "" if value is None else value
    return out


def _config_view(runtime: Runtime) -> ConfigView:
    s = runtime.settings
    return ConfigView(
        units=s.units,
        theme=s.theme,
        location_query=s.location.query,
        location_label=s.location.label,
        countdown_enabled=s.countdown.enabled,
        countdown_start=s.countdown.start,
        countdown_end=s.countdown.end,
        setup_complete=s.setup_complete,
        time_format=runtime.household.time_format,
        date_style=runtime.household.date_style,
        guest_uploads=runtime.household.guest_uploads,
    )


def _apply_config(runtime: Runtime, patch: ConfigUpdate) -> None:
    s = runtime.settings
    if patch.units is not None:
        s.units = patch.units
    if patch.theme is not None:
        s.theme = patch.theme
    if patch.location_query is not None:
        if patch.location_query != s.location.query:
            # Coordinates pinned in config.toml belong to the old place.
            s.location.latitude = s.location.longitude = None
        s.location.query = patch.location_query
    if patch.location_label is not None:
        s.location.label = patch.location_label
    if patch.countdown_enabled is not None:
        s.countdown.enabled = patch.countdown_enabled
    if patch.countdown_start is not None:
        s.countdown.start = patch.countdown_start
    if patch.countdown_end is not None:
        s.countdown.end = patch.countdown_end
    household = patch.model_dump(
        include={"time_format", "date_style", "guest_uploads"}, exclude_none=True
    )
    runtime.household = runtime.household.model_copy(update=household)
    runtime.save_household()
    runtime.resolve_cards()


# registry.pair_device's id shape (token_hex(8)) — what a server may adopt.
_DEVICE_ID_RE = re.compile(r"[0-9a-f]{16}")


async def _resolve(runtime: Runtime, device_id: str) -> tuple[Device, Profile]:
    device = await runtime.devices.device(device_id)
    if device is None and _DEVICE_ID_RE.fullmatch(device_id):
        if runtime.settings.api.adopt_unknown_devices:
            device = await runtime.devices.adopt_device(device_id)
        else:
            # A browser holding an id this server forgot: a new screen again.
            device = await runtime.devices.adopt_device(device_id, kept=False)
    if device is None:
        raise HTTPException(status_code=404, detail="unknown device")
    profile = await runtime.devices.profile(device.profile_id)
    if profile is None:  # pragma: no cover - FK guarantees this
        raise HTTPException(status_code=500, detail="device points at a missing profile")
    return device, profile


async def _view_for(runtime: Runtime, device_id: str, *, _depth: int = 0) -> ViewModel:
    device, profile = await _resolve(runtime, device_id)
    if device.follow and device.follow != device_id and _depth == 0:
        with contextlib.suppress(HTTPException):
            mirrored = await _view_for(runtime, device.follow, _depth=1)
            return mirrored.model_copy(update={"device_id": device_id})
    return build_view_model(
        device=device,
        profile=profile,
        settings=runtime.settings,
        stores=runtime.stores,
        state=runtime.state.current(),
        ready_cards=set(runtime.cards.ready_ids()),
        detail_cards={m.id for m in runtime.cards.all() if m.detail},
        wallpaper_rev=runtime.wallpaper.revision(),
        theme_rev=custom_rev(),
        timers=_on_screen(runtime.timers.list()),
        takeover=_popup_for(runtime, device),
        card_settings=runtime.card_settings,
        household=runtime.household,
    )


_ALARM_HORIZON_S = 12 * 3600


def _on_screen(timers: list[Timer]) -> list[Timer]:
    """What the screens show: every timer, and alarms and reminders due in
    the next 12 hours — a weekly one days off would just read "7:00 AM"."""
    now = datetime.now(UTC)
    return [
        t
        for t in timers
        if t.kind == "timer" or (t.fires_at - now).total_seconds() <= _ALARM_HORIZON_S
    ]


def _card_view(runtime: Runtime, manifest: Any) -> CardView:
    status = runtime.cards.status(manifest.id)
    return CardView(
        id=manifest.id,
        name=manifest.name,
        description=manifest.description,
        status="ready" if status.ready else "blocked",
        reason=status.reason,
        provides=manifest.provides,
        needs=manifest.needs,
        slots=manifest.slots,
        settings=manifest.settings,
        tier_min=manifest.tier.min,
        has_provider=manifest.provider is not None,
        detail=manifest.detail,
    )


def _now_showing(runtime: Runtime, device_id: str | None) -> NowShowingView:
    daily = runtime.stores.get("dailyContent")
    snap = daily.snapshot() if daily is not None else None
    content: dict[str, Any] = snap.value if snap is not None else {}

    photo = None
    if shown := runtime.now_showing.get("photo", device_id):
        meta = next((p for p in runtime.photos.all() if p.name == shown.item), None)
        taken = meta.taken_at if meta is not None else None
        photo = ShownPhoto(
            name=shown.item,
            since=shown.since,
            # _extract_taken_at stamps the camera's naive local time as UTC,
            # so reading it back as UTC recovers the camera's wall clock.
            taken_local=(
                datetime.fromtimestamp(taken, UTC).replace(tzinfo=None).isoformat()
                if taken is not None
                else None
            ),
        )

    quote = None
    if shown := runtime.now_showing.get("quote", device_id):
        known: dict[str, Any] = next(
            (q for q in content.get("affirmations", []) if q.get("text") == shown.item), {}
        )
        quote = ShownQuote(
            text=shown.item, author=known.get("author"), year=known.get("year"), since=shown.since
        )

    phrase = None
    # A retired phrase card isn't on any screen, so it isn't "showing".
    if "phrase" not in runtime.settings.disabled_cards and (word := content.get("word")):
        es: dict[str, Any] = next(
            (lang for lang in word.get("languages", []) if lang.get("code") == "es"), {}
        )
        phrase = DailyPhrase(
            english=word.get("english", ""),
            spanish=es.get("text"),
            pron=es.get("pron"),
            note=word.get("note"),
        )
    return NowShowingView(
        photo=photo, quote=quote, phrase=phrase, look=runtime.now_showing.look(device_id)
    )


def _sse(event: str, event_id: int, payload: BaseModel | dict[str, Any]) -> str:
    body = payload.model_dump_json() if isinstance(payload, BaseModel) else json.dumps(payload)
    return f"id: {event_id}\nevent: {event}\ndata: {body}\n\n"


async def _stream(runtime: Runtime, device_id: str) -> AsyncGenerator[str, None]:
    runtime.online[device_id] = runtime.online.get(device_id, 0) + 1
    try:
        async for chunk in _stream_views(runtime, device_id):
            yield chunk
    finally:
        # last_seen is when it was last on: "Off since …" in the phone menu.
        with contextlib.suppress(Exception):
            await runtime.devices.touch(device_id)
        left = runtime.online.get(device_id, 1) - 1
        if left > 0:
            runtime.online[device_id] = left
        else:
            runtime.online.pop(device_id, None)


async def _stream_views(runtime: Runtime, device_id: str) -> AsyncGenerator[str, None]:
    with runtime.broadcaster.subscription() as queue:
        first = await _view_for(runtime, device_id)
        # Most pushes (a provider re-polling the same forecast) rebuild an
        # identical view; skip those so the screen doesn't re-render and
        # rewrite its localStorage copy for nothing. generated_at always differs.
        last = first.model_dump_json(exclude={"generated_at"})
        yield _sse("view", 0, first)
        counter = 1
        cur_update = get_update_status(runtime.settings)
        if cur_update.state == "updating":
            yield _sse("update_status", counter, cur_update)
            counter += 1
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if event.get("type") == "identify" and event.get("deviceId") == device_id:
                yield _sse("identify", counter, event)
                counter += 1
                continue
            if event.get("type") == "identify":
                continue  # for another device
            if event.get("type") == "update_status":
                yield _sse("update_status", counter, event.get("status") or {})
                counter += 1
                continue
            try:
                view = await _view_for(runtime, device_id)
            except HTTPException:
                yield _sse("gone", counter, {"deviceId": device_id})
                return
            same = view.model_dump_json(exclude={"generated_at"})
            if same == last:
                continue
            last = same
            yield _sse("view", counter, view)
            counter += 1


def _popup_for(runtime: Runtime, device: Device) -> Takeover | None:
    """The takeover this screen shows, if its pop-ups setting lets it."""
    takeover = runtime.takeover.current()
    if takeover is None:
        return None
    home = runtime.settings.control.screen
    # Unset: everything on the kiosk (or a lone screen), nothing on tablets.
    popups = device.popups or ("all" if home in (None, device.id) else "none")
    if popups == "all":
        return takeover
    if popups == "cameras" and takeover.card.kind == "camera":
        return takeover
    return None


def _shows_grid(shows: Shows, tall: bool) -> Grid | None:
    """The hand-placed layout behind the Cameras and Mix choices, in the
    layout editor's two-units-a-cell grid so it opens there as drawn."""
    if shows == "cameras":
        return Grid(cols=2, items=[GridItem(card="home-cams", x=0, y=0, w=2, h=2)])
    if shows != "mix":
        return None
    side = ["weather", "clock", "calendar"]
    if tall:  # the cameras across the top, three cards under them
        cams = GridItem(card="home-cams", x=0, y=0, w=6, h=4)
        rest = [GridItem(card=c, x=2 * i, y=4, w=2, h=2) for i, c in enumerate(side)]
        return Grid(cols=6, items=[cams, *rest])
    cams = GridItem(card="home-cams", x=0, y=0, w=4, h=6)
    rest = [GridItem(card=c, x=4, y=2 * i, w=2, h=2) for i, c in enumerate(side)]
    return Grid(cols=6, items=[cams, *rest])


async def _set_shows(runtime: Runtime, device_id: str, shows: Shows) -> Device:
    device = await runtime.devices.device(device_id)
    assert device is not None
    photo = shows == "photo"
    await runtime.devices.update_device(
        device_id,
        night_clock_hold=photo,
        night_clock_photo=photo or device.night_clock_photo,
        alternate=False,
    )
    tall = (device.viewport_h or 0) > (device.viewport_w or 0)
    if not photo:
        await runtime.devices.set_grid(device_id, _shows_grid(shows, tall))
    _broadcast_view_change(runtime, "device")
    updated = await runtime.devices.device(device_id)
    assert updated is not None
    return updated


async def _retire_cards(runtime: Runtime) -> None:
    """Move saved stacks off cards that have been retired."""
    if "phrase" in runtime.settings.disabled_cards:
        # Retired: the traffic cams take its slot (config.disabled_cards).
        moved = await runtime.devices.retire_card("phrase", "traffic", "affirmation")
        if moved:
            logger.info("phrase card retired: traffic cams moved into %d stack(s)", moved)
    if "moon-climate" in runtime.settings.disabled_cards:
        # Retired: the home cameras take its slot (config.disabled_cards).
        moved = await runtime.devices.retire_card("moon-climate", "home-cams", "photo")
        if moved:
            logger.info("moon-climate card retired: home cams moved into %d stack(s)", moved)
    # Retired for good: the news card took its place.
    moved = await runtime.devices.retire_card("did-you-know", "news", "now-playing")
    if moved:
        logger.info("did-you-know card retired: news moved into %d stack(s)", moved)


# ── app ──────────────────────────────────────────────────────────────────────


def create_app(runtime: Runtime | None = None) -> FastAPI:
    runtime = runtime or build_runtime(load_settings())

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await runtime.devices.init()
        set_file_themes(load_file_themes(runtime.settings.themes_dir))
        set_custom_themes(await runtime.devices.custom_themes())
        await _retire_cards(runtime)
        forgotten = await runtime.devices.settle_screens(runtime.settings.control.screen)
        if forgotten:
            logger.info("forgot %d screen(s) nobody set up", forgotten)
        if runtime.mqtt is not None:
            await runtime.mqtt.start()
            runtime.resolve_cards()
        tasks = [
            asyncio.create_task(runtime.scheduler.run(), name="scheduler"),
            asyncio.create_task(runtime.timers.run(), name="timers"),
            asyncio.create_task(runtime.takeover.run(), name="takeover"),
            asyncio.create_task(runtime.cameras.run(), name="cameras"),
            asyncio.create_task(runtime.sun.run(), name="sun"),
            # One-off: display copies for photos added before they existed.
            asyncio.create_task(
                asyncio.to_thread(runtime.photos.backfill_display), name="photo-backfill"
            ),
            asyncio.create_task(
                asyncio.to_thread(runtime.photos.backfill_subjects), name="photo-subject-backfill"
            ),
            asyncio.create_task(
                asyncio.to_thread(runtime.photos.backfill_colours), name="photo-colour-backfill"
            ),
            asyncio.create_task(
                asyncio.to_thread(runtime.photos.backfill_aspects), name="photo-aspect-backfill"
            ),
        ]
        try:
            async with contextlib.AsyncExitStack() as stack:
                if (mcp := getattr(_app.state, "mcp", None)) is not None:
                    await stack.enter_async_context(mcp.session_manager.run())
                yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await runtime.cameras.stop()
            if runtime.mqtt is not None:
                await runtime.mqtt.stop()

    app = FastAPI(title="PinedaDisplay Web", version=PROTOCOL_VERSION, lifespan=lifespan)
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime.settings.api.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _install_middleware(app, runtime)
    if runtime.settings.standby.primary:
        _install_standby(app, runtime, runtime.settings.standby.primary)
    _register(app)
    from pinedaview import connect  # imports this module's helpers

    app.include_router(connect.router)
    if runtime.settings.mcp.enabled:
        _mount_mcp(app, runtime)
    mount_web(app)
    return app


# The admin surface: config, secrets, playback control, setup, and device/profile
# management. The public surface (view, stream, health, metrics, themes, photos,
# the card list) stays open so any screen on the LAN just works.
_ADMIN_PREFIXES = (
    "/api/config",
    "/api/secrets",
    "/api/control",
    "/api/setup",
    "/api/profiles",
    "/api/devices",
    "/api/themes/custom",
    "/api/connect",
)


def _is_public_write(request_or_method: Request | str, path: str | None = None) -> bool:
    """Guest photo drop-off: ``POST /api/photos`` stays open even when a write
    token is set, so anyone on the LAN can scan the card's QR and add a photo.
    Editing and deleting photos still needs the token. The screens' own
    now-showing reports stay open for the same reason: the kiosk has no token."""
    if isinstance(request_or_method, str):
        method = request_or_method
        p = path or ""
    else:
        method = request_or_method.method
        p = request_or_method.url.path
    return method == "POST" and p.rstrip("/") in (
        "/api/photos",
        "/api/now-showing",  # the kiosk's cards report what they show; they hold no token
        "/api/now-showing/look",
    )


def _is_admin_path(path: str) -> bool:
    if path.rstrip("/").endswith("/settings"):
        return True  # /api/cards/{id}/settings
    return path.startswith(_ADMIN_PREFIXES)


class CorrelationIdMiddleware:
    """Stamp every request and response with an X-Request-ID without using
    BaseHTTPMiddleware, which breaks streaming and client disconnects."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = ""
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-request-id":
                rid = value.decode("latin1")
                break
        if not rid:
            rid = uuid4().hex[:12]

        token = request_id.set(rid)

        async def send_with_rid(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["x-request-id"] = rid
            await send(message)

        try:
            await self.app(scope, receive, send_with_rid)
        finally:
            request_id.reset(token)


class AuthMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        write_token: str | None = None,
        admin_token: str | None = None,
    ) -> None:
        self.app = app
        self.write_token = write_token
        self.admin_token = admin_token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        auth_header = ""
        for name, value in scope.get("headers", []):
            if name.lower() == b"authorization":
                auth_header = value.decode("latin1")
                break

        if (
            self.write_token
            and method in ("POST", "PUT", "PATCH", "DELETE")
            and not _is_public_write(method, path)
            and auth_header.removeprefix("Bearer ").strip() != self.write_token
        ):
            resp = Response(
                status_code=401,
                content='{"detail":"write token required"}',
                media_type="application/json",
            )
            await resp(scope, receive, send)
            return

        if (
            self.admin_token
            and _is_admin_path(path)
            and auth_header.removeprefix("Bearer ").strip() != self.admin_token
        ):
            resp = Response(
                status_code=401,
                content='{"detail":"admin token required"}',
                media_type="application/json",
            )
            await resp(scope, receive, send)
            return

        await self.app(scope, receive, send)


class StandbyMiddleware:
    def __init__(self, app: ASGIApp, standby: Standby) -> None:
        self.app = app
        self.standby = standby

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        if method == "GET" and path in STANDBY_PAGES and await self.standby.primary_up():
            query = scope.get("query_string", b"").decode("latin1")
            query_str = f"?{query}" if query else ""
            resp = RedirectResponse(f"{self.standby.primary}{path}{query_str}", status_code=307)
            await resp(scope, receive, send)
            return

        status_code = 200

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if is_saving_write(method, path) and status_code < 400:
            self.standby.mark_changed()


def _install_middleware(app: FastAPI, runtime: Runtime) -> None:
    write_token = runtime.settings.api.write_token
    admin_token = runtime.settings.api.admin_token
    if write_token or admin_token:
        app.add_middleware(AuthMiddleware, write_token=write_token, admin_token=admin_token)
    app.add_middleware(CorrelationIdMiddleware)


def _mount_mcp(app: FastAPI, runtime: Runtime) -> None:
    # The display as an MCP server for Antigua (docs/MCP.md); token-only.
    def saved(reason: str) -> None:
        _broadcast_view_change(runtime, reason)
        if (standby := getattr(app.state, "standby", None)) is not None:
            standby.mark_changed()

    app.state.mcp = build_mcp(runtime, runtime.cameras, _now_showing, saved)
    app.mount("/mcp", mcp_app(app.state.mcp, runtime.settings.mcp))


def _install_standby(app: FastAPI, runtime: Runtime, primary: str) -> None:
    # This box is the backup (see pinedaview.standby): phones go to the
    # primary while it's up, and saving anything here flags it for the sync.
    standby = Standby(primary, runtime.settings.state_dir, lambda: runtime.http)
    app.state.standby = standby
    app.add_middleware(StandbyMiddleware, standby=standby)


def _broadcast_view_change(runtime: Runtime, reason: str) -> None:
    runtime.broadcaster.publish({"type": "config", "reason": reason})


def _existing_calendar_selection(runtime: Runtime) -> dict[str, bool]:
    sources = runtime.card_settings.get("calendar", {}).get("sources", [])
    return {
        s["calendarId"]: bool(s.get("selected"))
        for s in sources
        if isinstance(s, dict) and s.get("calendarId")
    }


def _drop_calendar_sources_of_type(runtime: Runtime, source_type: str) -> None:
    """Disconnecting one backend (Google or Apple) should only remove that
    backend's saved calendars, leaving the other's untouched."""
    kept = [
        s
        for s in runtime.card_settings.get("calendar", {}).get("sources", [])
        if isinstance(s, dict) and s.get("type", "google") != source_type
    ]
    runtime.card_settings["calendar"] = {
        **runtime.card_settings.get("calendar", {}),
        "sources": kept,
    }
    runtime.save_card_settings()


async def _refreshed_picker_html(
    runtime: Runtime, *, client_id: str, client_secret: str
) -> str | None:
    """Re-fetch the connected account's calendar list without a full OAuth
    round trip — lets a newly-shared calendar show up just by revisiting the
    connect page. Returns ``None`` if there's no connected account yet, or the
    refresh itself fails (a revoked token), so the caller can fall back to a
    full reconnect."""
    raw = runtime.secrets.get("google_calendar_account")
    if not raw:
        return None
    try:
        account = json.loads(raw)
        tokens = await google_oauth.ensure_fresh(
            runtime.http, account=account, client_id=client_id, client_secret=client_secret
        )
        calendars = await google_oauth.fetch_calendar_list(
            runtime.http, access_token=tokens.access_token
        )
    except (ValueError, KeyError, google_oauth.OAuthError):
        return None
    if tokens.access_token != account.get("access_token"):
        runtime.secrets.set("google_calendar_account", json.dumps({**account, **tokens.as_dict()}))
    return render_picker(
        email=str(account.get("email") or ""),
        calendars=calendars,
        existing_selection=_existing_calendar_selection(runtime),
    )


def _register(app: FastAPI) -> None:  # noqa: C901 - a flat list of route handlers
    @app.get("/api/health")
    async def health(runtime: RuntimeDep, response: Response) -> Health:
        report = await health_report(runtime)
        if not report["ok"]:
            response.status_code = 503
        return Health(
            app_version=__version__,
            providers=runtime.scheduler.provider_keys,
            subscribers=runtime.broadcaster.subscriber_count,
            cards_ready=len(runtime.cards.ready_ids()),
            cards_total=len(runtime.cards.all()),
            ok=report["ok"],
            uptime_s=report["uptime_s"],
            checks=report["checks"],
        )

    @app.get("/api/metrics", response_class=PlainTextResponse, include_in_schema=False)
    async def metrics(runtime: RuntimeDep) -> str:
        return render_metrics(runtime)

    @app.get("/status", response_class=HTMLResponse, include_in_schema=False)
    async def status_page(runtime: RuntimeDep) -> str:
        return await render_status_page(runtime)

    @app.get("/upload", response_class=HTMLResponse, include_in_schema=False)
    async def upload_page() -> str:
        # The "scan to add photos" page for anyone on the LAN. Uploads land on
        # the public POST /api/photos (see _write_auth exemption).
        return UPLOAD_HTML

    @app.get("/menu", response_class=HTMLResponse, include_in_schema=False)
    async def menu_page() -> str:
        # What the photo card's QR code points at: everything a phone can
        # change about the screen it scanned (``?screen=<device id>``).
        return MENU_HTML

    @app.get("/api/menu-url", include_in_schema=False)
    async def menu_url(request: Request) -> dict[str, str]:
        # A standby names the primary while it's up (see pinedaview.standby).
        standby: Standby | None = getattr(request.app.state, "standby", None)
        if standby is not None and await standby.primary_up():
            return {"url": f"{standby.primary}/menu"}
        # The kiosk loads the dashboard through its local failover proxy
        # (127.0.0.1:8090), so its own origin is useless in a QR code. The
        # socket this request arrived on is this server's LAN address.
        server = request.scope.get("server")
        if server and server[0] not in ("127.0.0.1", "::1"):
            host = f"[{server[0]}]" if ":" in server[0] else server[0]
            return {"url": f"http://{host}:{server[1]}/menu"}
        return {"url": f"{request.base_url}menu"}

    @app.get("/menu/fraunces.woff2", include_in_schema=False)
    async def menu_font() -> FileResponse:
        # The clock's typeface, for the menu's headings.
        return await menu_specimen_font("fraunces")

    @app.get("/menu/fonts/{font_id}.woff2", include_in_schema=False)
    async def menu_specimen_font(font_id: str) -> FileResponse:
        # The menu's font picker draws each name in its own face. The SPA
        # build content-hashes filenames, so find whichever one shipped.
        stem = FONTS.get(font_id)
        if stem is None:
            raise HTTPException(status_code=404, detail="unknown font")
        # Aileron ships as static .otf; the menu specimen only needs regular.
        pattern = "Aileron-Regular-*.otf" if stem == "Aileron" else f"{stem}-*.woff2"
        found = sorted(
            f for f in (webroot_dir() / "assets").glob(pattern) if "Italic" not in f.name
        )
        if not found:
            raise HTTPException(status_code=404, detail="no bundled font")
        font = found[-1]
        return FileResponse(font, media_type=f"font/{font.suffix.lstrip('.')}")

    @app.get("/settings", include_in_schema=False)
    async def settings_page() -> Response:
        # The old standalone theme page, folded into the menu.
        return Response(status_code=307, headers={"Location": "/menu#themes"})

    @app.get("/apple-touch-icon.png", include_in_schema=False)
    @app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
    async def apple_touch_icon() -> FileResponse:
        candidates = [
            webroot_dir() / "apple-touch-icon.png",
            Path(__file__).resolve().parents[3] / "web" / "public" / "apple-touch-icon.png",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return FileResponse(candidate, media_type="image/png")
        raise HTTPException(status_code=404, detail="apple touch icon not found")

    @app.get("/manifest.json", include_in_schema=False)
    async def pwa_manifest() -> Response:
        data = {
            "name": "Pineda Display",
            "short_name": "Display",
            "start_url": "/menu",
            "display": "standalone",
            "background_color": "#000000",
            "theme_color": "#000000",
            "icons": [
                {"src": "/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
            ],
        }
        return JSONResponse(data)

    @app.get("/api/cards")
    async def list_cards(runtime: RuntimeDep) -> list[CardView]:
        return [_card_view(runtime, manifest) for manifest in runtime.cards.all()]

    @app.get("/api/cards/{card_id}/settings")
    async def get_card_settings(card_id: str, runtime: RuntimeDep) -> CardSettings:
        if runtime.cards.manifest(card_id) is None:
            raise HTTPException(status_code=404, detail="unknown card")
        return CardSettings(values=runtime.card_settings.get(card_id, {}))

    @app.put("/api/cards/{card_id}/settings")
    async def put_card_settings(
        card_id: str, body: CardSettings, runtime: RuntimeDep
    ) -> CardSettings:
        manifest = runtime.cards.manifest(card_id)
        if manifest is None:
            raise HTTPException(status_code=404, detail="unknown card")
        allowed = set(manifest.settings)
        merged = {**runtime.card_settings.get(card_id, {}), **body.values}
        runtime.card_settings[card_id] = {k: v for k, v in merged.items() if k in allowed}
        runtime.save_card_settings()
        for key in manifest.provides:
            runtime.scheduler.refresh(key)
        _broadcast_view_change(runtime, "card-settings")
        return CardSettings(values=runtime.card_settings[card_id])

    @app.get("/api/secrets")
    async def list_secrets(runtime: RuntimeDep) -> SecretList:
        return SecretList(names=runtime.secrets.names())

    @app.put("/api/secrets/{name}", status_code=204)
    async def set_secret(name: str, body: SecretValue, runtime: RuntimeDep) -> Response:
        runtime.secrets.set(name, body.value)
        runtime.resolve_cards()
        _broadcast_view_change(runtime, "secret")
        return Response(status_code=204)

    @app.delete("/api/secrets/{name}")
    async def delete_secret(name: str, runtime: RuntimeDep) -> Response:
        if not runtime.secrets.delete(name):
            raise HTTPException(status_code=404, detail="unknown secret")
        runtime.resolve_cards()
        _broadcast_view_change(runtime, "secret")
        return Response(status_code=204)

    # ── Calendar: QR-initiated Google OAuth ──────────────────────────────────
    # Deliberately public (see _ADMIN_PREFIXES — "/api/calendar" isn't listed):
    # the QR code on the physical display *is* the authorization to pair, the
    # same trust model /api/photos already uses for scan-to-upload.

    @app.get("/connect-calendar", response_class=HTMLResponse, include_in_schema=False)
    async def connect_calendar(request: Request, runtime: RuntimeDep) -> Any:
        client_id = runtime.secrets.get("google_calendar_client_id")
        client_secret = runtime.secrets.get("google_calendar_client_secret")
        bounce_url = runtime.settings.calendar.bounce_url
        if not client_id or not bounce_url:
            return HTMLResponse(render_not_configured())
        if client_secret:
            refreshed = await _refreshed_picker_html(
                runtime, client_id=client_id, client_secret=client_secret
            )
            if refreshed is not None:
                return HTMLResponse(refreshed)
        nonce, verifier = runtime.oauth_pending.create()
        return_url = f"{request.url.scheme}://{request.url.netloc}/api/calendar/oauth/finish"
        state = google_oauth.encode_state(nonce=nonce, return_url=return_url)
        authorize_url = google_oauth.build_authorize_url(
            client_id=client_id, redirect_uri=bounce_url, state=state, code_verifier=verifier
        )
        return Response(status_code=302, headers={"Location": authorize_url})

    @app.get("/api/calendar/oauth/finish", response_class=HTMLResponse, include_in_schema=False)
    async def calendar_oauth_finish(
        runtime: RuntimeDep,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> Any:
        client_id = runtime.secrets.get("google_calendar_client_id")
        client_secret = runtime.secrets.get("google_calendar_client_secret")
        if not client_id or not client_secret:
            return HTMLResponse(render_not_configured())
        if error:
            return HTMLResponse(render_error(f"Google declined: {error}."))
        if not code or not state:
            return HTMLResponse(
                render_error("Google didn't send back what we expected. Scan the QR and try again.")
            )
        try:
            nonce, return_url = google_oauth.decode_state(state)
        except google_oauth.OAuthError:
            return HTMLResponse(render_error("That link looked tampered with."))
        pending = runtime.oauth_pending.pop(nonce)
        if pending is None:
            return HTMLResponse(render_error("This link expired. Scan the QR code again."))
        try:
            tokens = await google_oauth.exchange_code(
                runtime.http,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=runtime.settings.calendar.bounce_url or "",
                code=code,
                code_verifier=pending.code_verifier,
            )
            userinfo = await google_oauth.fetch_userinfo(
                runtime.http, access_token=tokens.access_token
            )
            calendars = await google_oauth.fetch_calendar_list(
                runtime.http, access_token=tokens.access_token
            )
        except google_oauth.OAuthError as exc:
            logger.warning("calendar connect failed: %s", exc)
            return HTMLResponse(render_error("Google didn't accept that connection. Try again."))

        email = str(userinfo.get("email") or "")
        runtime.secrets.set(
            "google_calendar_account", json.dumps({"email": email, **tokens.as_dict()})
        )
        runtime.resolve_cards()
        _broadcast_view_change(runtime, "secret")
        return HTMLResponse(
            render_picker(
                email=email,
                calendars=calendars,
                existing_selection=_existing_calendar_selection(runtime),
            )
        )

    @app.get("/api/calendar/account")
    async def calendar_account(runtime: RuntimeDep) -> CalendarAccountView:
        raw = runtime.secrets.get("google_calendar_account")
        if not raw:
            return CalendarAccountView(connected=False)
        try:
            email = json.loads(raw).get("email")
        except (ValueError, AttributeError):
            email = None
        return CalendarAccountView(connected=True, email=email)

    @app.post("/api/calendar/sources", status_code=204)
    async def set_calendar_sources(body: CalendarSourcesUpdate, runtime: RuntimeDep) -> Response:
        manifest = runtime.cards.manifest("calendar")
        allowed = set(manifest.settings) if manifest is not None else {"sources"}
        # Each picker only shows one backend's calendars, so a save here only
        # ever covers that backend's types — carry any other backend's saved
        # sources forward untouched instead of wiping them.
        incoming_types = {s.type for s in body.sources}
        kept = [
            s
            for s in runtime.card_settings.get("calendar", {}).get("sources", [])
            if isinstance(s, dict) and s.get("type", "google") not in incoming_types
        ]
        sources = kept + [s.model_dump() for s in body.sources]
        merged = {**runtime.card_settings.get("calendar", {}), "sources": sources}
        runtime.card_settings["calendar"] = {k: v for k, v in merged.items() if k in allowed}
        runtime.save_card_settings()
        _broadcast_view_change(runtime, "card-settings")
        return Response(status_code=204)

    @app.post("/api/calendar/disconnect", status_code=204)
    async def disconnect_calendar(runtime: RuntimeDep) -> Response:
        raw = runtime.secrets.get("google_calendar_account")
        if raw:
            try:
                account = json.loads(raw)
                if account.get("access_token"):
                    await google_oauth.revoke(runtime.http, token=account["access_token"])
            except (ValueError, AttributeError):
                pass
        runtime.secrets.delete("google_calendar_account")
        _drop_calendar_sources_of_type(runtime, "google")
        runtime.resolve_cards()
        _broadcast_view_change(runtime, "secret")
        return Response(status_code=204)

    @app.get("/connect-apple-calendar", response_class=HTMLResponse, include_in_schema=False)
    async def connect_apple_calendar(runtime: RuntimeDep) -> Any:
        raw = runtime.secrets.get("apple_calendar_account")
        if not raw:
            return HTMLResponse(render_apple_form())
        try:
            account = json.loads(raw)
            calendars = await caldav_client.discover_calendars(
                runtime.http, apple_id=account["appleId"], app_specific_password=account["password"]
            )
        except (ValueError, KeyError, caldav_client.CalDavError):
            return HTMLResponse(render_apple_form())
        return HTMLResponse(
            render_picker(
                email=str(account.get("appleId") or ""),
                calendars=caldav_client.as_dict(calendars),
                existing_selection=_existing_calendar_selection(runtime),
                source_type="apple",
            )
        )

    @app.post("/api/calendar/apple/connect", response_class=HTMLResponse, include_in_schema=False)
    async def apple_calendar_connect(
        runtime: RuntimeDep,
        apple_id: str = Form(...),
        password: str = Form(...),
    ) -> Any:
        try:
            calendars = await caldav_client.discover_calendars(
                runtime.http, apple_id=apple_id, app_specific_password=password
            )
        except caldav_client.CalDavError as exc:
            return HTMLResponse(render_apple_form(error=str(exc)))
        runtime.secrets.set(
            "apple_calendar_account", json.dumps({"appleId": apple_id, "password": password})
        )
        runtime.resolve_cards()
        _broadcast_view_change(runtime, "secret")
        return HTMLResponse(
            render_picker(
                email=apple_id,
                calendars=caldav_client.as_dict(calendars),
                existing_selection=_existing_calendar_selection(runtime),
                source_type="apple",
            )
        )

    @app.get("/api/calendar/apple/account")
    async def apple_calendar_account(runtime: RuntimeDep) -> AppleCalendarAccountView:
        raw = runtime.secrets.get("apple_calendar_account")
        if not raw:
            return AppleCalendarAccountView(connected=False)
        try:
            apple_id = json.loads(raw).get("appleId")
        except (ValueError, AttributeError):
            apple_id = None
        return AppleCalendarAccountView(connected=True, apple_id=apple_id)

    @app.post("/api/calendar/apple/disconnect", status_code=204)
    async def disconnect_apple_calendar(runtime: RuntimeDep) -> Response:
        runtime.secrets.delete("apple_calendar_account")
        _drop_calendar_sources_of_type(runtime, "apple")
        runtime.resolve_cards()
        _broadcast_view_change(runtime, "secret")
        return Response(status_code=204)

    @app.get("/api/view/{device_id}")
    async def get_view(device_id: str, runtime: RuntimeDep, touch: bool = True) -> ViewModel:
        # touch=false: the phone menu looking, which isn't the screen being on.
        view = await _view_for(runtime, device_id)
        if touch:
            await runtime.devices.touch(device_id)
        return view

    @app.get("/api/stream/{device_id}")
    async def stream(device_id: str, runtime: RuntimeDep) -> StreamingResponse:
        await _resolve(runtime, device_id)
        return StreamingResponse(
            _stream(runtime, device_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/config")
    async def get_config(runtime: RuntimeDep) -> ConfigView:
        return _config_view(runtime)

    @app.post("/api/config")
    async def post_config(patch: ConfigUpdate, runtime: RuntimeDep) -> ConfigView:
        _apply_config(runtime, patch)
        _broadcast_view_change(runtime, "config")
        return _config_view(runtime)

    @app.post("/api/config/reset")
    async def reset_section(body: ResetRequest, runtime: RuntimeDep) -> ConfigView:
        """Put one Settings section back to its defaults."""
        if body.section in _RESET_PROFILE and body.profile_id:
            fields = _defaults(Profile, _RESET_PROFILE[body.section])
            if await runtime.devices.update_profile(body.profile_id, **fields) is None:
                raise HTTPException(status_code=404, detail="unknown profile")
        if body.section in _RESET_DEVICE and body.device_id:
            fields = _defaults(Device, _RESET_DEVICE[body.section])
            if await runtime.devices.update_device(body.device_id, **fields) is None:
                raise HTTPException(status_code=404, detail="unknown device")
        if body.section in _RESET_HOUSEHOLD:
            fields = _defaults(HouseholdPrefs, _RESET_HOUSEHOLD[body.section])
            runtime.household = runtime.household.model_copy(update=fields)
            if body.section == "time":
                runtime.settings.units = "imperial"
            runtime.save_household()
        _broadcast_view_change(runtime, "reset")
        return _config_view(runtime)

    @app.get("/api/config/backup")
    async def export_settings(runtime: RuntimeDep) -> Backup:
        view = _config_view(runtime)
        return Backup(
            exported_at=datetime.now(UTC),
            app_version=__version__,
            config=ConfigUpdate.model_validate(view.model_dump(exclude={"setup_complete"})),
            profiles=await runtime.devices.profiles(),
            devices=await runtime.devices.devices(),
            card_settings=runtime.card_settings,
            custom_themes=await runtime.devices.custom_themes(),
        )

    @app.post("/api/config/restore")
    async def import_settings(body: Backup, runtime: RuntimeDep) -> RestoreSummary:
        for theme in body.custom_themes:
            await runtime.devices.save_custom_theme(theme)
        set_custom_themes(await runtime.devices.custom_themes())
        for profile in body.profiles:
            await runtime.devices.restore_profile(profile)
        known = {d.id for d in await runtime.devices.devices()}
        profiles = {p.id for p in await runtime.devices.profiles()}
        restored = 0
        for device in body.devices:
            if device.id not in known:
                continue
            fields = device.model_dump(include={"name", "locked", "follow", *_COPYABLE_DEVICE})
            if fields["profile_id"] not in profiles:
                del fields["profile_id"]
            fields = {k: "" if v is None else v for k, v in fields.items()}
            await runtime.devices.update_device(device.id, **fields)
            await runtime.devices.set_grid(device.id, device.grid)
            restored += 1
        for card_id, values in body.card_settings.items():
            if runtime.cards.manifest(card_id) is not None:
                runtime.card_settings.setdefault(card_id, {}).update(values)
        runtime.save_card_settings()
        _apply_config(runtime, body.config)
        _broadcast_view_change(runtime, "restore")
        return RestoreSummary(
            profiles=len(body.profiles),
            screens=restored,
            skipped_screens=len(body.devices) - restored,
        )

    @app.get("/api/setup/detect-location")
    async def setup_detect_location(runtime: RuntimeDep) -> DetectedLocationView | None:
        found = await detect_location(runtime.http)
        return DetectedLocationView(**found.as_dict()) if found else None

    @app.post("/api/setup/complete")
    async def setup_complete(runtime: RuntimeDep) -> ConfigView:
        write_config(runtime.settings, runtime.settings.config_file)
        _broadcast_view_change(runtime, "setup")
        return _config_view(runtime)

    @app.get("/api/system")
    async def system(runtime: RuntimeDep) -> SystemView:
        disk = runtime.settings.api.db_path.parent
        return SystemView(
            server=await asyncio.to_thread(local_stats, disk if disk.exists() else Path("/")),
            screen=runtime.mqtt.screen_stats if runtime.mqtt is not None else None,
        )

    @app.get("/api/system/update")
    async def get_system_update(runtime: RuntimeDep) -> UpdateStatus:
        return get_update_status(runtime.settings)

    @app.post("/api/system/update/check")
    async def check_system_update(runtime: RuntimeDep) -> UpdateStatus:
        status = await run_update(runtime.settings, check_only=True)
        runtime.broadcaster.publish({"type": "update_status", "status": status.model_dump()})
        return status

    @app.get("/api/themes")
    async def list_themes(runtime: RuntimeDep) -> ThemeList:
        return ThemeList(current=runtime.settings.theme, themes=all_themes())

    @app.post("/api/themes/apply")
    async def apply_theme(body: ThemeApply, runtime: RuntimeDep) -> ThemeList:
        if find_theme(body.name) is None:
            raise HTTPException(status_code=400, detail=f"unknown theme: {body.name}")
        runtime.settings.theme = body.name
        _broadcast_view_change(runtime, "theme")
        return ThemeList(current=body.name, themes=all_themes())

    async def _store_custom(runtime: Runtime, theme: Theme) -> Theme:
        await runtime.devices.save_custom_theme(theme)
        set_custom_themes(await runtime.devices.custom_themes())
        _broadcast_view_change(runtime, "theme")
        return theme

    @app.post("/api/themes/custom", status_code=201)
    async def create_custom_theme(body: CustomColours, runtime: RuntimeDep) -> Theme:
        name = f"custom-{secrets.token_hex(4)}"
        return await _store_custom(runtime, custom_theme(name, body))

    @app.put("/api/themes/custom/{name}")
    async def update_custom_theme(name: str, body: CustomColours, runtime: RuntimeDep) -> Theme:
        found = find_theme(name)
        if found is None or not found.custom:
            raise HTTPException(status_code=404, detail="no such theme")
        return await _store_custom(runtime, custom_theme(name, body))

    @app.delete("/api/themes/custom/{name}", status_code=204)
    async def delete_custom_theme(name: str, runtime: RuntimeDep) -> None:
        found = find_theme(name)
        if found is None or not found.custom:
            raise HTTPException(status_code=404, detail="no such theme")
        users = [p.name for p in await runtime.devices.profiles() if p.theme == name]
        if users or runtime.settings.theme == name:
            raise HTTPException(status_code=409, detail="theme is in use")
        await runtime.devices.delete_custom_theme(name)
        set_custom_themes(await runtime.devices.custom_themes())

    @app.get("/api/profiles")
    async def list_profiles(runtime: RuntimeDep) -> list[Profile]:
        return await runtime.devices.profiles()

    @app.post("/api/profiles", status_code=201)
    async def create_profile(body: ProfileCreate, runtime: RuntimeDep) -> Profile:
        template = await runtime.devices.profile(body.copy_from) if body.copy_from else None
        created = await runtime.devices.create_profile(body.name, template)
        _broadcast_view_change(runtime, "profile")
        return created

    @app.patch("/api/profiles/{profile_id}")
    async def update_profile(profile_id: str, body: ProfileUpdate, runtime: RuntimeDep) -> Profile:
        night = body.night_theme
        if night not in (None, "", "off") and find_theme(night) is None:
            raise HTTPException(status_code=400, detail=f"unknown theme: {night}")
        if body.hide_words is not None:
            body.hide_words = _tidy_words(body.hide_words)
        updated = await runtime.devices.update_profile(
            profile_id, **body.model_dump(exclude_none=True)
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="unknown profile")
        _broadcast_view_change(runtime, "profile")
        return updated

    @app.delete("/api/profiles/{profile_id}")
    async def delete_profile(profile_id: str, runtime: RuntimeDep) -> Response:
        reason = await runtime.devices.delete_profile(profile_id)
        if reason is not None:
            raise HTTPException(
                status_code=404 if reason == "unknown profile" else 409, detail=reason
            )
        _broadcast_view_change(runtime, "profile")
        return Response(status_code=204)

    @app.get("/api/devices")
    async def list_devices(runtime: RuntimeDep) -> list[ScreenView]:
        home = runtime.settings.control.screen
        return [
            ScreenView(**d.model_dump(), online=d.id in runtime.online, home=d.id == home)
            for d in await runtime.devices.devices()
        ]

    @app.post("/api/devices/pair", status_code=201)
    async def pair(body: PairRequest, request: Request, runtime: RuntimeDep) -> Device:
        viewport = (
            (body.viewport_w, body.viewport_h) if body.viewport_w and body.viewport_h else None
        )
        control = runtime.settings.control
        client = request.client.host if request.client else None
        if control.screen and control.host and client == control.host:
            # The kiosk asking again (its cache was cleared): same screen as before.
            if await runtime.devices.device(control.screen) is None:
                await runtime.devices.adopt_device(control.screen)
            await runtime.devices.settle_screens(control.screen)
            if viewport:
                await runtime.devices.update_device(
                    control.screen, viewport_w=viewport[0], viewport_h=viewport[1]
                )
            kiosk = await runtime.devices.device(control.screen)
            assert kiosk is not None
            return kiosk
        device = await runtime.devices.pair_device(body.name, viewport, body.kind)
        _broadcast_view_change(runtime, "device")
        return device

    @app.post("/api/devices/{device_id}/keep")
    async def keep_screen(device_id: str, body: KeepRequest, runtime: RuntimeDep) -> Device:
        if body.colour not in SCREEN_COLOURS:
            raise HTTPException(status_code=422, detail=f"unknown colour: {body.colour}")
        if await runtime.devices.keep_device(device_id, body.name.strip(), body.colour) is None:
            raise HTTPException(status_code=404, detail="unknown device")
        return await _set_shows(runtime, device_id, body.shows)

    @app.post("/api/devices/{device_id}/replace")
    async def replace_screen(device_id: str, body: ReplaceRequest, runtime: RuntimeDep) -> Device:
        new = await runtime.devices.device(device_id)
        old = await runtime.devices.device(body.old)
        if new is None or old is None or new.id == old.id:
            raise HTTPException(status_code=404, detail="unknown device")
        if new.kept or not old.kept or old.id == runtime.settings.control.screen:
            raise HTTPException(status_code=409, detail="only a new screen can replace a kept one")
        replaced = await runtime.devices.replace_device(device_id, body.old)
        assert replaced is not None
        _broadcast_view_change(runtime, "device")
        return replaced

    @app.put("/api/devices/{device_id}/shows")
    async def set_shows(device_id: str, body: ShowsRequest, runtime: RuntimeDep) -> Device:
        if await runtime.devices.device(device_id) is None:
            raise HTTPException(status_code=404, detail="unknown device")
        return await _set_shows(runtime, device_id, body.shows)

    @app.put("/api/devices/{device_id}/viewport", status_code=204)
    async def set_viewport(device_id: str, body: ViewportUpdate, runtime: RuntimeDep) -> Response:
        # The screen reports its size on load and when turned. Turned while
        # on Mix, the layout turns with it.
        device = await runtime.devices.device(device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="unknown device")
        if (device.viewport_w, device.viewport_h) == (body.w, body.h):
            return Response(status_code=204)
        await runtime.devices.update_device(device_id, viewport_w=body.w, viewport_h=body.h)
        was_tall = (device.viewport_h or 0) > (device.viewport_w or 0)
        tall = body.h > body.w
        if tall != was_tall and device.grid == _shows_grid("mix", was_tall):
            await runtime.devices.set_grid(device_id, _shows_grid("mix", tall))
            _broadcast_view_change(runtime, "device")
        return Response(status_code=204)

    @app.post("/api/devices/{device_id}/forget", status_code=204)
    async def forget_screen(device_id: str, runtime: RuntimeDep) -> Response:
        if device_id == runtime.settings.control.screen:
            raise HTTPException(status_code=409, detail="the kiosk can't be removed")
        if not await runtime.devices.forget_device(device_id):
            raise HTTPException(status_code=404, detail="unknown device")
        _broadcast_view_change(runtime, "device")
        return Response(status_code=204)

    @app.patch("/api/devices/{device_id}")
    async def update_device(device_id: str, body: DeviceUpdate, runtime: RuntimeDep) -> Device:
        unknown = [c for c in body.circle_stack or [] if runtime.cards.manifest(c) is None]
        if unknown:
            raise HTTPException(status_code=422, detail=f"unknown card: {unknown[0]}")
        updated = await runtime.devices.update_device(device_id, **body.model_dump())
        if updated is None:
            raise HTTPException(status_code=404, detail="unknown device")
        _broadcast_view_change(runtime, "device")
        return updated

    @app.post("/api/devices/{device_id}/copy-from")
    async def copy_screen(device_id: str, body: CopyScreenRequest, runtime: RuntimeDep) -> Device:
        target = await runtime.devices.device(device_id)
        source = await runtime.devices.device(body.source)
        if target is None or source is None:
            raise HTTPException(status_code=404, detail="unknown device")
        fields = {
            k: "" if v is None else v
            for k, v in source.model_dump(include=set(_COPYABLE_DEVICE)).items()
        }
        await runtime.devices.update_device(device_id, **fields)
        if source.grid != target.grid:
            await runtime.devices.set_grid(device_id, source.grid)
        _broadcast_view_change(runtime, "device")
        copied = await runtime.devices.device(device_id)
        assert copied is not None
        return copied

    @app.delete("/api/devices/{device_id}")
    async def unpair_device(device_id: str, runtime: RuntimeDep) -> Response:
        if not await runtime.devices.delete_device(device_id):
            raise HTTPException(status_code=404, detail="unknown device")
        _broadcast_view_change(runtime, "device")
        return Response(status_code=204)

    @app.put("/api/devices/{device_id}/grid")
    async def set_device_grid(device_id: str, body: GridUpdate, runtime: RuntimeDep) -> Device:
        if body.grid is not None:
            unknown = [i.card for i in body.grid.items if runtime.cards.manifest(i.card) is None]
            if unknown:
                raise HTTPException(status_code=422, detail=f"unknown card: {unknown[0]}")
        updated = await runtime.devices.set_grid(device_id, body.grid)
        if updated is None:
            raise HTTPException(status_code=404, detail="unknown device")
        _broadcast_view_change(runtime, "device")
        return updated

    @app.get("/api/devices/{device_id}/grid/history")
    async def device_grid_history(device_id: str, runtime: RuntimeDep) -> list[LayoutSnapshot]:
        if await runtime.devices.device(device_id) is None:
            raise HTTPException(status_code=404, detail="unknown device")
        return await runtime.devices.layout_history(device_id)

    @app.post("/api/devices/{device_id}/identify", status_code=202)
    async def identify_device(device_id: str, runtime: RuntimeDep) -> Response:
        if await runtime.devices.device(device_id) is None:
            raise HTTPException(status_code=404, detail="unknown device")
        runtime.broadcaster.publish({"type": "identify", "deviceId": device_id})
        return Response(status_code=202)

    @app.post("/api/control/state")
    async def set_state(body: StateRequest, runtime: RuntimeDep) -> Response:
        if body.playing is not None:
            runtime.state.playing = body.playing
        runtime.state.forced = body.forced
        _broadcast_view_change(runtime, "state")
        return Response(status_code=204)

    pin_gate = PinGate()

    def _require_pin(runtime: Runtime, request: Request) -> None:
        # The phone menu sends the PIN typed on its keypad; a wrong one is a
        # 403 the page can shake at, a lockout a 429 it can explain.
        if pin_gate.locked_for():
            raise HTTPException(status_code=429, detail="too many wrong PINs")
        if not pin_gate.check(runtime.settings.control.pin, request.headers.get("x-control-pin")):
            raise HTTPException(status_code=403, detail="wrong PIN")

    @app.get("/api/control")
    async def control_info(runtime: RuntimeDep) -> dict[str, bool]:
        return {
            "pin_required": runtime.settings.control.pin is not None,
            # Only the kiosk has a live snapshot (/api/control/snapshot).
            "snapshot": bool(runtime.settings.control.host and runtime.settings.control.screen),
        }

    # One capture serves every phone looking within SNAPSHOT_TTL_S, and the
    # lock keeps phones that ask at once from each running grim on the Pi.
    snap: dict[str, Any] = {"at": 0.0, "jpeg": None}
    snap_lock = asyncio.Lock()
    SNAPSHOT_TTL_S = 5.0

    @app.get("/api/control/snapshot")
    async def control_snapshot(runtime: RuntimeDep) -> Response:
        # The phone menu's mini screen: what the kiosk really shows, as a
        # small JPEG. Not a live dashboard in an iframe — that drew the whole
        # 2048x1280 screen at the phone's 3x and crashed iOS Safari.
        async with snap_lock:
            if snap["jpeg"] is None or time.monotonic() - snap["at"] > SNAPSHOT_TTL_S:
                try:
                    snap["jpeg"] = await asyncio.to_thread(snapshot, runtime.settings.control)
                except ControlError as exc:
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                snap["at"] = time.monotonic()
        return Response(
            snap["jpeg"], media_type="image/jpeg", headers={"Cache-Control": "no-store"}
        )

    @app.post("/api/control/restart-display", status_code=202)
    async def control_restart_display(runtime: RuntimeDep, request: Request) -> Response:
        _require_pin(runtime, request)
        # Restarts pineda-kiosk.service (cage + Chromium) on the kiosk
        # device — locally, or over SSH per [control].host — never this
        # server's own host if that differs. Needs the polkit rule in
        # packaging/pineda-restart.rules installed on the kiosk device.
        try:
            await asyncio.to_thread(restart_display, runtime.settings.control)
        except ControlError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return Response(status_code=202)

    @app.post("/api/control/restart-system", status_code=202)
    async def control_restart_system(runtime: RuntimeDep, request: Request) -> Response:
        _require_pin(runtime, request)
        try:
            await asyncio.to_thread(restart_system, runtime.settings.control)
        except ControlError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return Response(status_code=202)

    @app.post("/api/control/update", status_code=202)
    async def control_update(runtime: RuntimeDep, request: Request) -> UpdateStatus:
        _require_pin(runtime, request)
        status = await run_update(runtime.settings, check_only=False)
        runtime.broadcaster.publish({"type": "update_status", "status": status.model_dump()})
        return status

    # Which way the kiosk's screen is turned. No PIN: it's as harmless as a
    # theme, and the voice assistant turns it too.
    @app.get("/api/control/rotation")
    async def control_rotation(runtime: RuntimeDep) -> RotationBody:
        try:
            turn = await asyncio.to_thread(rotation, runtime.settings.control)
        except ControlError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return RotationBody.model_validate({"rotation": turn})

    @app.put("/api/control/rotation")
    async def control_rotate(body: RotationBody, runtime: RuntimeDep) -> RotationBody:
        try:
            await asyncio.to_thread(rotate, runtime.settings.control, body.rotation)
        except ControlError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return body

    @app.get("/api/timers")
    async def list_timers(runtime: RuntimeDep) -> list[Timer]:
        return runtime.timers.list()

    @app.post("/api/timers", status_code=201)
    async def add_timer(body: TimerRequest, runtime: RuntimeDep) -> Timer:
        return runtime.timers.add(body.seconds, body.label, body.kind, body.name)

    @app.put("/api/timers/sync/{source}", status_code=204)
    async def sync_timers(source: str, body: TimerSync, runtime: RuntimeDep) -> Response:
        # A voice assistant mirrors its own timers here (see TimerService.sync).
        if not source.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(status_code=400, detail="bad source name")
        runtime.timers.sync(source, body.timers)
        return Response(status_code=204)

    @app.get("/api/takeover")
    async def get_takeover(runtime: RuntimeDep) -> Takeover | None:
        return runtime.takeover.current()

    @app.put("/api/takeover")
    async def show_takeover(body: TakeoverRequest, runtime: RuntimeDep) -> Takeover:
        # A full-screen card (Antigua's recipe view) on the screens whose
        # pop-ups allow it (_popup_for); a new one replaces the old, and it
        # comes down by itself at expires_at.
        if isinstance(body.card, CameraTakeover):
            if body.card.camera not in runtime.settings.cameras.streams:
                raise HTTPException(status_code=422, detail="unknown camera")
            if (
                body.card.pip_camera is not None
                and body.card.pip_camera not in runtime.settings.cameras.streams
            ):
                raise HTTPException(status_code=422, detail="unknown pip camera")
        return runtime.takeover.show(body.card, body.seconds)

    @app.patch("/api/takeover")
    async def update_takeover(body: TakeoverUpdate, runtime: RuntimeDep) -> Takeover | None:
        # What's being read moved on (a step, an ingredient). Changes only
        # the fields sent, never brings back a dismissed or expired card
        # (null then), and keeps the time left.
        return runtime.takeover.update(body)

    @app.get(
        "/api/takeover/images/{image_id}",
        response_class=Response,
        responses={200: {"content": {"image/webp": {}}}, 404: {}},
    )
    async def takeover_image(image_id: str, runtime: RuntimeDep, size: Size = "full") -> Response:
        # An image search or recipe choices picture, fetched and shrunk by
        # this server (image_proxy) — only the pictures on the card that's
        # up, or one a camera has set aside, so this can't fetch anything else.
        up = runtime.takeover.current()
        cards = [up.card if up is not None else None, runtime.takeover.covering]
        card = next((c for c in cards if isinstance(c, PictureCard)), None)
        item = None
        if card is not None:
            item = next((i for i in card.images if i.id.upper() == image_id.upper()), None)
        if item is None:
            raise HTTPException(status_code=404, detail="no such picture on screen")
        try:
            data, media_type = await runtime.images.picture(item, size)
        except ImageFetchError as exc:
            # 404, not 502: the kiosk's nginx fails over to the standby on a
            # 502 (proxy_next_upstream), and the rest of the collage's
            # pictures would follow it there and miss.
            logger.info("image search %s (%s): %s", item.id, size, exc)
            raise HTTPException(status_code=404, detail="picture unavailable") from exc
        return Response(
            content=data, media_type=media_type, headers={"Cache-Control": "private, max-age=600"}
        )

    @app.delete("/api/takeover", status_code=204)
    async def clear_takeover(runtime: RuntimeDep) -> Response:
        up = runtime.takeover.current()
        runtime.takeover.clear()
        # An alarm turned off on the screen or the phone stops Antigua
        # ringing it on the speaker too.
        if up is not None and isinstance(up.card, AlarmTakeover) and runtime.mqtt is not None:
            runtime.mqtt.publish("antigua/alarm_stop", {})
        return Response(status_code=204)

    # Alarms and reminders, and the recipe box, kept by Antigua (see
    # pinedaview.alarms and pinedaview.recipes).
    async def _antigua(runtime: Runtime, method: str, path: str, body: Any = None) -> Any:
        if not re.fullmatch(
            r"/alarms(/[A-Za-z0-9]+)?|/recipes(/[0-9a-f]{10}/(favorite|show))?", path
        ):
            raise HTTPException(status_code=404, detail="no such alarm or recipe")
        try:
            antigua = runtime.settings.antigua
            return await alarms.call_any(
                runtime.http, [antigua.url, antigua.fallback_url], method, path, body
            )
        except AntiguaError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

    @app.get("/api/alarms")
    async def list_alarms(runtime: RuntimeDep) -> list[Alarm]:
        rows = (await _antigua(runtime, "GET", "/alarms"))["alarms"]
        return [Alarm.model_validate(r) for r in rows]

    @app.post("/api/alarms", status_code=201)
    async def set_alarm(body: AlarmRequest, runtime: RuntimeDep) -> Alarm:
        row = await _antigua(runtime, "POST", "/alarms", body.model_dump(exclude_none=True))
        return Alarm.model_validate(row)

    @app.patch("/api/alarms/{alarm_id}")
    async def switch_alarm(alarm_id: str, body: AlarmSwitch, runtime: RuntimeDep) -> Alarm:
        row = await _antigua(runtime, "PATCH", f"/alarms/{alarm_id}", body.model_dump())
        return Alarm.model_validate(row)

    @app.delete("/api/alarms/{alarm_id}", status_code=204)
    async def delete_alarm(alarm_id: str, runtime: RuntimeDep) -> Response:
        await _antigua(runtime, "DELETE", f"/alarms/{alarm_id}")
        return Response(status_code=204)

    @app.get("/api/recipes")
    async def recipe_box(runtime: RuntimeDep) -> RecipeBox:
        # Favorites and history, each recipe whole, with its page's URL.
        return RecipeBox.model_validate(await _antigua(runtime, "GET", "/recipes"))

    @app.post("/api/recipes/{recipe_id}/favorite")
    async def favorite_recipe(recipe_id: str, runtime: RuntimeDep) -> RecipeFavorite:
        row = await _antigua(runtime, "POST", f"/recipes/{recipe_id}/favorite")
        return RecipeFavorite.model_validate(row)

    @app.delete("/api/recipes/{recipe_id}/favorite")
    async def unfavorite_recipe(recipe_id: str, runtime: RuntimeDep) -> RecipeFavorite:
        row = await _antigua(runtime, "DELETE", f"/recipes/{recipe_id}/favorite")
        return RecipeFavorite.model_validate(row)

    @app.post("/api/recipes/{recipe_id}/show")
    async def show_recipe(recipe_id: str, runtime: RuntimeDep) -> RecipeShown:
        # Antigua opens it and puts its card up, ready for "Alexa, I'm ready".
        return RecipeShown.model_validate(
            await _antigua(runtime, "POST", f"/recipes/{recipe_id}/show")
        )

    @app.get("/api/cameras/{name}/stream.mp4")
    async def camera_stream(  # noqa: C901 - go2rtc proxy with its own lifecycle closures
        name: str, runtime: RuntimeDep
    ) -> StreamingResponse:
        # The camera's live video (fragmented MP4 from go2rtc), and only
        # while its takeover is up — the server has no auth, so this isn't a
        # way to watch the cameras from anywhere on the LAN. Ends when the
        # takeover comes down.
        cams = runtime.settings.cameras

        def showing() -> bool:
            cur = runtime.takeover.current()
            if cur is None or not isinstance(cur.card, CameraTakeover):
                return False
            return cur.card.camera == name or cur.card.pip_camera == name

        if name not in cams.streams or not showing():
            raise HTTPException(status_code=404, detail="camera not showing")
        await runtime.cameras.started(name)
        client = httpx.AsyncClient(timeout=httpx.Timeout(10, read=None))
        # A battery camera's video reaches go2rtc a few seconds after Home
        # Assistant says the stream started; until then go2rtc answers 500.
        # Keep asking while the card is up rather than fail the screen,
        # which would only try again after its own back-off.
        deadline = time.monotonic() + 15
        while True:
            try:
                upstream = await client.send(
                    client.build_request(
                        "GET", f"{cams.go2rtc}/api/stream.mp4", params={"src": cams.streams[name]}
                    ),
                    stream=True,
                )
                upstream.raise_for_status()
                break
            except httpx.HTTPError as exc:
                if isinstance(exc, httpx.HTTPStatusError):
                    await exc.response.aclose()
                if time.monotonic() < deadline and showing():
                    await asyncio.sleep(0.5)
                    continue
                await client.aclose()
                raise HTTPException(status_code=502, detail="camera stream unavailable") from exc

        async def relay() -> AsyncIterator[bytes]:
            try:
                async for chunk in upstream.aiter_bytes():
                    if not showing():
                        return
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(
            relay(),
            media_type=upstream.headers.get("content-type", "video/mp4"),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/now-showing")
    async def get_now_showing(runtime: RuntimeDep, device_id: str | None = None) -> NowShowingView:
        return _now_showing(runtime, device_id)

    @app.post("/api/now-showing", status_code=204)
    async def report_now_showing(body: NowShowingReport, runtime: RuntimeDep) -> Response:
        # No broadcast: nothing on screen depends on it, and a photo swap
        # every 20s shouldn't rebuild every screen's view.
        runtime.now_showing.report(body.device_id, body.card, body.item)
        return Response(status_code=204)

    @app.post("/api/now-showing/look", status_code=204)
    async def report_look(body: ScreenLookReport, runtime: RuntimeDep) -> Response:
        runtime.now_showing.report_look(body.device_id, ScreenLook(**body.model_dump()))
        return Response(status_code=204)

    @app.delete("/api/timers/{timer_id}")
    async def cancel_timer(timer_id: str, runtime: RuntimeDep) -> Response:
        if not runtime.timers.cancel(timer_id):
            raise HTTPException(status_code=404, detail="unknown timer")
        return Response(status_code=204)

    @app.get("/api/photos")
    async def list_photos(runtime: RuntimeDep) -> list[Photo]:
        return await asyncio.to_thread(runtime.photos.all)

    def _cut_out_subject(runtime: Runtime, name: str) -> None:
        """Make the Photo Clock's cutout in the background; screens pick it
        up from the next photos push."""

        async def run() -> None:
            if await asyncio.to_thread(runtime.photos.make_subjects, [name]):
                _broadcast_view_change(runtime, "photos")

        _background.add(task := asyncio.create_task(run(), name=f"photo-subject-{name}"))
        task.add_done_callback(_background.discard)

    async def _add_photo(runtime: Runtime, file: UploadFile, *, pending: bool) -> Photo:
        data = await file.read()
        try:
            photo = await asyncio.to_thread(
                runtime.photos.add, file.filename or "photo.jpg", data, pending=pending
            )
        except DuplicatePhotoError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except TooLongError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except ValueError as exc:
            logger.warning(
                "photo rejected: %r (%d bytes, starts %s): %s",
                file.filename,
                len(data),
                data[:16].hex(),
                exc,
            )
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        if not pending:
            runtime.resolve_cards()
            _cut_out_subject(runtime, photo.name)
        _broadcast_view_change(runtime, "photos")
        return photo

    @app.post("/api/photos", status_code=201)
    async def upload_photo(runtime: RuntimeDep, file: UploadFile = File()) -> Photo:  # noqa: B008
        """The guest drop-off (the QR code and /upload): follows Settings →
        Photos → Guest uploads."""
        policy = runtime.household.guest_uploads
        if policy == "off":
            raise HTTPException(status_code=403, detail="guest uploads are turned off")
        return await _add_photo(runtime, file, pending=policy == "review")

    @app.post("/api/photos/library", status_code=201)
    async def add_to_library(runtime: RuntimeDep, file: UploadFile = File()) -> Photo:  # noqa: B008
        """The owner's upload from Settings: straight into the slideshow,
        whatever the guest policy. Needs the write token when one is set."""
        return await _add_photo(runtime, file, pending=False)

    @app.get("/api/photos/pending")
    async def pending_photos(runtime: RuntimeDep) -> list[Photo]:
        return await asyncio.to_thread(runtime.photos.pending)

    @app.post("/api/photos/{name}/approve")
    async def approve_photo(name: str, runtime: RuntimeDep) -> Photo:
        try:
            photo = await asyncio.to_thread(runtime.photos.approve, name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown photo") from exc
        runtime.resolve_cards()
        _broadcast_view_change(runtime, "photos")
        _cut_out_subject(runtime, photo.name)
        return photo

    @app.delete("/api/photos/{name}")
    async def delete_photo(name: str, runtime: RuntimeDep) -> Response:
        if not await asyncio.to_thread(runtime.photos.delete, name):
            raise HTTPException(status_code=404, detail="unknown photo")
        runtime.resolve_cards()
        _broadcast_view_change(runtime, "photos")
        return Response(status_code=204)

    @app.post("/api/photos/{name}/rotate")
    async def rotate_photo(name: str, degrees: int, runtime: RuntimeDep) -> Photo:
        try:
            photo = await asyncio.to_thread(runtime.photos.rotate, name, degrees)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown photo") from exc
        _broadcast_view_change(runtime, "photos")
        return photo

    @app.post("/api/photos/reorder")
    async def reorder_photos(body: PhotoOrder, runtime: RuntimeDep) -> list[Photo]:
        photos = await asyncio.to_thread(runtime.photos.reorder, body.names)
        _broadcast_view_change(runtime, "photos")
        return photos

    @app.post("/api/photos/{name}/use-as-wallpaper", status_code=204)
    async def photo_to_wallpaper(name: str, runtime: RuntimeDep) -> Response:
        if not runtime.photos.original_path(name).is_file():
            raise HTTPException(status_code=404, detail="unknown photo")
        data = await asyncio.to_thread(runtime.photos.render, name)
        await asyncio.to_thread(runtime.wallpaper.set, data)
        _broadcast_view_change(runtime, "wallpaper")
        return Response(status_code=204)

    _PHOTO_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}

    @app.get("/api/photos/{name}")
    async def get_photo(name: str, runtime: RuntimeDep) -> FileResponse:
        path = runtime.photos.original_path(name)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="unknown photo")
        return FileResponse(path, headers=_PHOTO_CACHE_HEADERS)

    @app.get("/api/photos/{name}/display")
    async def get_photo_display(name: str, runtime: RuntimeDep) -> FileResponse:
        path = runtime.photos.display_path(name)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="unknown photo")
        return FileResponse(path, headers=_PHOTO_CACHE_HEADERS)

    @app.get("/api/photos/{name}/subject")
    async def get_photo_subject(name: str, runtime: RuntimeDep) -> FileResponse:
        path = runtime.photos.subject_path(name)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="no subject cutout")
        return FileResponse(path, media_type="image/webp", headers=_PHOTO_CACHE_HEADERS)

    @app.get("/api/photos/{name}/mask")
    async def get_photo_mask(name: str, runtime: RuntimeDep) -> FileResponse:
        path = await asyncio.to_thread(runtime.photos.mask, name)
        if path is None:
            raise HTTPException(status_code=404, detail="no subject cutout")
        return FileResponse(path, media_type="image/png", headers=_PHOTO_CACHE_HEADERS)

    @app.get("/api/photos/{name}/motion")
    async def get_photo_motion(name: str, runtime: RuntimeDep) -> FileResponse:
        path = runtime.photos.motion_path(name)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="no motion clip")
        return FileResponse(path, media_type="video/mp4", headers=_PHOTO_CACHE_HEADERS)

    @app.get("/api/photos/{name}/thumb")
    async def get_photo_thumb(name: str, runtime: RuntimeDep) -> FileResponse:
        path = runtime.photos.thumb_path(name)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="no thumbnail")
        return FileResponse(path, media_type="image/jpeg", headers=_PHOTO_CACHE_HEADERS)

    @app.get("/api/nowplaying/cover", include_in_schema=False)
    async def now_playing_cover(runtime: RuntimeDep) -> Response:
        data = runtime.mqtt.cover() if runtime.mqtt is not None else None
        if not data:
            raise HTTPException(status_code=404, detail="no album art")
        media = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        return Response(content=data, media_type=media, headers={"Cache-Control": "no-cache"})

    @app.get("/api/cams/{name}", include_in_schema=False)
    async def traffic_cam(name: str) -> Response:
        # The traffic provider's in-memory copy — one per camera, replaced
        # every ~3 min. The URL carries ?v=<capture time>, so a new capture is
        # a new URL and each one can be cached for its whole lifetime.
        data = CAM_CACHE.get(name) if valid_file(name) else None
        if not data:
            raise HTTPException(status_code=404, detail="no such camera image")
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=900, immutable"},
        )

    @app.get("/api/news/{story_id}.jpg", include_in_schema=False)
    async def news_picture(story_id: str) -> Response:
        # The news provider's blurred copy of a story's picture, kept while the
        # story is in the rotation. A story id is a hash of its article URL,
        # so each picture is cached for its whole lifetime.
        data = NEWS_CACHE.get(story_id) if valid_news_id(story_id) else None
        if not data:
            raise HTTPException(status_code=404, detail="no such news picture")
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400, immutable"},
        )

    @app.get("/api/home-cams/{name}.jpg", include_in_schema=False)
    async def home_cam(name: str, runtime: RuntimeDep) -> FileResponse:
        # Antigua's latest photo from the doorbell or the garage camera, for
        # the home-cams card. Only configured camera names, so the path can't
        # wander out of the directory.
        cams = runtime.settings.cameras
        path = cams.snapshots_dir / f"{name}.jpg" if cams.snapshots_dir else None
        if name not in cams.streams or path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="no such camera photo")
        return FileResponse(
            path,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )

    @app.get("/api/wallpaper")
    @app.head("/api/wallpaper", include_in_schema=False)
    async def get_wallpaper(runtime: RuntimeDep) -> FileResponse:
        # FastAPI, unlike plain Starlette, doesn't add HEAD to a GET route
        # automatically — client.hasWallpaper() (and the new /settings page)
        # depend on HEAD to check for a wallpaper without fetching the image.
        path = runtime.wallpaper.path()
        if path is None:
            raise HTTPException(status_code=404, detail="no wallpaper set")
        return FileResponse(
            path,
            media_type=runtime.wallpaper.content_type(),
            headers={"Cache-Control": "no-cache"},
        )

    @app.put("/api/wallpaper", status_code=204)
    async def set_wallpaper(runtime: RuntimeDep, file: UploadFile = File()) -> Response:  # noqa: B008
        try:
            await asyncio.to_thread(runtime.wallpaper.set, await file.read())
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        _broadcast_view_change(runtime, "wallpaper")
        return Response(status_code=204)

    @app.delete("/api/wallpaper")
    async def clear_wallpaper(runtime: RuntimeDep) -> Response:
        if not await asyncio.to_thread(runtime.wallpaper.clear):
            raise HTTPException(status_code=404, detail="no wallpaper set")
        _broadcast_view_change(runtime, "wallpaper")
        return Response(status_code=204)

    @app.post("/api/ingest/{store}", status_code=202)
    async def ingest(store: str, body: dict[str, Any], runtime: RuntimeDep) -> Response:
        if not store.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(status_code=400, detail="bad store name")
        runtime.stores.get_or_create(store, stale_after_s=600.0).publish(body)
        runtime.broadcaster.publish({"type": "store", "key": store})
        _broadcast_view_change(runtime, "ingest")
        return Response(status_code=202)

    @app.get("/api/debug/stores")
    async def debug_stores(runtime: RuntimeDep) -> dict[str, Any]:
        return {
            "generatedAt": datetime.now(UTC).isoformat(),
            "stores": runtime.stores.snapshot(),
        }
