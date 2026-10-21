# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pinedaview.config import Settings
from pinedaview.providers.base import ProviderContext, ProviderError
from pinedaview.stores import StoreRegistry


class _Handler(BaseHTTPRequestHandler):
    body = b'{"ok": true}'

    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *_args: object) -> None:
        pass


@pytest.fixture
def base_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


def _ctx() -> ProviderContext:
    return ProviderContext(Settings(), StoreRegistry())


async def test_fetch_json_reads_a_real_response(base_url: str) -> None:
    assert await _ctx().fetch_json(base_url) == {"ok": True}


async def test_fetch_json_rejects_non_http() -> None:
    with pytest.raises(ProviderError, match="non-http"):
        await _ctx().fetch_json("file:///etc/hostname")


async def test_fetch_json_wraps_connection_errors() -> None:
    with pytest.raises(ProviderError, match="fetch failed"):
        await _ctx().fetch_json("http://127.0.0.1:9/")


async def test_fetch_json_rejects_bad_json(base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_Handler, "body", b"not json")
    with pytest.raises(ProviderError, match="bad JSON"):
        await _ctx().fetch_json(base_url)


def test_store_value_reads_registry() -> None:
    ctx = _ctx()
    ctx.registry.get_or_create("weather", stale_after_s=60).publish({"tempC": 9})
    assert ctx.store_value("weather") == {"tempC": 9}
    assert ctx.store_value("absent") is None
