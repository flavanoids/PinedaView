# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures and a fake provider context."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager

from pinedaview.config import Settings, load_settings
from pinedaview.providers.base import ProviderContext, ProviderError
from pinedaview.runtime import Runtime, build_runtime
from pinedaview.secrets import SecretStore
from pinedaview.stores import StoreRegistry

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_host_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a dev box's real /etc/pineda-web/config.toml out of the tests."""
    monkeypatch.delenv("PINEDA_CONFIG_FILE", raising=False)
    monkeypatch.setattr("pinedaview.config._SYSTEM_CONFIG", Path("/nonexistent/config.toml"))


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings(
        overrides={
            "state_dir": tmp_path,
            "photos_dir": str(tmp_path / "photos"),
            "location": {"query": "Houston"},
            "api": {"db_path": str(tmp_path / "pineda.db")},
            "config_file": str(tmp_path / "config.toml"),
        }
    )


@pytest_asyncio.fixture
async def runtime(settings: Settings) -> Runtime:
    # No live providers — tests seed stores by hand.
    return build_runtime(settings, providers=[])


@pytest_asyncio.fixture
async def client(runtime: Runtime) -> AsyncIterator[httpx.AsyncClient]:
    from pinedaview.api import create_app

    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


class FakeContext(ProviderContext):
    """A ProviderContext whose HTTP is a queue of canned responses."""

    def __init__(
        self,
        settings: Settings,
        *,
        responses: list[Any] | None = None,
        stores: dict[str, Any] | None = None,
        card_settings: dict[str, dict[str, Any]] | None = None,
        secrets: SecretStore | None = None,
    ) -> None:
        super().__init__(settings, StoreRegistry(), card_settings=card_settings, secrets=secrets)
        self._responses = list(responses or [])
        self._stores = stores or {}
        self.requested_urls: list[str] = []

    def store_value(self, key: str) -> Any:
        return self._stores.get(key)

    async def fetch_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        allow_hosts: list[str] | None = None,
    ) -> Any:
        self.requested_urls.append(url)
        if not self._responses:
            raise ProviderError("fake context: no more canned responses")
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
