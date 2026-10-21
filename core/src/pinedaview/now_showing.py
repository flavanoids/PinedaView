# SPDX-License-Identifier: Apache-2.0
"""What each screen is showing right now, as reported by the screen itself.

The photo slideshow and the quote rotation run client-side, so only the
browser knows which photo or quote is up. The cards report each change here
(``POST /api/now-showing``) and a voice assistant asks (``GET``) to answer
"when was this photo taken?" or "who said that?". Held in memory only — a
restart forgets it until the next swap, at most one dwell later.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

ShownCard = Literal["photo", "quote"]


class ShownItem(BaseModel):
    item: str
    since: datetime


class NowShowingReport(BaseModel):
    device_id: str
    card: ShownCard
    item: str


class ScreenLook(BaseModel):
    """The bits of a screen's look that live in its own browser (launch-URL
    flags and localStorage), reported so the phone menu's live miniature can
    draw it the same way."""

    clock_face: str = Field(max_length=24)
    pi: bool
    scale: float = Field(gt=0, le=4)


class ScreenLookReport(ScreenLook):
    device_id: str


class NowShowingStore:
    def __init__(self) -> None:
        self._by_device: dict[str, dict[str, ShownItem]] = {}
        self._looks: dict[str, ScreenLook] = {}

    def report_look(self, device_id: str, look: ScreenLook) -> None:
        self._looks[device_id] = look

    def look(self, device_id: str | None) -> ScreenLook | None:
        return self._looks.get(device_id) if device_id is not None else None

    def report(self, device_id: str, card: ShownCard, item: str) -> None:
        shown = ShownItem(item=item, since=datetime.now(UTC))
        self._by_device.setdefault(device_id, {})[card] = shown

    def get(self, card: ShownCard, device_id: str | None = None) -> ShownItem | None:
        """The item on ``device_id``, or — with no device named — the most
        recent report from any screen."""
        if device_id is not None:
            return self._by_device.get(device_id, {}).get(card)
        reports = [cards[card] for cards in self._by_device.values() if card in cards]
        return max(reports, key=lambda s: s.since, default=None)
