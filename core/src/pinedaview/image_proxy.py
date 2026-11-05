# SPDX-License-Identifier: Apache-2.0
"""Image search pictures, fetched and shrunk here for the kiosk.

The collage's pictures come from all over the web. Loaded straight from
there, many never arrive: social and news CDNs refuse a request from
another site (a broken-image icon on the tile), and the ones that do come
can be 12 MP originals the kiosk Pi would have to decode six at a time.
So the screen asks this server for them by letter, and the server fetches
each once, scales it to what a tile shows, and keeps it in memory while
the card is up.

Only pictures on the card that's up can be asked for, and only public
addresses are fetched (no LAN, loopback or link-local, re-checked on every
redirect), so the endpoint isn't a way to reach the rest of the network.
"""

from __future__ import annotations

import asyncio
import io
import ipaddress
import logging
import socket
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Literal
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from pinedaview.takeover import PictureCard

if TYPE_CHECKING:
    from pinedaview.takeover import ImageItem, Takeover, TakeoverService

logger = logging.getLogger(__name__)

Size = Literal["thumb", "full"]

MAX_SIDE: dict[Size, int] = {"thumb": 480, "full": 1600}
"""Longest side out. A hero tile on the 2048x1280 kiosk is ~1000 px wide;
the spotlight is ~1500."""

MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 60_000_000
"""Refused before decoding: a 60 MP RGB image is ~180 MB in memory."""

CACHE_BYTES = 64 * 1024 * 1024
FETCH_TIMEOUT = 6.0
FAILED_FOR = 600.0
"""How long a picture that couldn't be had is not asked for again: the
screen's request shouldn't wait out the same timeout the warm-up did."""
MAX_REDIRECTS = 3
_CONCURRENT = 4

# A plain browser request: some CDNs refuse an obvious bot.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


class ImageFetchError(Exception):
    """The picture couldn't be fetched or isn't a usable image."""


async def _public(host: str) -> bool:
    """Every address `host` resolves to is on the public internet."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    addrs = {str(info[4][0]).split("%")[0] for info in infos}
    return bool(addrs) and all(ipaddress.ip_address(a).is_global for a in addrs)


def _shrink(data: bytes, size: Size) -> tuple[bytes, str]:
    """Bytes -> WebP no larger than MAX_SIDE[size] (alpha kept)."""
    side = MAX_SIDE[size]
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.width * img.height > MAX_PIXELS:
                raise ImageFetchError(f"{img.width}x{img.height} is too large to decode")
            # JPEG decodes at a reduced scale directly: far less memory and time.
            img.draft("RGB", (side, side))
            img.seek(0)  # a GIF's first frame
            out = ImageOps.exif_transpose(img)
            out.thumbnail((side, side), Image.Resampling.LANCZOS)
            if out.mode not in ("RGB", "RGBA"):
                alpha = "A" in out.getbands() or "transparency" in out.info
                out = out.convert("RGBA" if alpha else "RGB")
            buf = io.BytesIO()
            out.save(buf, "WEBP", quality=82, method=4)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
        raise ImageFetchError(f"not a usable image: {e}") from e
    return buf.getvalue(), "image/webp"


def sources(item: ImageItem, size: Size) -> list[str]:
    """Where to get `item` at `size`, best first. The full picture falls
    back to the search engine's thumbnail, which is usually served from the
    engine's own CDN and so arrives when the original site refuses."""
    thumb = item.thumb_url or item.url
    order = [thumb] if size == "thumb" else [item.url, thumb]
    return list(dict.fromkeys(u for u in order if u))


class ImageProxy:
    def __init__(
        self, takeover: TakeoverService | None = None, cache_bytes: int = CACHE_BYTES
    ) -> None:
        self._cache: OrderedDict[tuple[str, Size], tuple[bytes, str]] = OrderedDict()
        self._cache_bytes = cache_bytes
        self._held = 0
        self._inflight: dict[tuple[str, Size], asyncio.Future[tuple[bytes, str]]] = {}
        self._gate = asyncio.Semaphore(_CONCURRENT)
        self._failed: dict[tuple[str, Size], tuple[float, str]] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        if takeover is not None:
            takeover.on_change(self._follow)

    def _follow(self, up: Takeover | None) -> None:
        """A collage (or recipe choices) going up: start fetching its
        pictures, thumbnails first, so they're here by the time the screen asks."""
        if up is None or not isinstance(up.card, PictureCard):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        images = list(up.card.images)

        async def warm() -> None:
            await self.warm([sources(i, "thumb")[0] for i in images], "thumb")
            await self.warm([sources(i, "full")[0] for i in images], "full")

        task = loop.create_task(warm(), name="image-search-warm")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def picture(self, item: ImageItem, size: Size) -> tuple[bytes, str]:
        """`item` at `size`, from the first of its sources that works."""
        errors = []
        for url in sources(item, size):
            try:
                return await self.get(url, size)
            except ImageFetchError as e:
                errors.append(str(e))
        raise ImageFetchError("; ".join(errors) or "no source")

    async def get(self, url: str, size: Size) -> tuple[bytes, str]:
        """The picture at `url`, shrunk to `size`: (bytes, content type).
        Concurrent asks for the same picture share one fetch."""
        key = (url, size)
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        failed = self._failed.get(key)
        if failed is not None and time.monotonic() - failed[0] < FAILED_FOR:
            raise ImageFetchError(failed[1])
        pending = self._inflight.get(key)
        if pending is not None:
            return await asyncio.shield(pending)
        future: asyncio.Future[tuple[bytes, str]] = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            async with self._gate:
                raw = await self._fetch(url)
                result = await asyncio.to_thread(_shrink, raw, size)
        except asyncio.CancelledError:
            future.cancel()
            raise
        except Exception as e:
            if isinstance(e, ImageFetchError):
                now = time.monotonic()
                self._failed = {k: v for k, v in self._failed.items() if now - v[0] < FAILED_FOR}
                self._failed[key] = (now, str(e))
            future.set_exception(e)
            future.exception()  # retrieved: nobody else may be waiting
            raise
        finally:
            self._inflight.pop(key, None)
        future.set_result(result)
        self._remember(key, result)
        return result

    async def warm(self, urls: list[str], size: Size) -> None:
        """Fetch `urls` ahead of the screen asking; failures are only logged."""
        results = await asyncio.gather(*(self.get(u, size) for u in urls), return_exceptions=True)
        failed = sum(isinstance(r, BaseException) for r in results)
        if failed:
            logger.info("image search: %d of %d %s pictures unavailable", failed, len(urls), size)

    def _remember(self, key: tuple[str, Size], value: tuple[bytes, str]) -> None:
        self._cache[key] = value
        self._held += len(value[0])
        while self._held > self._cache_bytes and len(self._cache) > 1:
            _, (old, _) = self._cache.popitem(last=False)
            self._held -= len(old)

    async def _fetch(self, url: str) -> bytes:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=FETCH_TIMEOUT, follow_redirects=False
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                parts = urlsplit(url)
                if parts.scheme not in ("http", "https") or not parts.hostname:
                    raise ImageFetchError(f"not a web address: {url[:80]}")
                if not await _public(parts.hostname):
                    raise ImageFetchError(f"not a public host: {parts.hostname}")
                try:
                    async with client.stream("GET", url) as resp:
                        if resp.is_redirect and "location" in resp.headers:
                            url = urljoin(url, resp.headers["location"])
                            continue
                        if resp.status_code != 200:
                            raise ImageFetchError(f"HTTP {resp.status_code} from {parts.hostname}")
                        kind = resp.headers.get("content-type", "")
                        if kind and not kind.startswith(("image/", "application/octet-stream")):
                            raise ImageFetchError(f"{kind} from {parts.hostname}, not an image")
                        body = bytearray()
                        async for chunk in resp.aiter_bytes():
                            body += chunk
                            if len(body) > MAX_BYTES:
                                raise ImageFetchError(f"over {MAX_BYTES} bytes")
                        return bytes(body)
                except httpx.HTTPError as e:
                    raise ImageFetchError(f"{type(e).__name__} from {parts.hostname}") from e
        raise ImageFetchError("too many redirects")
