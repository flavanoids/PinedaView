# SPDX-License-Identifier: Apache-2.0
"""The view model.

The server decides what each screen shows — which state, which cards, which slot
holds the hero, whether a banner is up — and hands the client a finished
description to render. No display logic runs client-side; no data fetching runs
server-side. These pydantic models are also the wire contract: they generate the
OpenAPI schema and, from it, the TypeScript client.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from pinedaview.config import CountdownConfig, Settings
from pinedaview.household import DateStyle, HouseholdPrefs, TimeFormat
from pinedaview.registry import (
    CIRCLE_MAX,
    Device,
    Grid,
    Pace,
    PhotoClock,
    PhotoFit,
    PhotoOrderSetting,
    Profile,
)
from pinedaview.state import DisplayState, parse_hhmm
from pinedaview.stores import StoreRegistry
from pinedaview.sun import is_night, resolve_coords
from pinedaview.takeover import Takeover
from pinedaview.themes import get_theme
from pinedaview.timers import Timer

PROTOCOL_VERSION = "v0"

# Which store(s) back each card. Cards absent here have no backing data (the
# clock ticks client-side; now-playing arrives via MQTT in Phase 08; the timer
# card is injected separately below since it comes from TimerService, not a
# store). A mini-card cluster (moon-climate) reads more than one.
_CARD_STORE: dict[str, str | tuple[str, ...]] = {
    "weather": "weather",
    "forecast": "weather",
    "affirmation": "dailyContent",
    "phrase": "dailyContent",
    "moon": "moon",
    "moon-climate": ("moon", "indoorClimate"),
    "air-quality": "airQuality",
    "now-playing": "nowPlaying",
    "commute": "commute",
    "alerts": "alerts",
    "radar": "radar",
    "indoor-climate": "indoorClimate",
    "on-this-day": "onThisDay",
    "traffic": ("traffic", "dailyContent"),
    "home-cams": "homeCams",
    "news": "news",
    "calendar": "calendar",
}


def _as_tuple(value: str | tuple[str, ...]) -> tuple[str, ...]:
    return (value,) if isinstance(value, str) else value


def _card_stores(card: str) -> tuple[str, ...]:
    key = _CARD_STORE.get(card)
    return () if key is None else _as_tuple(key)


# Cards that can own the hero slot, in priority order. The photo frame leads —
# family photos are the thing worth making big; the clock drops to a normal
# grid tile. A transient takeover (now-playing while PLAYING, the countdown, an
# alert) still overrides all of this.
_HERO_ELIGIBLE = ("photo", "clock", "weather", "nowPlaying")


class Ticker(BaseModel):
    kind: Literal["clock", "countdown"]
    target: datetime | None = None


class Hero(BaseModel):
    kind: Literal["card", "nowPlaying", "countdown"]
    card: str | None = None


class ViewCard(BaseModel):
    id: str
    stale: bool
    detail: bool = False
    hidden: bool = False
    """Holding its slot but showing nothing (the radar on a dry day): the
    client renders an empty cell, so the rest of the grid doesn't move."""


class AlertBanner(BaseModel):
    severity: str
    event: str
    headline: str


class ScreenPrefs(BaseModel):
    """The household's, profile's and screen's preferences the client applies
    itself — formatting, timings, the night clock's hours."""

    time_format: TimeFormat = "12h"
    date_style: DateStyle = "long"
    pace: Pace = "normal"
    photo_hold_s: int = 20
    photo_order: PhotoOrderSetting = "manual"
    photo_fit: PhotoFit = "fill"
    accent: str | None = None
    wallpaper_everywhere: bool = False
    night_weeknight_start: str = "00:00"
    night_weekend_start: str = "02:00"
    night_end: str = "05:00"
    peek_s: int = 60
    dynamic_shuffle: bool = False
    shuffle_hold_s: int = 15
    ambient_cycle_m: int = 5


class ViewModel(BaseModel):
    version: str = PROTOCOL_VERSION
    device_id: str
    profile_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state: DisplayState
    profile_name: str = ""
    screen_name: str = ""
    screen_colour: str | None = None
    """The screen's colour in the phone menu; "Find it" flashes it."""
    welcome: bool = False
    """Nobody has set this screen up yet: it shows "New screen!" (web Welcome)
    instead of the cards, until someone keeps it from the phone menu."""
    theme: str
    layout: str
    units: str
    locked: bool = False
    brightness: float = 1.0
    blackout: bool = False
    night_clock: bool = True
    """Show the lone night clock in the small hours (the client keeps the
    schedule, web lib/nightClock)."""
    night_clock_hold: bool = False
    """Show the night clock now and keep it up until this is switched off."""
    alternate: bool = False
    """Take turns between the Photo Clock (1 min) and the cards (30 s), with a
    2 s handoff (web Alternate). The small-hours night clock still wins."""
    night_clock_font: str | None = None
    """The night clock's typeface (a FONTS id); None = its own."""
    night_clock_color: str | None = None
    """The night clock's colour (#rrggbb); None = its own."""
    night_clock_photo: bool = False
    """Clock only (held) shows the Photo Clock instead of the lone clock."""
    night_clock_tint: str | None = None
    """The Photo Clock's glass tint: #rrggbb, "auto", or None for clear."""
    photo_clock: PhotoClock | None = None
    """The Photo Clock's font, size and glass; None = its defaults."""
    hero: Hero
    cards: list[ViewCard]
    alert: AlertBanner | None = None
    tickers: list[Ticker]
    stale_stores: list[str]
    stale_since: dict[str, str] = Field(default_factory=dict)
    """When each stale store last had fresh data (ISO 8601), so a card can say
    "Updated 2 hr ago" rather than just that it's old."""
    data: dict[str, Any] = Field(default_factory=dict)
    """Store values for the cards on screen — so the client renders in one
    round trip. Keyed by store name (``weather``, ``moon``, ``dailyContent`` …)."""
    clock_face: str | None = None
    """The profile's pushed clock face (see ``Profile.clock_face``). The client
    applies it when it changes, so a pick on the phone page lands live."""
    animated_background: bool = False
    """The profile's slow theme-gradient drift (see ``Profile.animated_background``)."""
    font: str | None = None
    """The profile's typeface override (see ``Profile.font``)."""
    takeover: Takeover | None = None
    """A full-screen card (a recipe Antigua is reading) covering the whole
    screen until ``expires_at`` or until it's taken down."""
    grid: Grid | None = None
    """The screen's hand-placed layout, when it has one. The client puts each
    of ``cards`` in its box and the hero in ``grid.hero_item()``'s; a placed
    card missing from ``cards`` (not ready, nothing today) leaves its box
    empty rather than reflowing the rest."""
    theme_rev: int = 0
    """Bumps whenever a custom theme is saved, so screens fetch /api/themes
    again and pick up its new colours."""
    wallpaper_rev: int = 0
    """Mtime of the Liquid Glass background image, or 0 when none is set. The
    client pins its ``/api/wallpaper`` URL to this so a new upload propagates
    to live displays without a reload."""
    prefs: ScreenPrefs = Field(default_factory=ScreenPrefs)
    shape: Literal["rect", "circle"] = "rect"
    """The rectangle of cards, or the round watch face (web RoundStage)."""
    frame_inset: int = 0
    """Percent of the width a picture frame hides on each side (web App)."""
    circle: list[str] = Field(default_factory=list)
    """On a round screen, its cards in slot order (web lib/round.ts): the
    centre, the top, then the bottom from left to right. The centre one is the
    hero; a card that isn't ready leaves its slot empty instead of moving the
    rest."""


def _countdown_target(now: datetime, cfg: CountdownConfig) -> datetime:
    end = parse_hhmm(cfg.end)
    return now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)


def _hero(state: DisplayState, stack: list[str], override: str | None = None) -> Hero:
    if state in (DisplayState.COUNTDOWN, DisplayState.ALERT):
        return Hero(kind="countdown", card=None)
    # A pinned hero (Settings > Devices > Hero card) wins over the now-playing
    # takeover — someone who pinned e.g. the photo frame wants it to stay put,
    # not get bumped every time music starts. Countdown/alert still override
    # any pin above, since those are time-critical. now-playing still renders
    # as an ordinary grid card (it's in the stack) when it isn't hero.
    if override and override in stack:
        return Hero(kind="card", card=override)
    if state == DisplayState.PLAYING:
        return Hero(kind="nowPlaying")
    present = set(stack)
    for card in _HERO_ELIGIBLE:
        if card in present:
            return Hero(kind="card", card=card)
    return Hero(kind="card", card=stack[0] if stack else None)


def _hero_card(hero: Hero) -> str | None:
    """The stack card the hero is already showing — it must not also appear in
    the grid. The now-playing takeover renders the now-playing card itself."""
    if hero.kind == "card":
        return hero.card
    if hero.kind == "nowPlaying":
        return "now-playing"
    return None


def _alert_banner(stores: StoreRegistry) -> AlertBanner | None:
    entry = stores.get("alerts")
    snap = entry.snapshot() if entry is not None else None
    value = snap.value if snap is not None else None
    top = value.get("top") if isinstance(value, dict) else None
    if not isinstance(top, dict):
        return None
    return AlertBanner(
        severity=top.get("severity", "Unknown"),
        event=top.get("event", "Alert"),
        headline=top.get("headline", ""),
    )


def _is_stale(card: str, stores: StoreRegistry) -> bool:
    keys = _card_stores(card)
    if not keys:
        return False
    for key in keys:
        entry = stores.get(key)
        snap = entry.snapshot() if entry else None
        if snap is None or snap.stale:
            return True
    return False


def _has_memory_today(stores: StoreRegistry) -> bool:
    entry = stores.get("onThisDay")
    snap = entry.snapshot() if entry is not None else None
    return isinstance(snap.value, dict) and bool(snap.value.get("name")) if snap else False


def _rain_chance(stores: StoreRegistry) -> int | None:
    """The highest rain chance today or over the next ~24h, or None before the
    first weather fetch."""
    value = _store_value(stores, "weather")
    if not isinstance(value, dict):
        return None
    slots = list(value.get("hourly") or [])[:24] + list(value.get("forecast") or [])[:1]
    raw = [s.get("precip") for s in slots if isinstance(s, dict)]
    chances = [c for c in raw if isinstance(c, int)]
    return max(chances) if chances else None


def _radar_worth_showing(stores: StoreRegistry, hide_below: int) -> bool:
    chance = _rain_chance(stores)
    return chance is None or chance >= hide_below


def _in_blackout(now: datetime, start: str | None, end: str | None) -> bool:
    if not start or not end:
        return False
    current = now.time()
    lo, hi = parse_hhmm(start), parse_hhmm(end)
    if lo <= hi:
        return lo <= current < hi
    return current >= lo or current < hi  # window wraps past midnight


def _store_value(stores: StoreRegistry, key: str) -> Any:
    store = stores.get(key)
    snap = store.snapshot() if store is not None else None
    return snap.value if snap is not None else None


def _resolve_theme_name(
    base_name: str,
    moment: datetime,
    settings: Settings,
    stores: StoreRegistry,
    night_theme: str | None = None,
) -> str:
    """The theme to paint now. ``night_theme`` (the profile's "After sunset")
    is None to follow the theme's own night colours, ``"off"`` to stay put,
    or the theme to switch to."""
    night = get_theme(base_name).night if night_theme is None else night_theme
    if not night or night == "off" or night == base_name:
        return base_name
    coords = resolve_coords(settings, stores)
    if coords is None:
        return base_name
    return night if is_night(moment, *coords) else base_name


def _mentions(text: object, words: list[str]) -> bool:
    if not isinstance(text, str):
        return False
    folded = text.casefold()
    return any(w.casefold() in folded for w in words)


def _filter_content(data: dict[str, Any], words: list[str]) -> None:
    """Drop the news stories and quotes the profile asked to hide, in place."""
    if not words:
        return
    news = data.get("news")
    if isinstance(news, dict) and isinstance(news.get("stories"), list):
        data["news"] = {
            **news,
            "stories": [
                s
                for s in news["stories"]
                if not (isinstance(s, dict) and _mentions(s.get("title"), words))
            ],
        }
    daily = data.get("dailyContent")
    if isinstance(daily, dict) and isinstance(daily.get("affirmations"), list):
        kept = [
            q
            for q in daily["affirmations"]
            if not (
                isinstance(q, dict)
                and (_mentions(q.get("text"), words) or _mentions(q.get("author"), words))
            )
        ]
        # The singular `affirmation` is the card's fallback when the list is
        # empty, so it has to go too.
        data["dailyContent"] = {
            **daily,
            "affirmations": kept,
            "affirmation": kept[0] if kept else None,
        }


def _brightness(device: Device, moment: datetime) -> float:
    """The screen's brightness, lowered to its dim level inside its dim window."""
    if _in_blackout(moment, device.dim_start, device.dim_end):
        return min(device.brightness, device.dim_level)
    return device.brightness


def _circle(device: Device, profile: Profile) -> list[str]:
    """A round screen's cards in slot order: its own pick, or else the first
    four of its stack — the clock left out, since the hands are the clock."""
    if device.circle_stack is not None:
        return device.circle_stack
    stack = device.card_stack if device.card_stack is not None else profile.card_stack
    return [c for c in stack if c != "clock" and c not in device.cards_off][:CIRCLE_MAX]


def _screen_stack(device: Device, profile: Profile) -> list[str]:
    """The cards this screen is set to show, in reading order."""
    if device.shape == "circle":
        return _circle(device, profile)
    if device.grid is not None:
        return [i.card for i in sorted(device.grid.items, key=lambda i: (i.y, i.x))]
    stack = device.card_stack if device.card_stack is not None else profile.card_stack
    return [card for card in stack if card not in device.cards_off]


def _place(
    device: Device,
    profile: Profile,
    state: DisplayState,
    stack: list[str],
    hidden: set[str],
) -> tuple[Hero, list[str]]:
    """The hero and the grid cards around it."""
    if device.shape == "circle":
        # Fixed slots, like a hand-placed grid: the centre card is the hero
        # (no now-playing takeover) and countdown or alert takes the centre.
        centre = next(iter(_circle(device, profile)), None)
        if state in (DisplayState.COUNTDOWN, DisplayState.ALERT):
            hero = _hero(state, stack)
        else:
            hero = Hero(kind="card", card=centre if centre in stack else None)
        return hero, [c for c in stack if c != centre and c not in hidden]
    grid = device.grid
    if grid is not None:
        # Hand-placed: the biggest box is the hero and nothing moves — no
        # now-playing takeover, and a card with nothing to show just leaves
        # its box empty. Countdown and alert still take the big box.
        big = grid.hero_item()
        if state in (DisplayState.COUNTDOWN, DisplayState.ALERT):
            hero = _hero(state, stack)
        else:
            hero = Hero(kind="card", card=big.card if big and big.card in stack else None)
        return hero, [c for c in stack if not big or c != big.card]
    is_shuffle = (
        device.dynamic_shuffle if device.dynamic_shuffle is not None else profile.dynamic_shuffle
    )
    if is_shuffle:
        # Photo card is omitted in dynamic shuffle: ambient Photo Clock handles
        # photos full-screen, and photos shouldn't sit in a small tile.
        stack = [c for c in stack if c != "photo"]
    override = device.hero_card or profile.hero_card
    if is_shuffle and override == "photo":
        override = None
    hero = _hero(state, stack, override)
    body = [c for c in stack if c != _hero_card(hero)]
    # A dropped card's gap is absorbed by the last card's trailing-row stretch
    # (Stage.svelte), whichever card that is — now-playing included, since the
    # kiosk now ends on it and wants it wide.
    return hero, [c for c in body if c not in hidden]


def build_view_model(
    *,
    device: Device,
    profile: Profile,
    settings: Settings,
    stores: StoreRegistry,
    state: DisplayState,
    now: datetime | None = None,
    ready_cards: set[str] | None = None,
    detail_cards: set[str] | None = None,
    wallpaper_rev: int = 0,
    theme_rev: int = 0,
    timers: list[Timer] | None = None,
    takeover: Takeover | None = None,
    card_settings: dict[str, dict[str, Any]] | None = None,
    household: HouseholdPrefs | None = None,
) -> ViewModel:
    moment = now or datetime.now().astimezone()
    stack = _screen_stack(device, profile)
    if ready_cards is not None:
        stack = [card for card in stack if card in ready_cards]
    # "on this day" has nothing most days (a few hundred photos rarely land on
    # today's month/day in a past year) — drop it from the grid entirely
    # rather than show an empty tile or a fake/wrong-day photo. The grid's
    # rows are auto-sized (see Stage.svelte), so this reflows cleanly.
    if "on-this-day" in stack and not _has_memory_today(stores):
        stack = [c for c in stack if c != "on-this-day"]
    # The radar on a dry day is an empty map: below the card's rain-chance
    # cut-off (the radar's card settings) it leaves the grid (see below).
    hidden: set[str] = set()
    hide_below = (card_settings or {}).get("radar", {}).get("hideBelow", 20)
    if "radar" in stack and not _radar_worth_showing(stores, int(hide_below or 0)):
        hidden.add("radar")
    detail_cards = detail_cards or set()
    hero, body = _place(device, profile, state, stack, hidden)

    needed = {store for c in stack for store in _card_stores(c)}
    # Whenever music plays, not only when it's the hero: the night clock's
    # corner music card reads it too, and a pinned hero card keeps the hero.
    if state == DisplayState.PLAYING:
        needed.add("nowPlaying")
    data = {key: _store_value(stores, key) for key in sorted(needed)}
    _filter_content(data, profile.hide_words)
    # The moon-climate and home-cams mini cards show a running timer too, and
    # every screen gets the list while one runs, so each can chime when it
    # ends (web lib/timerSound) whatever cards it shows.
    if timers or "timer" in stack or "moon-climate" in stack or "home-cams" in stack:
        data["timer"] = [t.model_dump(mode="json") for t in (timers or [])]

    tickers: list[Ticker] = [Ticker(kind="clock")]
    if state in (DisplayState.COUNTDOWN, DisplayState.ALERT):
        tickers.append(
            Ticker(kind="countdown", target=_countdown_target(moment, settings.countdown))
        )

    all_stores = {store for value in _CARD_STORE.values() for store in _as_tuple(value)}
    stale_since = {
        key: snap.updated_at.isoformat()
        for key in sorted(all_stores)
        if (store := stores.get(key)) is not None
        and (snap := store.snapshot()) is not None
        and snap.stale
    }
    stale_stores = list(stale_since)

    return ViewModel(
        device_id=device.id,
        profile_id=profile.id,
        profile_name=profile.name,
        screen_name=device.name,
        screen_colour=device.colour,
        welcome=not device.kept,
        state=state,
        theme=_resolve_theme_name(
            profile.theme or settings.theme, moment, settings, stores, profile.night_theme
        ),
        layout=device.layout or profile.layout,
        units=settings.units,
        locked=device.locked,
        brightness=_brightness(device, moment),
        blackout=_in_blackout(moment, device.blackout_start, device.blackout_end),
        night_clock=device.night_clock,
        night_clock_hold=device.night_clock and device.night_clock_hold,
        alternate=device.alternate,
        night_clock_font=device.night_clock_font,
        night_clock_color=device.night_clock_color,
        night_clock_photo=device.night_clock_photo,
        night_clock_tint=device.night_clock_tint,
        photo_clock=device.photo_clock,
        hero=hero,
        cards=[
            ViewCard(id=c, stale=_is_stale(c, stores), detail=c in detail_cards, hidden=c in hidden)
            for c in body
        ],
        alert=_alert_banner(stores),
        tickers=tickers,
        stale_stores=stale_stores,
        stale_since=stale_since,
        data=data,
        clock_face=profile.clock_face,
        animated_background=profile.animated_background,
        font=profile.font,
        wallpaper_rev=wallpaper_rev,
        theme_rev=theme_rev,
        takeover=takeover,
        grid=device.grid,
        prefs=_screen_prefs(device, profile, household or HouseholdPrefs()),
        shape=device.shape,
        frame_inset=device.frame_inset,
        circle=_circle(device, profile) if device.shape == "circle" else [],
    )


def _screen_prefs(device: Device, profile: Profile, household: HouseholdPrefs) -> ScreenPrefs:
    return ScreenPrefs(
        **household.model_dump(include={"time_format", "date_style"}),
        **profile.model_dump(
            include={
                "pace",
                "photo_hold_s",
                "photo_order",
                "photo_fit",
                "accent",
                "wallpaper_everywhere",
            }
        ),
        **device.model_dump(
            include={"night_weeknight_start", "night_weekend_start", "night_end", "peek_s"}
        ),
        dynamic_shuffle=(
            device.dynamic_shuffle
            if device.dynamic_shuffle is not None
            else profile.dynamic_shuffle
        ),
        shuffle_hold_s=(
            device.shuffle_hold_s if device.shuffle_hold_s is not None else profile.shuffle_hold_s
        ),
        ambient_cycle_m=(
            device.ambient_cycle_m
            if device.ambient_cycle_m is not None
            else profile.ambient_cycle_m
        ),
    )
