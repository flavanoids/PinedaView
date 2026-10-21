# SPDX-License-Identifier: Apache-2.0
"""News — the day's headlines from public-service and independent outlets
(NPR, BBC, PBS, Al Jazeera, The Guardian, …), sorted into the household's
*beats*: US, World, Good news, Houston, or whatever is set up in Settings.

A beat is a list of the outlet feeds it reads, keywords that pull a story in,
keywords that keep one out, and a weight. Each poll reads every feed any beat
uses, drops copies of the same story from different outlets, and gives each
beat its best few: keyword matches first, newest first, topped up with the
feeds' freshest when the keywords find too little. The card then takes the
beats in turn, weight by weight.

Every story carries its own picture — the feed's, or the article page's
``og:image`` when the feed has none. It is fetched once, shrunk and blurred
here (the Pi just shows a small finished JPEG), and kept in memory until the
story leaves the rotation. ``GET /api/news/{id}.jpg`` serves it.

Nothing is fetched in the quiet hours (10pm to 5am by default): a poll then only
re-sorts the stories already in hand, so a Settings change still shows up.
Early mornings can leave out the graphic headlines (death tolls, attacks).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from PIL import Image, ImageFilter, UnidentifiedImageError

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError
from pinedaview.providers.commute import _during_rush as in_window

CARD = "news"


@dataclass(frozen=True)
class Source:
    outlet: str
    url: str


# The outlets a beat can pick from. Ids are what Settings stores; the card's
# manifest lists the same ids with their labels (a test keeps them in step).
# Reuters and AP are absent on purpose: neither publishes an RSS feed whose
# links go straight to the article.
SOURCES: dict[str, Source] = {
    "npr-news": Source("NPR", "https://feeds.npr.org/1001/rss.xml"),
    "npr-politics": Source("NPR", "https://feeds.npr.org/1014/rss.xml"),
    "npr-world": Source("NPR", "https://feeds.npr.org/1004/rss.xml"),
    "npr-science": Source("NPR", "https://feeds.npr.org/1007/rss.xml"),
    "npr-health": Source("NPR", "https://feeds.npr.org/1128/rss.xml"),
    "bbc-us": Source("BBC", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
    "bbc-world": Source("BBC", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    "bbc-science": Source("BBC", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    "pbs-politics": Source("PBS", "https://www.pbs.org/newshour/feeds/rss/politics"),
    "pbs-nation": Source("PBS", "https://www.pbs.org/newshour/feeds/rss/nation"),
    "pbs-world": Source("PBS", "https://www.pbs.org/newshour/feeds/rss/world"),
    "pbs-science": Source("PBS", "https://www.pbs.org/newshour/feeds/rss/science"),
    "aljazeera": Source("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    "guardian-us": Source("The Guardian", "https://www.theguardian.com/us-news/rss"),
    "guardian-world": Source("The Guardian", "https://www.theguardian.com/world/rss"),
    "guardian-environment": Source("The Guardian", "https://www.theguardian.com/environment/rss"),
    "guardian-science": Source("The Guardian", "https://www.theguardian.com/science/rss"),
    "nasa": Source("NASA", "https://www.nasa.gov/news-release/feed/"),
    "sciencedaily": Source("ScienceDaily", "https://www.sciencedaily.com/rss/top/science.xml"),
    "mongabay": Source("Mongabay", "https://news.mongabay.com/feed/"),
    "reasons-to-be-cheerful": Source(
        "Reasons to be Cheerful", "https://reasonstobecheerful.world/feed/"
    ),
    "positive-news": Source("Positive News", "https://www.positive.news/feed/"),
    "houston-public-media": Source(
        "Houston Public Media", "https://www.houstonpublicmedia.org/topics/news/feed/"
    ),
    "houston-landing": Source("Houston Landing", "https://houstonlanding.org/feed/"),
    "khou": Source("KHOU", "https://www.khou.com/feeds/syndication/rss/news/local"),
}

_PER_BEAT = 5
_REFETCH_AFTER_S = 5 * 60
_PER_SOURCE = 2  # per beat, so one prolific feed can't fill it
_DEFAULT_MAX_AGE_H = 24
_DEFAULT_QUIET = "22:00-05:00"
_DEFAULT_SOFT = "05:00-08:00"
_FEED_CONCURRENCY = 6
_IMAGE_CONCURRENCY = 4
_IMAGE_MAX_BYTES = 12 * 1024 * 1024
_PAGE_MAX_BYTES = 1024 * 1024  # og:image sits in <head>; never read a whole page
_IMAGE_EDGE = 480
_BLUR_RADIUS = 6
_SIMILAR = 0.5  # word overlap at which two headlines are the same story

_NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}

# Share and campaign tags the outlets bolt onto feed links. Off they come: the
# QR is a straight link to the article, and a shorter URL is a code that
# scans from across the room.
_TRACKING = re.compile(
    r"^(utm_\w+|at_\w+|traffic_source|cmp|cmpid|cmp_id|ref|src|source|"
    r"fbclid|gclid|mc_cid|mc_eid|ocid|rss|partner|icid)$",
    re.IGNORECASE,
)

# What "soften mornings" leaves out: headlines built around death and attacks.
_GRAPHIC = re.compile(
    r"\b(kill(s|ed|ing|ings)?|dead|deaths?|death toll|die[sd]?|massacres?|"
    r"bomb(s|ed|ing|ings)?|shot|shootings?|gunm[ae]n|stabb\w*|airstrikes?|"
    r"beheaded|rap(e|ed|es|ist)|bodies|corpses?|slaughter\w*|casualt\w*|"
    r"wounded|executed|executions?|tortur\w*|genocide)\b",
    re.IGNORECASE,
)

_TAG = re.compile(r"<[^>]+>")
_IMG_SRC = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_OG_IMAGE = re.compile(
    r"<meta\b[^>]*?(?:property|name)\s*=\s*[\"'](?:og:image|twitter:image)[\"'][^>]*>",
    re.IGNORECASE,
)
# Outlets' fallback share images, by file name: NPR's facebook-default-wide,
# Al Jazeera's logo_aje_social, ScienceDaily's scidaily-icon.
_STAND_IN = re.compile(r"default|logo|placeholder|fallback|icon|avatar", re.IGNORECASE)
_CONTENT_ATTR = re.compile(r"\bcontent\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+")
_SMALL_WORDS = frozenset(
    "the a an and or of to in on for at by with from as is are was be after over "
    "into says say said new its it this that than amid about how why what who".split()
)


@dataclass
class Story:
    id: str
    title: str
    url: str
    outlet: str
    source: str
    published: datetime
    summary: str
    image_url: str | None

    @property
    def text(self) -> str:
        return f"{self.title} {self.summary}"


@dataclass
class _Picture:
    jpeg: bytes
    tint: str


class NewsCache:
    """What the news keeps between polls, outliving any one provider (a
    Settings change rebuilds it): the stories last read from each feed, and
    one blurred JPEG per story on screen — never more."""

    def __init__(self) -> None:
        self._pictures: dict[str, _Picture] = {}
        self.pool: dict[str, list[Story]] = {}
        self.fetched_at = 0.0
        # Stories whose picture was looked for and not found — not looked
        # for again while they stay on screen.
        self.pictureless: set[str] = set()

    def get(self, story_id: str) -> bytes | None:
        picture = self._pictures.get(story_id)
        return picture.jpeg if picture is not None else None

    def entry(self, story_id: str) -> _Picture | None:
        return self._pictures.get(story_id)

    def put(self, story_id: str, picture: _Picture) -> None:
        self._pictures[story_id] = picture

    def keep_only(self, ids: set[str]) -> None:
        for story_id in set(self._pictures) - ids:
            del self._pictures[story_id]
        self.pictureless &= ids


NEWS_CACHE = NewsCache()
_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def valid_id(story_id: str) -> bool:
    return bool(_ID_RE.match(story_id))


# ── feeds ───────────────────────────────────────────────────────────────────


def clean_url(url: str) -> str:
    """The article's own address: no tracking parameters, no fragment."""
    parts = urlsplit(url.strip())
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    query = [(k, v) for k, v in pairs if not _TRACKING.match(k)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _story_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def _plain(html: str | None) -> str:
    return " ".join(unescape(_TAG.sub(" ", html or "")).split())


def _when(item: ET.Element) -> datetime | None:
    for tag in ("pubDate", "dc:date", "atom:updated", "atom:published"):
        raw = item.findtext(tag, namespaces=_NS)
        if not raw:
            continue
        raw = raw.strip()
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            try:
                when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
        return when if when.tzinfo else when.replace(tzinfo=UTC)
    return None


def _width(node: ET.Element) -> int:
    try:
        return int(node.get("width") or 0)
    except ValueError:
        return 0


def _usable_image(url: str | None) -> bool:
    # NPR's feed opens every story with a 1x1 tracking pixel.
    if not url:
        return False
    return url.startswith(("http://", "https://")) and "pixel" not in url.lower()


def _feed_image(item: ET.Element, html: str) -> str | None:
    """The best picture the feed itself offers: the widest ``media:content``
    image up to ~1000px (the Guardian lists several sizes), a thumbnail, an
    image enclosure, or the first real ``<img>`` in the item's HTML."""
    media = [
        n
        for n in item.findall("media:content", _NS) + item.findall("media:group/media:content", _NS)
        if _usable_image(n.get("url"))
        and (n.get("medium") in (None, "image") or (n.get("type") or "").startswith("image/"))
    ]
    if media:
        fitting = [n for n in media if _width(n) <= 1000] or media
        return max(fitting, key=_width).get("url")
    thumbs = [n for n in item.findall("media:thumbnail", _NS) if _usable_image(n.get("url"))]
    if thumbs:
        url = max(thumbs, key=_width).get("url") or ""
        # BBC's thumbnails are 240px; the same image comes in 480.
        return url.replace("/standard/240/", "/standard/480/")
    for enclosure in item.findall("enclosure"):
        is_image = (enclosure.get("type") or "").startswith("image/")
        if is_image and _usable_image(enclosure.get("url")):
            return enclosure.get("url")
    for src in _IMG_SRC.findall(html):
        src = unescape(src)
        if _usable_image(src):
            return src
    return None


def parse_feed(xml: str | bytes, source_id: str, outlet: str) -> list[Story]:
    """Every dated item in an RSS (or Atom) feed that links to an article."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ProviderError(f"{source_id}: unreadable feed: {exc}") from exc
    channel_title = root.findtext("channel/title") or root.findtext("atom:title", namespaces=_NS)
    outlet = outlet or (channel_title or "").strip() or urlsplit(source_id).hostname or "News"
    items = root.findall("channel/item") or root.findall("atom:entry", _NS)
    stories: list[Story] = []
    for item in items:
        title = _plain(item.findtext("title") or item.findtext("atom:title", namespaces=_NS))
        link = (item.findtext("link") or "").strip()
        if not link:
            atom_link = item.find("atom:link", _NS)
            link = atom_link.get("href", "") if atom_link is not None else ""
        published = _when(item)
        if not title or not link.startswith(("http://", "https://")) or published is None:
            continue
        html = (
            item.findtext("content:encoded", namespaces=_NS)
            or item.findtext("description")
            or item.findtext("atom:summary", namespaces=_NS)
            or ""
        )
        url = clean_url(link)
        image = _feed_image(item, html)
        stories.append(
            Story(
                id=_story_id(url),
                title=title,
                url=url,
                outlet=outlet,
                source=source_id,
                published=published,
                summary=_plain(item.findtext("description") or html)[:400],
                image_url=urljoin(url, unescape(image)) if image else None,
            )
        )
    return stories


# ── beats ───────────────────────────────────────────────────────────────────


@dataclass
class Beat:
    name: str
    sources: list[str]
    keywords: list[re.Pattern[str]]
    exclude: list[re.Pattern[str]]
    weight: int
    max_age_h: float


def keyword_pattern(word: str) -> re.Pattern[str] | None:
    """One Settings keyword as a whole-word pattern. ``immigra*`` is a prefix;
    a plain word also takes its plural. Written in capitals (ICE, AI, AOC) it
    only matches capitals — so ICE the agency, not an ice storm."""
    word = word.strip()
    if not word:
        return None
    prefix = word.endswith("*")
    stem = word.rstrip("*").strip()
    if not stem:
        return None
    letters = [c for c in stem if c.isalpha()]
    exact_case = len(letters) >= 2 and all(c.isupper() for c in letters)
    body = r"\s+".join(re.escape(part) for part in stem.split())
    tail = r"\w*" if prefix else r"(?:s|es)?"
    flags = 0 if exact_case else re.IGNORECASE
    return re.compile(rf"(?<!\w){body}{tail}(?!\w)", flags)


def _words(value: object) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,\n]", value)
    if isinstance(value, list):
        return [w for w in (str(v).strip() for v in value) if w]
    return []


def parse_beats(value: object) -> list[Beat]:
    """The beats from Settings, skipping any switched off or malformed."""
    beats: list[Beat] = []
    if not isinstance(value, list):
        return beats
    for raw in value:
        if not isinstance(raw, dict) or raw.get("enabled") is False:
            continue
        sources = [
            s for s in _words(raw.get("sources")) if s in SOURCES or s.startswith("https://")
        ]
        name = str(raw.get("name") or "").strip()
        if not name or not sources:
            continue
        try:
            weight = max(1, min(5, int(raw.get("weight") or 1)))
        except (TypeError, ValueError):
            weight = 1
        try:
            max_age = float(raw.get("maxAgeHours") or _DEFAULT_MAX_AGE_H)
        except (TypeError, ValueError):
            max_age = _DEFAULT_MAX_AGE_H
        beats.append(
            Beat(
                name=name,
                sources=sources,
                keywords=[p for w in _words(raw.get("keywords")) if (p := keyword_pattern(w))],
                exclude=[p for w in _words(raw.get("exclude")) if (p := keyword_pattern(w))],
                weight=weight,
                max_age_h=max(1.0, max_age),
            )
        )
    return beats


def _signature(title: str) -> set[str]:
    return {w for w in _WORD.findall(title.lower()) if w not in _SMALL_WORDS and len(w) > 2}


def _same_story(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= _SIMILAR


def _hits(story: Story, patterns: list[re.Pattern[str]]) -> int:
    return sum(1 for p in patterns if p.search(story.text))


def _candidates(
    pool: dict[str, list[Story]], beat: Beat, now: datetime, soften: bool
) -> list[Story]:
    """The beat's stories in the order it wants them: keyword matches first,
    newest first, then the feeds' freshest to fill in when matches are thin."""
    cutoff = now - timedelta(hours=beat.max_age_h)
    fresh = [
        s
        for source in beat.sources
        for s in pool.get(source, [])
        if cutoff <= s.published <= now + timedelta(minutes=10)
        and not _hits(s, beat.exclude)
        and not (soften and _GRAPHIC.search(s.title))
    ]
    newest = sorted(fresh, key=lambda s: s.published, reverse=True)
    if not beat.keywords:
        return newest
    matched = [s for s in newest if _hits(s, beat.keywords)]
    return matched + [s for s in newest if s not in matched]


def _pick(candidates: list[Story], taken: list[set[str]]) -> list[Story]:
    """Up to a handful, no outlet hogging them, and nothing already on
    screen under another outlet's headline. Adds the picks to ``taken``."""
    picks: list[Story] = []
    per_source: dict[str, int] = {}
    for story in candidates:
        if len(picks) >= _PER_BEAT:
            break
        if per_source.get(story.source, 0) >= _PER_SOURCE:
            continue
        signature = _signature(story.title)
        if any(_same_story(signature, seen) for seen in taken):
            continue
        taken.append(signature)
        per_source[story.source] = per_source.get(story.source, 0) + 1
        picks.append(story)
    return picks


def select(
    pool: dict[str, list[Story]],
    beats: list[Beat],
    now: datetime,
    *,
    soften: bool = False,
) -> list[tuple[Beat, Story]]:
    """Each beat's best few, then the beats in turn by weight. A story
    belongs to the first beat that takes it, and only one outlet's copy of
    any story makes the screen."""
    taken: list[set[str]] = []
    queues = [(beat, _pick(_candidates(pool, beat, now, soften), taken)) for beat in beats]
    order: list[tuple[Beat, Story]] = []
    while any(queue for _, queue in queues):
        for beat, queue in queues:
            for _ in range(beat.weight):
                if queue:
                    order.append((beat, queue.pop(0)))
    return order


# ── pictures ────────────────────────────────────────────────────────────────


def blur_picture(data: bytes) -> _Picture:
    """A small, softly blurred JPEG of the story's picture and its average
    colour, for the card's tinted panel. Raises on anything not an image."""
    with Image.open(io.BytesIO(data)) as source:
        # A JPEG can decode straight at a fraction of its size — NPR's
        # originals are 5000px wide.
        source.draft("RGB", (_IMAGE_EDGE * 2, _IMAGE_EDGE * 2))
        image = source.convert("RGB")
    image.thumbnail((_IMAGE_EDGE, _IMAGE_EDGE))
    r, g, b = image.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))  # type: ignore[misc]
    blurred = image.filter(ImageFilter.GaussianBlur(_BLUR_RADIUS))
    out = io.BytesIO()
    blurred.save(out, "JPEG", quality=72, optimize=True, progressive=True)
    return _Picture(out.getvalue(), f"#{r:02x}{g:02x}{b:02x}")


def og_image(html: str, base: str) -> str | None:
    """The article page's share image — unless it's the outlet's stand-in
    (a logo or default card), which isn't the story's picture at all."""
    for tag in _OG_IMAGE.findall(html):
        found = _CONTENT_ATTR.search(tag)
        if not found:
            continue
        url = urljoin(base, unescape(found.group(1)))
        if _usable_image(url) and not _STAND_IN.search(urlsplit(url).path.rsplit("/", 1)[-1]):
            return url
    return None


async def _get_capped(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    *,
    kind: str,
    cap: int,
    truncate: bool = False,
) -> bytes | None:
    """The body of a GET whose content type starts with ``kind``, read no
    further than ``cap`` bytes: cut there (``truncate``) or given up on."""
    if urlsplit(url).scheme not in ("http", "https"):
        return None
    try:
        async with client.stream("GET", url, headers=headers, follow_redirects=True) as response:
            content_type = response.headers.get("content-type", "")
            if response.status_code != 200 or not content_type.startswith(kind):
                return None
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > cap:
                    return bytes(body[:cap]) if truncate else None
            return bytes(body)
    except httpx.HTTPError:
        return None


# ── provider ────────────────────────────────────────────────────────────────


class NewsProvider(Provider):
    key = "news"

    def __init__(
        self,
        interval_s: int | None = None,
        cache: NewsCache | None = None,
        clock: Any = None,
    ) -> None:
        super().__init__(interval_s)
        self.cache = cache or NEWS_CACHE
        self._clock = clock or (lambda: datetime.now().astimezone())

    def _default_interval_s(self, cfg: ProviderConfig) -> int:  # noqa: ARG002
        return 1800

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        now = self._clock()
        beats = parse_beats(ctx.card_setting(CARD, "beats"))
        quiet = ctx.card_setting(CARD, "quietHours") or _DEFAULT_QUIET
        resting = in_window(quiet, now)
        wanted = {s for beat in beats for s in beat.sources}
        # Overnight, only re-sort what's in hand — unless nothing is (a
        # restart at midnight still gets a screen of news). A Settings change
        # re-sorts too, and only reads feeds again if it adds one or the last
        # read is a few minutes old.
        have_all = wanted <= set(self.cache.pool)
        recent = time.time() - self.cache.fetched_at < _REFETCH_AFTER_S
        if (not resting and not (recent and have_all)) or not self.cache.pool:
            await self._fetch_feeds(ctx, wanted)
        soften = ctx.card_setting(CARD, "softenMornings")
        soft_window = ctx.card_setting(CARD, "softenWindow") or _DEFAULT_SOFT
        picked = select(
            self.cache.pool,
            beats,
            now,
            soften=soften is not False and in_window(soft_window, now),
        )
        if not resting:
            await self._fetch_pictures(ctx, [story for _, story in picked])
        self.cache.keep_only({story.id for _, story in picked})

        stories: list[dict[str, Any]] = []
        for beat, story in picked:
            picture = self.cache.entry(story.id)
            stories.append(
                {
                    "id": story.id,
                    "title": story.title,
                    "url": story.url,
                    "outlet": story.outlet,
                    "beat": beat.name,
                    "published": story.published.isoformat(),
                    "image": f"/api/news/{story.id}.jpg" if picture else None,
                    "tint": picture.tint if picture else None,
                }
            )
        return {"stories": stories}

    async def _fetch_feeds(self, ctx: ProviderContext, wanted: set[str]) -> None:
        client = ctx.http_client
        if client is None:
            raise ProviderError("news needs the shared HTTP client")
        headers = {"User-Agent": ctx.settings.providers.user_agent}
        gate = asyncio.Semaphore(_FEED_CONCURRENCY)

        async def one(source_id: str) -> tuple[str, list[Story] | None]:
            known = SOURCES.get(source_id)
            url, outlet = (known.url, known.outlet) if known else (source_id, "")
            async with gate:
                try:
                    response = await client.get(url, headers=headers, follow_redirects=True)
                    response.raise_for_status()
                    return source_id, parse_feed(response.content, source_id, outlet)
                except (httpx.HTTPError, ProviderError):
                    return source_id, None

        results = await asyncio.gather(*(one(s) for s in sorted(wanted)))
        fresh = {source: stories for source, stories in results if stories is not None}
        if wanted and not fresh:
            raise ProviderError("no news feed could be read")
        # A feed that failed this time keeps its last stories; one no beat
        # uses any more is let go.
        pool = self.cache.pool
        self.cache.pool = {s: fresh.get(s, pool.get(s, [])) for s in wanted}
        self.cache.fetched_at = time.time()

    async def _fetch_pictures(self, ctx: ProviderContext, stories: list[Story]) -> None:
        client = ctx.http_client
        if client is None:
            return
        headers = {"User-Agent": ctx.settings.providers.user_agent}
        gate = asyncio.Semaphore(_IMAGE_CONCURRENCY)

        async def one(story: Story) -> None:
            async with gate:
                picture = await _picture(client, story, headers)
            if picture is None:
                self.cache.pictureless.add(story.id)
            else:
                self.cache.put(story.id, picture)

        await asyncio.gather(
            *(
                one(s)
                for s in stories
                if self.cache.entry(s.id) is None and s.id not in self.cache.pictureless
            )
        )


async def _picture(
    client: httpx.AsyncClient, story: Story, headers: dict[str, str]
) -> _Picture | None:
    image_url = story.image_url
    if image_url is None:
        page = await _get_capped(
            client, story.url, headers, kind="text/html", cap=_PAGE_MAX_BYTES, truncate=True
        )
        image_url = og_image(page.decode("utf-8", "replace"), story.url) if page else None
    if not image_url:
        return None
    data = await _get_capped(client, image_url, headers, kind="image/", cap=_IMAGE_MAX_BYTES)
    if data is None:
        return None
    try:
        return await asyncio.to_thread(blur_picture, data)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        return None
