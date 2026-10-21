# SPDX-License-Identifier: Apache-2.0
"""On this day — a photo taken on today's month/day in a past year, from the
household's own photo library. Local filesystem + EXIF only, no network.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.photos import PhotoStore
from pinedaview.providers.base import Provider, ProviderContext


class OnThisDayProvider(Provider):
    key = "onThisDay"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:  # noqa: ARG002
        # The match only changes once a day — no need to re-scan often.
        return 3600

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        store = PhotoStore(ctx.settings.photos_dir)
        # The household's own calendar day, not UTC's — matters near midnight.
        now = datetime.now().astimezone()
        match = store.on_this_day(now.date())
        if match is None or match.taken_at is None:
            return {}
        taken = datetime.fromtimestamp(match.taken_at, tz=UTC)
        return {"name": match.name, "yearsAgo": now.year - taken.year}
