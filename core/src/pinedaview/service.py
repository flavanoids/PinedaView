# SPDX-License-Identifier: Apache-2.0
"""Runs the API server. The scheduler and timer loops live inside the app's
lifespan, so this is just uvicorn."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import uvicorn
from watchfiles import awatch

from pinedaview.api import create_app
from pinedaview.cards import CardRegistry
from pinedaview.config import Settings
from pinedaview.runtime import Runtime, build_runtime

logger = logging.getLogger(__name__)


async def _watch_cards(runtime: Runtime) -> None:
    """Reload card manifests when a card.json changes. Providers still need a
    restart to pick up a new feed; statuses and the picker update live."""
    watch_dir = runtime.settings.cards_dir
    if not watch_dir.is_dir():
        return
    logger.info("watching %s for card changes", watch_dir)
    async for _changes in awatch(watch_dir):
        runtime.cards = CardRegistry.load(watch_dir, set(runtime.settings.disabled_cards))
        runtime.resolve_cards()
        runtime.broadcaster.publish({"type": "config", "reason": "cards-reloaded"})
        logger.info("reloaded cards: %s", ", ".join(runtime.cards.ready_ids()))


async def run_api(settings: Settings, *, watch: bool = False) -> None:
    runtime = build_runtime(settings)
    app = create_app(runtime)
    watcher: asyncio.Task[None] | None = (
        asyncio.create_task(_watch_cards(runtime)) if watch else None
    )
    logger.info(
        "serving on http://%s:%d  location=%r providers=%s",
        settings.api.host,
        settings.api.port,
        settings.location.query,
        ",".join(runtime.scheduler.provider_keys),
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=settings.api.host,
            port=settings.api.port,
            log_config=None,
            timeout_graceful_shutdown=5,
        )
    )
    try:
        await server.serve()
    finally:
        if watcher is not None:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
