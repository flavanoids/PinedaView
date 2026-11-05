# SPDX-License-Identifier: Apache-2.0
"""Image search pictures fetched and shrunk by the server (image_proxy)."""

from __future__ import annotations

import asyncio
import io
from collections.abc import Callable

import httpx
import pytest
from PIL import Image

from pinedaview import image_proxy
from pinedaview.image_proxy import ImageFetchError, ImageProxy, _shrink
from pinedaview.runtime import Runtime


def _jpeg(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()


def _png_alpha(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), (0, 0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], list[str]]:
    """Route the proxy's fetches to a handler; *.example hosts count as public."""

    async def public(host: str) -> bool:
        return host.endswith(".example")

    monkeypatch.setattr(image_proxy, "_public", public)
    real = httpx.AsyncClient

    def install(handler: Handler) -> list[str]:
        asked: list[str] = []

        def record(request: httpx.Request) -> httpx.Response:
            asked.append(str(request.url))
            return handler(request)

        monkeypatch.setattr(
            httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(record), **kw)
        )
        return asked

    return install


def _image(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_jpeg(3000, 2000), headers={"content-type": "image/jpeg"})


def test_shrink_scales_to_the_size_and_keeps_alpha() -> None:
    data, kind = _shrink(_jpeg(3000, 2000), "full")
    assert kind == "image/webp"
    with Image.open(io.BytesIO(data)) as img:
        assert img.size == (1600, 1067)
    data, _ = _shrink(_jpeg(3000, 2000), "thumb")
    with Image.open(io.BytesIO(data)) as img:
        assert max(img.size) == 480
    data, _ = _shrink(_png_alpha(800, 600), "full")
    with Image.open(io.BytesIO(data)) as img:
        assert img.mode == "RGBA" and img.size == (800, 600)  # never scaled up


def test_shrink_refuses_garbage_and_huge_images(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ImageFetchError):
        _shrink(b"<html>not an image</html>", "full")
    monkeypatch.setattr(image_proxy, "MAX_PIXELS", 1000)
    with pytest.raises(ImageFetchError, match="too large"):
        _shrink(_jpeg(100, 100), "full")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/a.jpg",
        "http://localhost/a.jpg",
        "http://172.16.1.10/a.jpg",
        "http://10.77.0.2:8123/api/states",
        "http://[::1]/a.jpg",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "ftp://pics.example/a.jpg",
    ],
)
async def test_fetch_refuses_the_lan_and_non_web_addresses(url: str) -> None:
    with pytest.raises(ImageFetchError):
        await ImageProxy().get(url, "thumb")


async def test_redirects_are_checked_at_every_hop(web: Callable[[Handler], list[str]]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "pics.example":
            return httpx.Response(302, headers={"location": "http://10.0.0.5/secret.jpg"})
        return _image(request)

    asked = web(handler)
    with pytest.raises(ImageFetchError, match="not a public host"):
        await ImageProxy().get("https://pics.example/a.jpg", "thumb")
    assert asked == ["https://pics.example/a.jpg"]  # the LAN address is never asked


async def test_fetch_refuses_non_images_and_oversized_bodies(
    web: Callable[[Handler], list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    web(lambda _r: httpx.Response(200, text="<html/>", headers={"content-type": "text/html"}))
    with pytest.raises(ImageFetchError, match="not an image"):
        await ImageProxy().get("https://pics.example/a.jpg", "thumb")
    web(_image)
    monkeypatch.setattr(image_proxy, "MAX_BYTES", 100)
    with pytest.raises(ImageFetchError, match="over 100 bytes"):
        await ImageProxy().get("https://pics.example/b.jpg", "thumb")


async def test_one_fetch_per_picture_and_size(web: Callable[[Handler], list[str]]) -> None:
    asked = web(_image)
    proxy = ImageProxy()
    first, second = await asyncio.gather(
        proxy.get("https://pics.example/a.jpg", "thumb"),
        proxy.get("https://pics.example/a.jpg", "thumb"),
    )
    assert first == second
    await proxy.get("https://pics.example/a.jpg", "thumb")
    assert len(asked) == 1
    await proxy.get("https://pics.example/a.jpg", "full")
    assert len(asked) == 2


async def test_a_failure_is_remembered(web: Callable[[Handler], list[str]]) -> None:
    asked = web(lambda _r: httpx.Response(403))
    proxy = ImageProxy()
    for _ in range(3):
        with pytest.raises(ImageFetchError, match="HTTP 403"):
            await proxy.get("https://pics.example/a.jpg", "full")
    assert len(asked) == 1


async def test_cache_is_bounded(web: Callable[[Handler], list[str]]) -> None:
    asked = web(_image)
    proxy = ImageProxy(cache_bytes=1)
    await proxy.get("https://pics.example/a.jpg", "thumb")
    await proxy.get("https://pics.example/b.jpg", "thumb")
    await proxy.get("https://pics.example/a.jpg", "thumb")  # evicted, fetched again
    assert len(asked) == 3


_CARD = {
    "kind": "image_search",
    "query": "the high line",
    "images": [
        {
            "id": "A",
            "url": "https://pics.example/a.jpg",
            "thumb_url": "https://thumbs.example/a.jpg",
        },
        {
            "id": "B",
            "url": "https://blocked.example/b.jpg",
            "thumb_url": "https://thumbs.example/b.jpg",
        },
        {"id": "C", "url": "https://blocked.example/c.jpg"},
    ],
}


def _picky(request: httpx.Request) -> httpx.Response:
    if request.url.host == "blocked.example":
        return httpx.Response(403)
    return _image(request)


async def test_route_serves_only_pictures_on_the_card(
    client: httpx.AsyncClient, web: Callable[[Handler], list[str]]
) -> None:
    web(_picky)
    assert (await client.get("/api/takeover/images/A")).status_code == 404  # nothing up
    await client.put("/api/takeover", json={"card": _CARD})
    full = await client.get("/api/takeover/images/a")
    assert full.status_code == 200
    assert full.headers["content-type"] == "image/webp"
    assert "max-age" in full.headers["cache-control"]
    thumb = await client.get("/api/takeover/images/A", params={"size": "thumb"})
    with Image.open(io.BytesIO(thumb.content)) as img:
        assert max(img.size) == 480
    assert (await client.get("/api/takeover/images/Z")).status_code == 404
    assert (await client.get("/api/takeover/images/A", params={"size": "huge"})).status_code == 422
    await client.delete("/api/takeover")
    assert (await client.get("/api/takeover/images/A")).status_code == 404


async def test_route_falls_back_to_the_thumbnail_then_gives_up(
    client: httpx.AsyncClient, web: Callable[[Handler], list[str]]
) -> None:
    asked = web(_picky)
    await client.put("/api/takeover", json={"card": _CARD})
    b = await client.get("/api/takeover/images/B")
    assert b.status_code == 200  # the original refused; the engine's thumbnail came
    assert "https://thumbs.example/b.jpg" in asked
    # 404, never 502: a 502 sends the kiosk's nginx to the standby.
    assert (await client.get("/api/takeover/images/C")).status_code == 404
    await client.delete("/api/takeover")


async def test_route_serves_recipe_choices_pictures(
    client: httpx.AsyncClient, web: Callable[[Handler], list[str]]
) -> None:
    web(_picky)
    card = {
        "kind": "recipe_choices",
        "dish": "apple pie",
        "images": [{"id": "A1", "url": "https://pics.example/a1.jpg"}],
        "choices": [{"id": "A", "title": "Apple Pie", "images": ["A1"]}],
    }
    await client.put("/api/takeover", json={"card": card})
    assert (await client.get("/api/takeover/images/a1")).status_code == 200
    assert (
        await client.get("/api/takeover/images/A")
    ).status_code == 404  # a choice, not a picture
    await client.delete("/api/takeover")


async def test_a_collage_going_up_is_fetched_ahead(
    client: httpx.AsyncClient, runtime: Runtime, web: Callable[[Handler], list[str]]
) -> None:
    asked = web(_picky)
    await client.put("/api/takeover", json={"card": _CARD})
    for _ in range(50):
        if not runtime.images._tasks:
            break
        await asyncio.sleep(0.02)
    assert {"https://thumbs.example/a.jpg", "https://pics.example/a.jpg"} <= set(asked)
    before = len(asked)
    assert (await client.get("/api/takeover/images/A")).status_code == 200
    assert len(asked) == before  # already here
    await client.delete("/api/takeover")
