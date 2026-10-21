# SPDX-License-Identifier: Apache-2.0
"""Full-screen takeovers: one card that covers every screen until it's
dismissed or its time runs out.

A voice assistant (Antigua) puts a recipe up here when it starts reading one,
or a live camera when someone's at the door, and takes it down on "stop the
display". Only one is up at a time; a new one
replaces the old. In memory only — a takeover lasts a couple of minutes, not
across a restart."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from pinedaview.broadcast import Broadcaster

_TICK_SECONDS = 0.5
_MAX_SECONDS = 3600


class IngredientGroup(BaseModel):
    name: str = ""
    """"For the frosting" — empty for an ungrouped list."""
    items: list[str]


class IngredientSwap(BaseModel):
    index: int = Field(ge=0)
    use: str
    """What the cook is using instead, shown after the struck-out line."""


Index = Annotated[int, Field(ge=0)]


class RecipeTakeover(BaseModel):
    """A recipe. Ingredient indexes count lines across the groups, in the
    order they're listed here; ones past the end are ignored."""

    kind: Literal["recipe", "howto"] = "recipe"
    """"howto" for a household guide (supplies instead of ingredients)."""
    title: str
    source: str = ""
    servings: str = ""
    total_min: int = 0
    ingredients: list[IngredientGroup]
    steps: list[str]
    caution: str = ""
    """A fixed safety line for a guide that involves power tools, ladders,
    harsh chemicals and the like; shown the whole time it's up."""
    stage: Literal["ingredients", "steps"] | None = None
    """What's being read: the ingredient list or the steps. None goes by
    current_step (steps once there is one)."""
    current_step: int | None = Field(default=None, ge=0)
    """The step being read aloud (0-based), highlighted; None for none."""
    current_ingredients: list[Index] = []
    """Lines highlighted: the one being checked or asked about, or the ones
    the current step uses."""
    checked: list[Index] = []
    """Lines the cook already said they have."""
    skipped: list[Index] = []
    """Lines being left out, struck through."""
    swaps: list[IngredientSwap] = []


class CameraTakeover(BaseModel):
    """A camera's live video, full screen. With Home Assistant configured
    (CameraService) this server starts the livestream while it's up;
    otherwise whoever put it up does."""

    kind: Literal["camera"]
    camera: str
    """A name from [cameras.streams]."""
    title: str = ""
    """"Front door"."""
    caption: str = ""
    """Under the video: "Identifying…", then who it is."""
    pip_camera: str | None = None
    """An optional second camera in [cameras.streams] for Picture-in-Picture."""
    pip_title: str = ""
    """"Garage"."""


class AlarmTakeover(BaseModel):
    """An alarm going off: its time and label, big, until it's dismissed."""

    kind: Literal["alarm"]
    label: str
    fires_at: datetime


class ImageItem(BaseModel):
    id: str
    """Letter or numeral: 'A', 'B', '1', '2'."""
    url: str
    """Direct image URL."""
    thumb_url: str | None = None
    """Optional fast thumbnail URL."""
    title: str = ""
    """Image or source title."""
    source: str = ""
    """Host or publisher domain: 'wikipedia.org', 'unsplash.com'."""
    snippet: str = ""
    """Context snippet or caption."""
    aspect_ratio: float = 1.0
    """Width / height ratio for layout packing."""


class ImageSearchTakeover(BaseModel):
    """A visual collage of image search results, tiled in an interlocking
    mosaic layout with letter badges (A, B, C...) for voice-guided inspection."""

    kind: Literal["image_search"] = "image_search"
    query: str
    images: list[ImageItem]
    highlight: str | None = None
    """Currently highlighted image id ('A', 'B', etc.), or None."""


ALARM_SECONDS = 600
"""How long a ringing alarm stays up if nobody dismisses it."""

Card = RecipeTakeover | CameraTakeover | AlarmTakeover | ImageSearchTakeover


class TakeoverRequest(BaseModel):
    card: Card
    seconds: float = Field(default=120, gt=0, le=_MAX_SECONDS)


class TakeoverUpdate(BaseModel):
    """What's being read on the card that's up. Only the fields sent change;
    the rest keep their values."""

    stage: Literal["ingredients", "steps"] | None = None
    current_step: int | None = Field(default=None, ge=0)
    current_ingredients: list[Index] | None = None
    checked: list[Index] | None = None
    skipped: list[Index] | None = None
    swaps: list[IngredientSwap] | None = None
    caption: str | None = None
    """A camera's caption (who's at the door, once known)."""
    highlight: str | None = None
    """For an image search takeover: which image is highlighted ('A', 'B'...)."""


class Takeover(BaseModel):
    card: Card
    shown_at: datetime
    expires_at: datetime


def _same_camera(a: Card, b: CameraTakeover) -> bool:
    return (
        isinstance(a, CameraTakeover)
        and a.camera == b.camera
        and a.pip_camera == b.pip_camera
    )


def _with(card: Card, fields: dict[str, object]) -> Card:
    allowed = set(type(card).model_fields.keys())
    applicable = {k: v for k, v in fields.items() if k in allowed}
    return type(card).model_validate({**card.model_dump(), **applicable})


class TakeoverService:
    """The one card that's up. A camera interrupts: put up over a recipe (or
    an alarm), it sets that card aside, its clock stopped, and brings it
    back when the camera's time runs out or it's released — the screen goes
    back to what it was doing. Clearing ("stop the display") takes both."""

    def __init__(self, broadcaster: Broadcaster) -> None:
        self._broadcaster = broadcaster
        self._current: Takeover | None = None
        self._aside: tuple[Card, timedelta, timedelta] | None = None
        """The card a camera interrupted: (card, time it had left, its full time)."""
        self._listeners: list[Callable[[Takeover | None], None]] = []

    @property
    def covering(self) -> Card | None:
        """The card a camera that's up set aside, to come back after it."""
        return self._aside[0] if self._aside is not None else None

    def on_change(self, listener: Callable[[Takeover | None], None]) -> None:
        """Called with the card that's up (None for none) after every show,
        restore, clear and expiry — not for a change to what's being read."""
        self._listeners.append(listener)

    def current(self, now: datetime | None = None) -> Takeover | None:
        cur = self._current
        if cur is not None and cur.expires_at <= (now or datetime.now(UTC)):
            return None
        return cur

    def show(self, card: Card, seconds: float) -> Takeover:
        now = datetime.now(UTC)
        cur = self.current(now)
        until = now + timedelta(seconds=seconds)
        if isinstance(card, CameraTakeover):
            if isinstance(cur, Takeover) and _same_camera(cur.card, card):
                # Already watching it: more time, not a fresh card (the
                # screen doesn't play the opening again).
                self._current = cur.model_copy(update={"expires_at": max(cur.expires_at, until)})
                self._broadcaster.publish({"type": "takeover", "action": "update"})
                return self._current
            if cur is not None and not isinstance(cur.card, CameraTakeover):
                self._aside = (cur.card, cur.expires_at - now, cur.expires_at - cur.shown_at)
        else:
            self._aside = None
        self._current = Takeover(card=card, shown_at=now, expires_at=until)
        self._publish("show")
        return self._current

    def update(self, change: TakeoverUpdate) -> Takeover | None:
        """Change what's being read on the card that's up — only the fields
        `change` sets — keeping its time left. Nothing up (dismissed,
        expired) stays that way: None. A recipe set aside under a camera
        keeps up with the reading, so it comes back on the right step."""
        cur = self.current()
        if cur is None:
            return None
        sent = change.model_dump(exclude_unset=True)
        # Lists can't be None on the card; a null sent for one clears it.
        fields = {
            k: ([] if v is None and k not in ("stage", "current_step", "caption") else v)
            for k, v in sent.items()
        }
        if fields.get("caption") is None:
            fields.pop("caption", None)
        if isinstance(cur.card, CameraTakeover) and self._aside is not None:
            card, left, total = self._aside
            reading = {k: v for k, v in fields.items() if k != "caption"}
            if reading:
                self._aside = (_with(card, reading), left, total)
        # Fields for the other kind of card are ignored.
        self._current = cur.model_copy(update={"card": _with(cur.card, fields)})
        self._broadcaster.publish({"type": "takeover", "action": "update"})
        return self._current

    def clear(self) -> bool:
        self._aside = None
        if self._current is None:
            return False
        self._current = None
        self._publish("clear")
        return True

    def release(self, camera: str | None = None) -> bool:
        """End the camera that's up (`camera`, or any): the card it set aside
        comes back, else the screen. False when no (such) camera was up."""
        cur = self.current()
        if cur is None or not isinstance(cur.card, CameraTakeover):
            return False
        if camera is not None and cur.card.camera != camera:
            return False
        self._end_camera(datetime.now(UTC))
        return True

    def _end_camera(self, now: datetime) -> None:
        aside, self._aside = self._aside, None
        if aside is None or aside[1] <= timedelta(0):
            self._current = None
            self._publish("clear")
            return
        card, left, total = aside
        # Its clock picks up where it stopped; the drain shows the same share left.
        self._current = Takeover(card=card, shown_at=now + left - total, expires_at=now + left)
        self._publish("show")

    def _publish(self, action: str) -> None:
        self._broadcaster.publish({"type": "takeover", "action": action})
        for listener in self._listeners:
            listener(self._current)

    def _expire(self, now: datetime) -> None:
        cur = self._current
        if cur is not None and cur.expires_at <= now:
            if isinstance(cur.card, CameraTakeover):
                self._end_camera(now)
            else:
                self.clear()

    async def run(self) -> None:
        while True:
            await asyncio.sleep(_TICK_SECONDS)
            self._expire(datetime.now(UTC))
