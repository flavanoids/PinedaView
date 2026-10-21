# SPDX-License-Identifier: Apache-2.0
"""Provider contract and the context handed to each poll."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx

from pinedaview.config import ProviderConfig, Settings
from pinedaview.secrets import SecretStore
from pinedaview.stores import StoreRegistry


class ProviderError(RuntimeError):
    """A poll failed in a way worth logging but not crashing over."""


class ProviderContext:
    """What a provider may reach for: config, the other stores, cached HTTP,
    secrets, and its card's own settings.

    A thin stand-in for the richer card ``ctx`` — same idea, fewer capabilities.
    """

    def __init__(
        self,
        settings: Settings,
        registry: StoreRegistry,
        *,
        secrets: SecretStore | None = None,
        card_settings: dict[str, dict[str, Any]] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self._secrets = secrets
        self._card_settings = card_settings or {}
        self._client = client

    @property
    def location(self) -> Any:
        return self.settings.location

    @property
    def http_client(self) -> httpx.AsyncClient | None:
        return self._client

    def store_value(self, key: str) -> Any:
        store = self.registry.get(key)
        entry = store.snapshot() if store is not None else None
        return entry.value if entry is not None else None

    def secret(self, name: str) -> str | None:
        return self._secrets.get(name) if self._secrets is not None else None

    def set_secret(self, name: str, value: str) -> None:
        """Write back a refreshed credential (e.g. a rotated OAuth token)."""
        if self._secrets is not None:
            self._secrets.set(name, value)

    def card_setting(self, card_id: str, key: str) -> Any:
        return self._card_settings.get(card_id, {}).get(key)

    async def fetch_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        allow_hosts: list[str] | None = None,
    ) -> Any:
        host = urllib.parse.urlparse(url).hostname or ""
        if allow_hosts is not None and host not in allow_hosts:
            raise ProviderError(f"host {host!r} not in the card's fetchHosts allow-list")
        merged = {"User-Agent": self.settings.providers.user_agent, **(headers or {})}
        try:
            if self._client is not None:
                response = await self._client.get(url, headers=merged)
                response.raise_for_status()
                return response.json()
            return _blocking_fetch_json(url, merged, self.settings.providers.http_timeout_s)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderError(f"fetch failed: {exc}") from exc


def _blocking_fetch_json(url: str, headers: dict[str, str], timeout: float) -> Any:
    request = urllib.request.Request(url, headers=headers)
    if request.type not in ("http", "https"):
        raise ProviderError(f"refusing non-http url: {url}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"fetch failed: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"bad JSON from {url}: {exc}") from exc


class Provider(ABC):
    """One data source. Publishes to the store named :attr:`key`."""

    key: ClassVar[str]

    def __init__(self, interval_s: int | None = None) -> None:
        self._interval_override = interval_s

    @abstractmethod
    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        """Return the new value, or ``None`` to leave the store unchanged and
        retry sooner (a dependency isn't ready yet)."""

    def interval_s(self, cfg: ProviderConfig) -> int:
        return self._interval_override or self._default_interval_s(cfg)

    @abstractmethod
    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        """Fallback cadence when the manifest gives no ``refresh.interval``."""
