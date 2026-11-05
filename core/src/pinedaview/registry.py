# SPDX-License-Identifier: Apache-2.0
"""Device and profile registry, backed by SQLite.

A **profile** is a named screen recipe — a layout, an ordered card stack, a
theme. A **device** is a browser paired to the server; it points at one profile.
The tables are tiny and writes are rare, so each call hops to a thread rather
than pulling in an async driver.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator

from pinedaview.themes import Theme

DEFAULT_PROFILE_ID = "default"

Pace = Literal["relaxed", "normal", "brisk"]
PhotoOrderSetting = Literal["manual", "newest", "shuffle"]
PhotoFit = Literal["fill", "fit"]
_DEFAULT_STACK = [
    "clock",
    "weather",
    "home-cams",
    "affirmation",
    "traffic",
    "radar",
    "photo",
    "now-playing",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    layout       TEXT NOT NULL DEFAULT 'wide_grid',
    card_stack   TEXT NOT NULL DEFAULT '[]',
    theme        TEXT NOT NULL DEFAULT 'blush',
    tier_default TEXT NOT NULL DEFAULT 'auto'
);
CREATE TABLE IF NOT EXISTS layout_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    saved_at  TEXT NOT NULL,
    grid      TEXT
);
CREATE TABLE IF NOT EXISTS custom_themes (
    name  TEXT PRIMARY KEY,
    theme TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    profile_id TEXT NOT NULL REFERENCES profiles(id),
    paired_at  TEXT NOT NULL,
    last_seen  TEXT,
    viewport_w INTEGER,
    viewport_h INTEGER,
    tier       TEXT
);
"""

# Columns added after the first release — applied idempotently on init.
_MIGRATIONS = (
    "ALTER TABLE devices ADD COLUMN card_stack TEXT",
    "ALTER TABLE devices ADD COLUMN layout TEXT",
    "ALTER TABLE devices ADD COLUMN locked INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE devices ADD COLUMN pair_code TEXT",
    "ALTER TABLE devices ADD COLUMN follow TEXT",
    "ALTER TABLE devices ADD COLUMN brightness REAL NOT NULL DEFAULT 1.0",
    "ALTER TABLE devices ADD COLUMN blackout_start TEXT",
    "ALTER TABLE devices ADD COLUMN blackout_end TEXT",
    "ALTER TABLE devices ADD COLUMN hero_card TEXT",
    "ALTER TABLE profiles ADD COLUMN hero_card TEXT",
    "ALTER TABLE profiles ADD COLUMN clock_face TEXT",
    "ALTER TABLE profiles ADD COLUMN animated_background INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE profiles ADD COLUMN font TEXT",
    "ALTER TABLE devices ADD COLUMN cards_off TEXT",
    "ALTER TABLE devices ADD COLUMN grid TEXT",
    "ALTER TABLE devices ADD COLUMN night_clock INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE devices ADD COLUMN night_clock_hold INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE profiles ADD COLUMN pace TEXT NOT NULL DEFAULT 'normal'",
    "ALTER TABLE profiles ADD COLUMN photo_hold_s INTEGER NOT NULL DEFAULT 20",
    "ALTER TABLE profiles ADD COLUMN photo_order TEXT NOT NULL DEFAULT 'manual'",
    "ALTER TABLE profiles ADD COLUMN photo_fit TEXT NOT NULL DEFAULT 'fill'",
    "ALTER TABLE profiles ADD COLUMN night_theme TEXT",
    "ALTER TABLE profiles ADD COLUMN accent TEXT",
    "ALTER TABLE profiles ADD COLUMN wallpaper_everywhere INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE profiles ADD COLUMN hide_words TEXT",
    "ALTER TABLE devices ADD COLUMN night_weeknight_start TEXT NOT NULL DEFAULT '00:00'",
    "ALTER TABLE devices ADD COLUMN night_weekend_start TEXT NOT NULL DEFAULT '02:00'",
    "ALTER TABLE devices ADD COLUMN night_end TEXT NOT NULL DEFAULT '05:00'",
    "ALTER TABLE devices ADD COLUMN peek_s INTEGER NOT NULL DEFAULT 60",
    "ALTER TABLE devices ADD COLUMN dim_start TEXT",
    "ALTER TABLE devices ADD COLUMN dim_end TEXT",
    "ALTER TABLE devices ADD COLUMN dim_level REAL NOT NULL DEFAULT 0.5",
    "ALTER TABLE devices ADD COLUMN night_clock_font TEXT",
    "ALTER TABLE devices ADD COLUMN night_clock_color TEXT",
    "ALTER TABLE devices ADD COLUMN night_clock_photo INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE devices ADD COLUMN night_clock_tint TEXT",
    "ALTER TABLE devices ADD COLUMN photo_clock TEXT",
    "ALTER TABLE devices ADD COLUMN shape TEXT NOT NULL DEFAULT 'rect'",
    "ALTER TABLE devices ADD COLUMN circle_stack TEXT",
    "ALTER TABLE devices ADD COLUMN alternate INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE profiles ADD COLUMN dynamic_shuffle INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE profiles ADD COLUMN shuffle_hold_s INTEGER NOT NULL DEFAULT 15",
    "ALTER TABLE profiles ADD COLUMN ambient_cycle_m INTEGER NOT NULL DEFAULT 5",
    "ALTER TABLE devices ADD COLUMN dynamic_shuffle INTEGER",
    "ALTER TABLE devices ADD COLUMN shuffle_hold_s INTEGER",
    "ALTER TABLE devices ADD COLUMN ambient_cycle_m INTEGER",
    # NULL = from before screens had to be kept (settle_screens decides once).
    "ALTER TABLE devices ADD COLUMN kept INTEGER",
    "ALTER TABLE devices ADD COLUMN colour TEXT",
    "ALTER TABLE devices ADD COLUMN kind TEXT",
    "ALTER TABLE devices ADD COLUMN popups TEXT",
    "ALTER TABLE devices ADD COLUMN frame_inset INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE devices ADD COLUMN night_weekend_end TEXT",
)

# Earlier layouts kept per screen for "restore an earlier layout".
_HISTORY_KEEP = 10
_GRID_MAX_COLS = 12
_GRID_MAX_ROWS = 40


class GridItem(BaseModel):
    card: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(ge=1)
    h: int = Field(ge=1)


class PhotoClock(BaseModel):
    """How the Photo Clock draws the time over the photos (web
    cards/PhotoClock.svelte). Mirrors PhotoClockSettings in
    web/src/lib/clockface.svelte.ts."""

    font: Literal["roboto", "aileron", "fraunces", "bricolage", "anton", "cormorant"] = "roboto"
    size: Literal["s", "m", "l", "xl"] = "l"
    glass: Literal[
        "liquid",
        "frosted",
        "crystal",
        "flat",
        "mesh",
        "match",
        "opposite",
        "chrome",
        "print",
        "neon",
    ] = "liquid"
    """Glass (liquid/frosted/crystal), or a look drawn in the photo's own
    colours: a colour blend, its main colour, the colour opposite it, chrome,
    a two-ink print or neon."""
    opacity: float = Field(default=0.45, ge=0.0, le=1.0)
    """How milky the glass is: 0 is clear, 1 is close to opaque."""
    depth: bool = True
    """Tuck the time behind people in photos with a cutout."""
    date: bool = True
    face: Literal["digits", "hands"] = "digits"
    """Glass figures over full-screen photos, or a round clock: the photos in
    a disc with glass hour and minute hands (web RoundPhotoClock)."""
    seconds: bool = False
    """The round clock's second hand."""
    sweep: bool = False
    """The round clock's hands glide at 60 frames a second instead of ticking."""
    layout: Literal["row", "stack"] = "row"
    """Row keeps digits side-by-side; stack places hours over minutes."""
    drift: bool = False
    """Gentle 3D parallax zoom while each photo is on screen."""
    transition: Literal["swipe", "fade"] = "swipe"
    """Swipe slides the next photo from the side; fade dissolves softly between photos."""
    whisper: bool = False
    """Briefly reveals the memory date/year of the photo, then softly dissolves away."""
    weather: bool = False
    """Subtly shows current temperature and condition glyph in the date pill."""
    grain: float = Field(default=0.0, ge=0.0, le=0.25)
    """Subtle analog photographic film grain to soften screen glare (0 to 0.25)."""


class Grid(BaseModel):
    """A hand-placed layout from the layout builder: each card snapped to a
    cell rectangle on a ``cols``-wide grid. Rows are however many the cards
    reach. A screen without one keeps the automatic card_stack flow."""

    cols: int = Field(ge=1, le=_GRID_MAX_COLS)
    items: list[GridItem]

    @model_validator(mode="after")
    def _fits(self) -> Grid:
        seen: set[str] = set()
        for i, a in enumerate(self.items):
            if a.card in seen:
                raise ValueError(f"{a.card} is placed twice")
            seen.add(a.card)
            if a.x + a.w > self.cols or a.y + a.h > _GRID_MAX_ROWS:
                raise ValueError(f"{a.card} runs off the grid")
            for b in self.items[:i]:
                if a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h:
                    raise ValueError(f"{a.card} overlaps {b.card}")
        return self

    @property
    def rows(self) -> int:
        return max((i.y + i.h for i in self.items), default=0)

    def hero_item(self) -> GridItem | None:
        """The biggest box (first in reading order on a tie) — where a countdown
        or alert takes over, and the card that gets the hero treatment."""
        ordered = sorted(self.items, key=lambda i: (i.y, i.x))
        return max(ordered, key=lambda i: i.w * i.h, default=None)


CIRCLE_MAX = 4
"""Circle mode's card limit: the centre, the top, and two along the bottom."""


def _circle_cards(cards: list[str]) -> list[str]:
    if len(cards) > CIRCLE_MAX:
        raise ValueError(f"a round screen holds at most {CIRCLE_MAX} cards")
    if len(set(cards)) != len(cards):
        raise ValueError("a card can only be on a round screen once")
    if "clock" in cards:
        raise ValueError("a round screen's hands are its clock; leave the clock card out")
    return cards


CircleStack = Annotated[list[str], AfterValidator(_circle_cards)]
"""Circle mode's cards in slot order: the centre, then the top, then the
bottom from left to right (see web lib/round.ts)."""


class LayoutSnapshot(BaseModel):
    id: int
    saved_at: datetime
    grid: Grid | None
    """None = the automatic layout was in use."""


class Profile(BaseModel):
    id: str
    name: str
    layout: str = "wide_grid"
    card_stack: list[str] = Field(default_factory=list)
    theme: str = "blush"
    tier_default: str = "auto"
    hero_card: str | None = None
    """Pin a specific card to the hero slot, overriding the automatic pick."""
    clock_face: str | None = None
    """Push a clock face to this profile's screens (the phone /settings page);
    None leaves each screen's own local choice alone."""
    animated_background: bool = False
    """A slow diagonal drift of the theme's own colours behind the cards."""
    font: str | None = None
    """A typeface for everything but the clock, whatever the theme; None
    keeps the theme's own."""
    pace: Pace = "normal"
    """How long the rotating cards (quotes, news, cameras) hold each item."""
    photo_hold_s: int = 20
    """Seconds the photo card holds each photo before cross-fading."""
    photo_order: PhotoOrderSetting = "manual"
    photo_fit: PhotoFit = "fill"
    """``fill`` crops to the card; ``fit`` shows the whole photo, letterboxed."""
    night_theme: str | None = None
    """After sunset: None follows the theme's own night colours, ``"off"``
    keeps the day theme, any other value is the theme to switch to."""
    accent: str | None = None
    """A ``#rrggbb`` accent colour over the theme's own; None keeps it."""
    wallpaper_everywhere: bool = False
    """Show the background image behind every theme, not just Liquid Glass."""
    hide_words: list[str] = Field(default_factory=list)
    """News stories and quotes mentioning any of these are skipped."""
    dynamic_shuffle: bool = False
    """Take turns expanding each card into the large hero spotlight."""
    shuffle_hold_s: int = 15
    """How long each card stays in the hero slot before returning home."""
    ambient_cycle_m: int = 5
    """How often the full-screen photo clock automatically peeks into the card dashboard."""


Popups = Literal["all", "cameras", "none"]


class Device(BaseModel):
    id: str
    name: str
    profile_id: str
    paired_at: datetime
    last_seen: datetime | None = None
    viewport_w: int | None = None
    viewport_h: int | None = None
    tier: str | None = None
    card_stack: list[str] | None = None
    """Per-device override of the profile's stack (the layout editor writes here)."""
    layout: str | None = None
    locked: bool = False
    pair_code: str | None = None
    follow: str | None = None
    """Another device id to mirror (a setup aid)."""
    brightness: float = 1.0
    blackout_start: str | None = None
    blackout_end: str | None = None
    hero_card: str | None = None
    """Per-device override of the profile's (or automatic) hero-slot card."""
    night_clock: bool = True
    """Overnight the dashboard gives way to a lone clock (web lib/nightClock)."""
    night_clock_hold: bool = False
    """Keep the night clock up day and night, until switched off."""
    alternate: bool = False
    """Take turns: the Photo Clock for a minute, then the cards for 30 s, with
    a 2 s handoff between them (web Alternate)."""
    night_clock_font: str | None = None
    """The night clock's typeface (a FONTS id); None = its own thin serif."""
    night_clock_color: str | None = None
    """The night clock's colour (#rrggbb); None = its own soft pink."""
    night_clock_photo: bool = False
    """Clock only (held) shows the Photo Clock — the photos full screen with
    the time over them — instead of the lone clock on black."""
    night_clock_tint: str | None = None
    """The Photo Clock's glass tint: #rrggbb, "auto" (each photo's own
    colour), or None for clear icy glass."""
    photo_clock: PhotoClock | None = None
    """The Photo Clock's font, size and glass; None = its defaults."""
    cards_off: list[str] = Field(default_factory=list)
    """Cards switched off on this screen. They keep their place in card_stack,
    so switching one back on returns it to the same spot."""
    grid: Grid | None = None
    """Hand-placed layout; overrides card_stack, cards_off and hero_card."""
    shape: Literal["rect", "circle"] = "rect"
    """The rectangle of cards, or a round watch face: up to four cards in rows
    that follow the rim, under clock hands (web RoundStage)."""
    circle_stack: CircleStack | None = None
    """The round face's cards; None = the screen's first four, clock left out."""
    frame_inset: int = 0
    """Percent of the screen's width a picture frame hides on each side. The
    content moves in by that much; photos and backgrounds still fill."""
    night_weeknight_start: str = "00:00"
    """When the night clock starts before a weekday morning (Monday to Friday)."""
    night_weekend_start: str = "02:00"
    """When it starts before a Saturday or Sunday morning."""
    night_end: str = "05:00"
    """When the dashboard comes back on a weekday morning (and at the weekend,
    unless night_weekend_end says otherwise)."""
    night_weekend_end: str | None = None
    """When it comes back on a Saturday or Sunday morning; None = night_end."""
    peek_s: int = 60
    """How long a tap on the night clock shows the dashboard."""
    dim_start: str | None = None
    dim_end: str | None = None
    """A daily window when the screen dims to ``dim_level``; None = never."""
    dim_level: float = 0.5
    dynamic_shuffle: bool | None = None
    """Per-device override for dynamic card shuffle; None = inherit from profile."""
    shuffle_hold_s: int | None = None
    """Per-device override for card dwell seconds; None = inherit from profile."""
    ambient_cycle_m: int | None = None
    """Per-device override for ambient cycle minutes; None = inherit from profile."""
    kept: bool = True
    """Set up from the phone menu. A screen that isn't shows "New screen!"
    until someone keeps it (web Welcome)."""
    colour: str | None = None
    """The screen's colour in the phone menu (a SCREEN_COLOURS name)."""
    kind: str | None = None
    """What the browser said it is ("iPad", "Android tablet", …), at pairing."""
    popups: Popups | None = None
    """Which takeovers (recipes, alarms, camera views) cover this screen. None:
    all of them on the kiosk, none elsewhere (api._popups)."""


SCREEN_COLOURS = ("amber", "teal", "violet", "rose", "blue", "green")
"""Mirrors COLOURS in menu_page.py and web Welcome/Overlay."""

_FORGET_AFTER = timedelta(days=7)
"""A screen nobody kept is forgotten once it's been off this long."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Registry:
    def __init__(self, db_path: Path) -> None:
        self._path = db_path

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # timeout: retry internally instead of raising "database is locked"
        # immediately — every request opens its own short-lived connection,
        # and several devices' SSE streams resolve against this file at once.
        conn = sqlite3.connect(self._path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # WAL: readers no longer block behind a writer (or each other) — the
        # default rollback journal takes a whole-file lock on every write,
        # which a pile of concurrent /api/stream reads made easy to hit.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _init_sync(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            for statement in _MIGRATIONS:
                with contextlib.suppress(sqlite3.OperationalError):
                    conn.execute(statement)  # column already present → OperationalError
            exists = conn.execute(
                "SELECT 1 FROM profiles WHERE id = ?", (DEFAULT_PROFILE_ID,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO profiles (id, name, card_stack) VALUES (?, ?, ?)",
                    (DEFAULT_PROFILE_ID, "Default", json.dumps(_DEFAULT_STACK)),
                )

    async def retire_card(self, card_id: str, successor: str, refill: str) -> int:
        """Put ``successor`` in ``card_id``'s slot on every saved stack. Where the
        successor was already elsewhere it moves, and ``refill`` takes the slot
        it left. Returns the number of stacks changed."""
        return await asyncio.to_thread(self._retire_sync, card_id, successor, refill)

    def _retire_sync(self, card_id: str, successor: str, refill: str) -> int:
        changed = 0
        with self._connect() as conn:
            for table in ("profiles", "devices"):
                rows = conn.execute(
                    f"SELECT id, card_stack FROM {table} WHERE card_stack LIKE ?",
                    (f'%"{card_id}"%',),
                ).fetchall()
                for row in rows:
                    stack: list[str] = json.loads(row["card_stack"])
                    if successor in stack:  # it moves: refill its old slot, or drop it
                        stack = (
                            [c for c in stack if c != successor]
                            if refill in stack
                            else [refill if c == successor else c for c in stack]
                        )
                    stack = [successor if c == card_id else c for c in stack]
                    conn.execute(
                        f"UPDATE {table} SET card_stack = ? WHERE id = ?",
                        (json.dumps(stack), row["id"]),
                    )
                    changed += 1
        return changed

    # ── profiles ──────────────────────────────────────────────────────────────

    async def profile(self, profile_id: str) -> Profile | None:
        return await asyncio.to_thread(self._profile_sync, profile_id)

    def _profile_sync(self, profile_id: str) -> Profile | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return _row_to_profile(row) if row else None

    async def update_profile(self, profile_id: str, **fields: object) -> Profile | None:
        return await asyncio.to_thread(self._update_profile_sync, profile_id, fields)

    def _update_profile_sync(self, profile_id: str, fields: dict[str, object]) -> Profile | None:
        allowed = {
            "name",
            "layout",
            "theme",
            "tier_default",
            "card_stack",
            "hero_card",
            "clock_face",
            "animated_background",
            "font",
            "pace",
            "photo_hold_s",
            "photo_order",
            "photo_fit",
            "night_theme",
            "accent",
            "wallpaper_everywhere",
            "hide_words",
            "dynamic_shuffle",
            "shuffle_hold_s",
            "ambient_cycle_m",
        }
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        for key in ("card_stack", "hide_words"):
            if key in sets and not isinstance(sets[key], str):
                sets[key] = json.dumps(sets[key])
        for key in (
            "hero_card",
            "clock_face",
            "font",
            "night_theme",
            "accent",
            "dynamic_shuffle",
            "shuffle_hold_s",
            "ambient_cycle_m",
        ):
            if sets.get(key) == "":  # empty string clears it
                sets[key] = None
        for key in ("animated_background", "wallpaper_everywhere", "dynamic_shuffle"):
            if key in sets and sets[key] is not None:
                sets[key] = int(bool(sets[key]))
        with self._connect() as conn:
            if sets:
                assignments = ", ".join(f"{k} = ?" for k in sets)  # keys allow-listed above
                conn.execute(
                    f"UPDATE profiles SET {assignments} WHERE id = ?",
                    (*sets.values(), profile_id),
                )
            row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return _row_to_profile(row) if row else None

    async def profiles(self) -> list[Profile]:
        return await asyncio.to_thread(self._profiles_sync)

    def _profiles_sync(self) -> list[Profile]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM profiles ORDER BY name").fetchall()
        return [_row_to_profile(r) for r in rows]

    async def create_profile(self, name: str, template: Profile | None = None) -> Profile:
        return await asyncio.to_thread(self._create_profile_sync, name, template)

    def _create_profile_sync(self, name: str, template: Profile | None) -> Profile:
        profile_id = secrets.token_hex(6)
        base = template or Profile(id=profile_id, name=name)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO profiles (id, name, layout, card_stack, theme, tier_default)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    profile_id,
                    name,
                    base.layout,
                    json.dumps(base.card_stack),
                    base.theme,
                    base.tier_default,
                ),
            )
        # A copy carries the template's look and preferences too.
        carried = (
            template.model_dump(exclude={"id", "name", "layout", "card_stack", "theme"})
            if template
            else {}
        )
        made = self._update_profile_sync(profile_id, carried)
        assert made is not None  # just inserted
        return made

    async def restore_profile(self, profile: Profile) -> Profile:
        """Write ``profile`` back under its own id (a settings restore),
        creating it when this server doesn't have it."""
        return await asyncio.to_thread(self._restore_profile_sync, profile)

    def _restore_profile_sync(self, profile: Profile) -> Profile:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO profiles (id, name) VALUES (?, ?)",
                (profile.id, profile.name),
            )
        fields = {k: "" if v is None else v for k, v in profile.model_dump().items()}
        made = self._update_profile_sync(profile.id, fields)
        assert made is not None
        return made

    async def delete_profile(self, profile_id: str) -> str | None:
        """Returns None on success, or a reason string it can't be deleted."""
        return await asyncio.to_thread(self._delete_profile_sync, profile_id)

    def _delete_profile_sync(self, profile_id: str) -> str | None:
        if profile_id == DEFAULT_PROFILE_ID:
            return "the default profile can't be deleted"
        with self._connect() as conn:
            in_use = conn.execute(
                "SELECT COUNT(*) FROM devices WHERE profile_id = ?", (profile_id,)
            ).fetchone()[0]
            if in_use:
                return f"{in_use} device(s) still use this profile"
            deleted = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,)).rowcount
        return None if deleted else "unknown profile"

    # ── devices ───────────────────────────────────────────────────────────────

    async def pair_device(
        self,
        name: str,
        viewport: tuple[int, int] | None = None,
        kind: str | None = None,
        *,
        kept: bool = False,
    ) -> Device:
        return await asyncio.to_thread(self._pair_sync, name, viewport, kind, kept)

    def _pair_sync(
        self, name: str, viewport: tuple[int, int] | None, kind: str | None, kept: bool
    ) -> Device:
        device_id = secrets.token_hex(8)
        pair_code = f"{secrets.randbelow(10000):04d}"
        vw, vh = viewport or (None, None)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO devices (id, name, profile_id, paired_at, viewport_w, viewport_h,"
                " pair_code, locked, kept, kind) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (device_id, name, DEFAULT_PROFILE_ID, _now(), vw, vh, pair_code, int(kept), kind),
            )
            row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return _row_to_device(row)

    async def adopt_device(self, device_id: str, *, kept: bool | None = None) -> Device:
        """Register ``device_id`` as a fresh screen on the default profile. For a
        kiosk failing over from another server that paired it there, or a
        browser still holding the id of a screen that was forgotten
        (``kept=False``: it shows "New screen!" again instead of hanging)."""
        return await asyncio.to_thread(self._adopt_sync, device_id, kept)

    def _adopt_sync(self, device_id: str, kept: bool | None) -> Device:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO devices (id, name, profile_id, paired_at, locked, kept)"
                " VALUES (?, 'Screen', ?, ?, 1, ?)",
                (device_id, DEFAULT_PROFILE_ID, _now(), None if kept is None else int(kept)),
            )
            row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return _row_to_device(row)

    async def keep_device(self, device_id: str, name: str, colour: str) -> Device | None:
        """Set up a new screen: its name, colour and its own copy of the
        default profile, so its theme and cards never change another screen's."""
        return await asyncio.to_thread(self._keep_sync, device_id, name, colour)

    def _keep_sync(self, device_id: str, name: str, colour: str) -> Device | None:
        device = self._device_sync(device_id)
        if device is None:
            return None
        profile_id = device.profile_id
        if profile_id == DEFAULT_PROFILE_ID:
            template = self._profile_sync(DEFAULT_PROFILE_ID)
            profile_id = self._create_profile_sync(name, template).id
        with self._connect() as conn:
            conn.execute(
                "UPDATE devices SET kept = 1, name = ?, colour = ?, profile_id = ? WHERE id = ?",
                (name, colour, profile_id, device_id),
            )
        return self._device_sync(device_id)

    async def forget_device(self, device_id: str) -> bool:
        """Send a screen back to "New screen!": every setting cleared, its own
        profile dropped. The id stays, so the browser holding it needn't pair again."""
        return await asyncio.to_thread(self._forget_sync, device_id)

    def _forget_sync(self, device_id: str) -> bool:
        device = self._device_sync(device_id)
        if device is None:
            return False
        with self._connect() as conn:
            conn.execute("DELETE FROM layout_history WHERE device_id = ?", (device_id,))
            conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
            conn.execute(
                "INSERT INTO devices (id, name, profile_id, paired_at, last_seen, viewport_w,"
                " viewport_h, pair_code, locked, kept, kind)"
                " VALUES (?, 'Screen', ?, ?, ?, ?, ?, ?, 1, 0, ?)",
                (
                    device_id,
                    DEFAULT_PROFILE_ID,
                    device.paired_at.isoformat(),
                    device.last_seen.isoformat() if device.last_seen else None,
                    device.viewport_w,
                    device.viewport_h,
                    device.pair_code,
                    device.kind,
                ),
            )
        if device.profile_id != DEFAULT_PROFILE_ID:
            self._delete_profile_sync(device.profile_id)  # refuses if another screen uses it
        return True

    async def replace_device(self, device_id: str, old_id: str) -> Device | None:
        """A screen that's the same tablet as ``old_id`` (its browser lost the
        id, or it opened from a home-screen icon with storage of its own): take
        over everything of the old one but its id and size, and drop the old."""
        return await asyncio.to_thread(self._replace_sync, device_id, old_id)

    def _replace_sync(self, device_id: str, old_id: str) -> Device | None:
        own = {"id", "paired_at", "last_seen", "viewport_w", "viewport_h", "pair_code", "kind"}
        with self._connect() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(devices)") if r[1] not in own]
            if conn.execute("SELECT 1 FROM devices WHERE id = ?", (old_id,)).fetchone() is None:
                return None
            assignments = ", ".join(f"{c} = (SELECT {c} FROM devices WHERE id = ?)" for c in cols)
            conn.execute(
                f"UPDATE devices SET {assignments} WHERE id = ?",  # names from the schema
                (*([old_id] * len(cols)), device_id),
            )
            conn.execute(
                "UPDATE layout_history SET device_id = ? WHERE device_id = ?", (device_id, old_id)
            )
            conn.execute("DELETE FROM devices WHERE id = ?", (old_id,))
        return self._device_sync(device_id)

    async def settle_screens(self, home_screen: str | None) -> int:
        """Keep ``home_screen`` (the kiosk), decide once for screens from before
        screens were kept, and forget the ones nobody kept that have been off a
        week. Returns how many were forgotten."""
        return await asyncio.to_thread(self._settle_sync, home_screen)

    def _settle_sync(self, home_screen: str | None) -> int:
        cutoff = (datetime.now(UTC) - _FORGET_AFTER).isoformat()
        with self._connect() as conn:
            if home_screen:
                conn.execute(
                    "UPDATE devices SET kept = 1, colour = COALESCE(colour, 'amber') WHERE id = ?",
                    (home_screen,),
                )
                # Old records were all "Screen": only the kiosk's is worth keeping.
                conn.execute("UPDATE devices SET kept = (name != 'Screen') WHERE kept IS NULL")
            else:
                conn.execute("UPDATE devices SET kept = 1 WHERE kept IS NULL")
            gone = [
                r[0]
                for r in conn.execute(
                    "SELECT id FROM devices WHERE kept = 0 AND id != ?"
                    " AND COALESCE(last_seen, paired_at) < ?",
                    (home_screen or "", cutoff),
                )
            ]
            for device_id in gone:
                conn.execute("DELETE FROM layout_history WHERE device_id = ?", (device_id,))
                conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return len(gone)

    async def device(self, device_id: str) -> Device | None:
        return await asyncio.to_thread(self._device_sync, device_id)

    def _device_sync(self, device_id: str) -> Device | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return _row_to_device(row) if row else None

    async def devices(self) -> list[Device]:
        return await asyncio.to_thread(self._devices_sync)

    def _devices_sync(self) -> list[Device]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM devices ORDER BY paired_at").fetchall()
        return [_row_to_device(r) for r in rows]

    async def update_device(self, device_id: str, **fields: object) -> Device | None:
        return await asyncio.to_thread(self._update_device_sync, device_id, fields)

    def _update_device_sync(self, device_id: str, fields: dict[str, object]) -> Device | None:
        allowed = {
            "name",
            "profile_id",
            "tier",
            "last_seen",
            "viewport_w",
            "viewport_h",
            "card_stack",
            "layout",
            "locked",
            "follow",
            "brightness",
            "blackout_start",
            "blackout_end",
            "hero_card",
            "cards_off",
            "night_clock",
            "night_clock_hold",
            "alternate",
            "night_weeknight_start",
            "night_weekend_start",
            "night_end",
            "night_weekend_end",
            "peek_s",
            "dim_start",
            "dim_end",
            "dim_level",
            "night_clock_font",
            "night_clock_color",
            "night_clock_photo",
            "night_clock_tint",
            "photo_clock",
            "shape",
            "circle_stack",
            "frame_inset",
            "dynamic_shuffle",
            "shuffle_hold_s",
            "ambient_cycle_m",
            "colour",
            "popups",
        }
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if sets.get("circle_stack") == []:  # an empty list goes back to the default
            sets["circle_stack"] = None
        for key in ("card_stack", "cards_off", "photo_clock", "circle_stack"):
            if key in sets and sets[key] is not None and not isinstance(sets[key], str):
                sets[key] = json.dumps(sets[key])
        for key in (
            "card_stack",
            "hero_card",
            "follow",
            "blackout_start",
            "blackout_end",
            "night_weekend_end",
            "dim_start",
            "dim_end",
            "night_clock_font",
            "night_clock_color",
            "night_clock_tint",
            "photo_clock",
            "circle_stack",
            "dynamic_shuffle",
            "shuffle_hold_s",
            "ambient_cycle_m",
        ):
            if sets.get(key) == "":  # empty string clears it
                sets[key] = None
        for key in (
            "locked",
            "night_clock",
            "night_clock_hold",
            "night_clock_photo",
            "alternate",
            "dynamic_shuffle",
        ):
            if key in sets and sets[key] is not None:
                sets[key] = int(bool(sets[key]))
        with self._connect() as conn:
            if sets:
                assignments = ", ".join(f"{k} = ?" for k in sets)  # keys are allow-listed above
                conn.execute(
                    f"UPDATE devices SET {assignments} WHERE id = ?",
                    (*sets.values(), device_id),
                )
            row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return _row_to_device(row) if row else None

    async def set_grid(self, device_id: str, grid: Grid | None) -> Device | None:
        """Replace the screen's layout (None = back to automatic), keeping the
        one it replaces in its history."""
        return await asyncio.to_thread(self._set_grid_sync, device_id, grid)

    def _set_grid_sync(self, device_id: str, grid: Grid | None) -> Device | None:
        with self._connect() as conn:
            row = conn.execute("SELECT grid FROM devices WHERE id = ?", (device_id,)).fetchone()
            if row is None:
                return None
            new = grid.model_dump_json() if grid else None
            if row["grid"] != new:
                conn.execute(
                    "INSERT INTO layout_history (device_id, saved_at, grid) VALUES (?, ?, ?)",
                    (device_id, _now(), row["grid"]),
                )
                conn.execute(
                    "DELETE FROM layout_history WHERE device_id = ? AND id NOT IN"
                    " (SELECT id FROM layout_history WHERE device_id = ?"
                    "  ORDER BY id DESC LIMIT ?)",
                    (device_id, device_id, _HISTORY_KEEP),
                )
                conn.execute("UPDATE devices SET grid = ? WHERE id = ?", (new, device_id))
            row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return _row_to_device(row)

    async def layout_history(self, device_id: str) -> list[LayoutSnapshot]:
        return await asyncio.to_thread(self._layout_history_sync, device_id)

    def _layout_history_sync(self, device_id: str) -> list[LayoutSnapshot]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, saved_at, grid FROM layout_history WHERE device_id = ?"
                " ORDER BY id DESC",
                (device_id,),
            ).fetchall()
        return [
            LayoutSnapshot(
                id=r["id"],
                saved_at=datetime.fromisoformat(r["saved_at"]),
                grid=Grid.model_validate_json(r["grid"]) if r["grid"] else None,
            )
            for r in rows
        ]

    async def custom_themes(self) -> list[Theme]:
        return await asyncio.to_thread(self._custom_themes_sync)

    def _custom_themes_sync(self) -> list[Theme]:
        with self._connect() as conn:
            rows = conn.execute("SELECT theme FROM custom_themes ORDER BY rowid").fetchall()
        return [Theme.model_validate_json(r["theme"]) for r in rows]

    async def save_custom_theme(self, theme: Theme) -> None:
        await asyncio.to_thread(self._save_custom_theme_sync, theme)

    def _save_custom_theme_sync(self, theme: Theme) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO custom_themes (name, theme) VALUES (?, ?)"
                " ON CONFLICT(name) DO UPDATE SET theme = excluded.theme",
                (theme.name, theme.model_dump_json()),
            )

    async def delete_custom_theme(self, name: str) -> bool:
        return await asyncio.to_thread(self._delete_custom_theme_sync, name)

    def _delete_custom_theme_sync(self, name: str) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM custom_themes WHERE name = ?", (name,)).rowcount > 0

    async def touch(self, device_id: str) -> None:
        await self.update_device(device_id, last_seen=_now())

    async def delete_device(self, device_id: str) -> bool:
        return await asyncio.to_thread(self._delete_device_sync, device_id)

    def _delete_device_sync(self, device_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM layout_history WHERE device_id = ?", (device_id,))
            cursor = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return cursor.rowcount > 0


def _row_to_profile(row: sqlite3.Row) -> Profile:
    cols = set(row.keys())
    return Profile(
        id=row["id"],
        name=row["name"],
        layout=row["layout"],
        card_stack=json.loads(row["card_stack"]),
        theme=row["theme"],
        tier_default=row["tier_default"],
        hero_card=row["hero_card"] if "hero_card" in cols else None,
        clock_face=row["clock_face"] if "clock_face" in cols else None,
        animated_background=bool(row["animated_background"])
        if "animated_background" in cols
        else False,
        font=row["font"] if "font" in cols else None,
        pace=row["pace"] if "pace" in cols else "normal",
        photo_hold_s=row["photo_hold_s"] if "photo_hold_s" in cols else 20,
        photo_order=row["photo_order"] if "photo_order" in cols else "manual",
        photo_fit=row["photo_fit"] if "photo_fit" in cols else "fill",
        night_theme=row["night_theme"] if "night_theme" in cols else None,
        accent=row["accent"] if "accent" in cols else None,
        wallpaper_everywhere=bool(row["wallpaper_everywhere"])
        if "wallpaper_everywhere" in cols
        else False,
        hide_words=json.loads(row["hide_words"])
        if "hide_words" in cols and row["hide_words"]
        else [],
        dynamic_shuffle=bool(row["dynamic_shuffle"])
        if "dynamic_shuffle" in cols and row["dynamic_shuffle"] not in (None, "")
        else False,
        shuffle_hold_s=int(row["shuffle_hold_s"])
        if "shuffle_hold_s" in cols and row["shuffle_hold_s"] not in (None, "")
        else 15,
        ambient_cycle_m=int(row["ambient_cycle_m"])
        if "ambient_cycle_m" in cols and row["ambient_cycle_m"] not in (None, "")
        else 5,
    )


def _row_to_device(row: sqlite3.Row) -> Device:
    cols = set(row.keys())
    raw_stack = row["card_stack"] if "card_stack" in cols else None
    return Device(
        id=row["id"],
        name=row["name"],
        profile_id=row["profile_id"],
        paired_at=datetime.fromisoformat(row["paired_at"]),
        last_seen=datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None,
        viewport_w=row["viewport_w"],
        viewport_h=row["viewport_h"],
        tier=row["tier"],
        card_stack=json.loads(raw_stack) if raw_stack else None,
        layout=row["layout"] if "layout" in cols else None,
        locked=bool(row["locked"]) if "locked" in cols else False,
        pair_code=row["pair_code"] if "pair_code" in cols else None,
        follow=row["follow"] if "follow" in cols else None,
        brightness=row["brightness"] if "brightness" in cols else 1.0,
        blackout_start=row["blackout_start"] if "blackout_start" in cols else None,
        blackout_end=row["blackout_end"] if "blackout_end" in cols else None,
        hero_card=row["hero_card"] if "hero_card" in cols else None,
        night_clock=bool(row["night_clock"]) if "night_clock" in cols else True,
        night_clock_hold=bool(row["night_clock_hold"]) if "night_clock_hold" in cols else False,
        night_clock_photo=bool(row["night_clock_photo"]) if "night_clock_photo" in cols else False,
        alternate=bool(row["alternate"]) if "alternate" in cols else False,
        cards_off=json.loads(row["cards_off"]) if "cards_off" in cols and row["cards_off"] else [],
        grid=Grid.model_validate_json(row["grid"]) if "grid" in cols and row["grid"] else None,
        photo_clock=_photo_clock(row["photo_clock"]) if "photo_clock" in cols else None,
        shape="circle" if "shape" in cols and row["shape"] == "circle" else "rect",
        circle_stack=_circle_stack(row["circle_stack"]) if "circle_stack" in cols else None,
        frame_inset=int(row["frame_inset"]) if "frame_inset" in cols else 0,
        dynamic_shuffle=bool(row["dynamic_shuffle"])
        if "dynamic_shuffle" in cols and row["dynamic_shuffle"] not in (None, "")
        else None,
        shuffle_hold_s=int(row["shuffle_hold_s"])
        if "shuffle_hold_s" in cols and row["shuffle_hold_s"] not in (None, "")
        else None,
        ambient_cycle_m=int(row["ambient_cycle_m"])
        if "ambient_cycle_m" in cols and row["ambient_cycle_m"] not in (None, "")
        else None,
        kept=bool(row["kept"]) if "kept" in cols and row["kept"] is not None else True,
        colour=row["colour"] if "colour" in cols else None,
        kind=row["kind"] if "kind" in cols else None,
        popups=row["popups"] if "popups" in cols and row["popups"] else None,
        **{k: row[k] for k in _DEVICE_SCHEDULE_COLS if k in cols},
    )


def _circle_stack(raw: str | None) -> list[str] | None:
    """A stored round-face card list, or None (the default) when absent or unreadable."""
    if not raw:
        return None
    try:
        return _circle_cards(json.loads(raw))
    except ValueError:
        return None


def _photo_clock(raw: str | None) -> PhotoClock | None:
    """A stored Photo Clock, or None (its defaults) when absent or unreadable."""
    if not raw:
        return None
    try:
        return PhotoClock.model_validate_json(raw)
    except ValueError:
        return None


# Device columns read straight across (NOT NULL defaults or plain nullable).
_DEVICE_SCHEDULE_COLS = (
    "night_weeknight_start",
    "night_weekend_start",
    "night_end",
    "night_weekend_end",
    "peek_s",
    "dim_start",
    "dim_end",
    "dim_level",
    "night_clock_font",
    "night_clock_color",
    "night_clock_tint",
)
