# SPDX-License-Identifier: Apache-2.0
"""Runs every provider on its own loop: poll, publish, sleep, repeat."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from pinedaview.config import Settings
from pinedaview.providers.base import Provider, ProviderContext, ProviderError
from pinedaview.secrets import SecretStore
from pinedaview.stores import Store, StoreRegistry

logger = logging.getLogger(__name__)

_STALE_INTERVAL_MULTIPLE = 2


ProviderSource = list[Provider] | Callable[[], list[Provider]]


class Scheduler:
    """Owns one poll loop per provider. ``sync()`` reconciles the running loops
    against the current provider list, so cards that become ready (a secret was
    added) start fetching without a restart."""

    def __init__(
        self,
        settings: Settings,
        registry: StoreRegistry,
        providers: ProviderSource,
        *,
        secrets: SecretStore | None = None,
        card_settings: dict[str, dict[str, Any]] | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._source = providers
        self._secrets = secrets
        self._card_settings = card_settings
        self._client = client
        self._sleep = sleep  # injectable for tests
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._ctx: ProviderContext | None = None

    def _current_providers(self) -> list[Provider]:
        return self._source() if callable(self._source) else self._source

    @property
    def provider_keys(self) -> list[str]:
        return sorted(self._tasks) if self._tasks else [p.key for p in self._current_providers()]

    async def run(self) -> None:
        self._ctx = ProviderContext(
            self._settings,
            self._registry,
            secrets=self._secrets,
            card_settings=self._card_settings,
            client=self._client,
        )
        self.sync()
        stop = asyncio.Event()
        try:
            await stop.wait()
        finally:
            for task in self._tasks.values():
                task.cancel()
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
            self._tasks.clear()

    def sync(self) -> None:
        """Start loops for newly-ready providers, cancel loops for gone ones.
        Idempotent; a no-op until ``run()`` has started."""
        if self._ctx is None:
            return
        wanted = {p.key: p for p in self._current_providers()}
        for key in list(self._tasks):
            if key not in wanted:
                self._tasks.pop(key).cancel()
                logger.info("stopped provider=%s", key)
        for key, provider in wanted.items():
            if key not in self._tasks:
                self._tasks[key] = asyncio.create_task(
                    self._loop(provider, self._ctx), name=f"provider:{key}"
                )
                logger.info("started provider=%s", key)

    def refresh(self, key: str) -> None:
        """Poll ``key``'s provider now instead of at its next turn — its card's
        settings just changed. A no-op for a provider that isn't running."""
        task = self._tasks.pop(key, None)
        if task is None:
            return
        task.cancel()
        self.sync()

    async def _loop(self, provider: Provider, ctx: ProviderContext) -> None:
        cfg = self._settings.providers
        interval = provider.interval_s(cfg)
        store = self._registry.get_or_create(
            provider.key, stale_after_s=interval * _STALE_INTERVAL_MULTIPLE
        )
        while True:
            delay = await self._poll_once(provider, ctx, store, interval)
            await self._sleep(delay)

    async def _poll_once(
        self, provider: Provider, ctx: ProviderContext, store: Store, interval: int
    ) -> float:
        cfg = self._settings.providers
        try:
            value = await provider.poll(ctx)
        except ProviderError as exc:
            logger.warning("poll failed provider=%s: %s", provider.key, exc)
            store.note_failure()
            self._registry.notify(provider.key)
            return cfg.retry_interval_s
        except Exception:
            logger.exception("poll crashed provider=%s", provider.key)
            store.note_failure()
            self._registry.notify(provider.key)
            return cfg.retry_interval_s

        if value is None:
            logger.debug("poll deferred provider=%s (dependency not ready)", provider.key)
            return min(interval, cfg.defer_interval_s)

        store.publish(value)
        self._registry.notify(provider.key)
        logger.info("poll ok provider=%s", provider.key)
        return interval + random.uniform(0, cfg.jitter_s)
