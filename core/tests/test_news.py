# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import io
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from pinedaview.config import Settings
from pinedaview.providers.base import ProviderContext
from pinedaview.providers.news import (
    SOURCES,
    NewsCache,
    NewsProvider,
    Story,
    clean_url,
    keyword_pattern,
    og_image,
    parse_beats,
    parse_feed,
    select,
)
from pinedaview.stores import StoreRegistry

NOW = datetime(2026, 10, 10, 14, 0).astimezone()
MANIFEST = Path(__file__).parents[1] / "src/pinedaview/cards/builtin/news/card.json"
NEVER = "03:00-03:01"


def _rss(*items: str, title: str = "Feed") -> str:
    return (
        '<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"'
        ' xmlns:content="http://purl.org/rss/1.0/modules/content/">'
        f"<channel><title>{title}</title><link>https://example.org/</link>"
        + "".join(items)
        + "</channel></rss>"
    )


def _item(title: str, link: str, hours_ago: float = 1, extra: str = "") -> str:
    when = format_datetime(NOW - timedelta(hours=hours_ago))
    return f"<item><title>{title}</title><link>{link}</link><pubDate>{when}</pubDate>{extra}</item>"


def _story(title: str, source: str = "npr-politics", hours_ago: float = 1, **kw: Any) -> Story:
    url = kw.pop("url", f"https://example.org/{abs(hash((title, source)))}")
    return Story(
        id=kw.pop("id", str(abs(hash(url)))[:12]),
        title=title,
        url=url,
        outlet=kw.pop("outlet", "NPR"),
        source=source,
        published=NOW - timedelta(hours=hours_ago),
        summary=kw.pop("summary", ""),
        image_url=kw.pop("image_url", None),
    )


def _beats(*beats: dict[str, Any]) -> list[Any]:
    return parse_beats(list(beats))


def _jpeg(color: tuple[int, int, int] = (200, 40, 40), size: int = 900) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (size, size // 2), color).save(out, "JPEG")
    return out.getvalue()


# ── feeds ───────────────────────────────────────────────────────────────────


def test_a_feed_link_loses_its_tracking_tags_but_keeps_its_real_query() -> None:
    assert (
        clean_url("https://www.bbc.co.uk/news/articles/x?at_medium=RSS&at_campaign=rss#top")
        == "https://www.bbc.co.uk/news/articles/x"
    )
    assert (
        clean_url("https://a.org/story?id=7&utm_source=rss&traffic_source=rss")
        == "https://a.org/story?id=7"
    )


def test_parse_feed_takes_each_dated_item_and_its_best_picture() -> None:
    guardian = (
        '<media:content width="140" url="https://i.guim.co.uk/a.jpg?width=140"/>'
        '<media:content width="460" url="https://i.guim.co.uk/a.jpg?width=460"/>'
    )
    bbc = '<media:thumbnail width="240" url="https://ichef.bbci.co.uk/ace/standard/240/b.jpg"/>'
    # NPR: a tracking pixel first, then the story's own photo.
    npr = (
        "<content:encoded><![CDATA[<img src='https://media.npr.org/x/npr-rss-pixel.png'/>"
        "<p>Hi</p><img src='https://npr.brightspotcdn.com/c.jpg'/>]]></content:encoded>"
    )
    xml = _rss(
        _item("One", "https://g.com/1?CMP=share", extra=guardian),
        _item("Two", "https://bbc.co.uk/2", extra=bbc),
        _item("Three", "https://npr.org/3", extra=npr),
        _item("Four", "https://aljazeera.com/4"),
        "<item><title>Undated</title><link>https://x.org/5</link></item>",
    )
    stories = parse_feed(xml, "npr-news", "NPR")
    assert [s.title for s in stories] == ["One", "Two", "Three", "Four"]
    assert stories[0].url == "https://g.com/1"
    assert stories[0].image_url == "https://i.guim.co.uk/a.jpg?width=460"
    assert stories[1].image_url == "https://ichef.bbci.co.uk/ace/standard/480/b.jpg"
    assert stories[2].image_url == "https://npr.brightspotcdn.com/c.jpg"
    assert stories[3].image_url is None  # looked for on the article page later
    assert stories[0].id != stories[1].id and len(stories[0].id) == 12


def test_og_image_skips_an_outlets_stand_in() -> None:
    stand_in = "https://media.npr.org/include/images/facebook-default-wide-s1400-c85.jpg"
    page = f'<meta property="og:image" content="{stand_in}" />'
    assert og_image(page, "https://npr.org/a") is None
    photo = "/wp-content/uploads/photo.jpg?resize=1920%2C1080&amp;q=80"
    page = f'<meta data-rh="true" property="og:image" content="{photo}"/>'
    assert og_image(page, "https://www.aljazeera.com/news/a") == (
        "https://www.aljazeera.com/wp-content/uploads/photo.jpg?resize=1920%2C1080&q=80"
    )


# ── beats ───────────────────────────────────────────────────────────────────


def test_keywords_in_capitals_only_match_capitals() -> None:
    ice = keyword_pattern("ICE")
    assert ice is not None
    assert ice.search("ICE agents detain workers")
    assert ice.search("Inside ICE's new detention plan")
    assert not ice.search("Ice storm closes roads")
    assert not ice.search("Police chief resigns")


def test_keywords_take_plurals_prefixes_and_phrases() -> None:
    election = keyword_pattern("election")
    deport = keyword_pattern("deport*")
    phrase = keyword_pattern("artificial intelligence")
    assert election and election.search("Elections loom")
    assert election and not election.search("Electioneering")
    assert deport and deport.search("Deportations rise") and deport.search("deported")
    assert phrase and phrase.search("Artificial  Intelligence rules")


def test_beats_switched_off_or_without_sources_are_skipped() -> None:
    beats = _beats(
        {"name": "Off", "enabled": False, "sources": ["npr-news"]},
        {"name": "Empty", "sources": ["nope"]},
        {"name": "Mine", "sources": "npr-news, https://my.town/feed", "weight": 9},
    )
    assert [b.name for b in beats] == ["Mine"]
    assert beats[0].sources == ["npr-news", "https://my.town/feed"]
    assert beats[0].weight == 5


def test_select_takes_the_beats_in_turn_by_weight() -> None:
    pool = {
        "npr-politics": [
            _story("Senate passes farm bill", hours_ago=1),
            _story("Governor vetoes housing plan", hours_ago=2),
            _story("Mayor unveils transit budget", hours_ago=3),
        ],
        "bbc-world": [
            _story("Ceasefire holds in Gaza", "bbc-world"),
            _story("Floods displace thousands in Sudan", "bbc-world"),
        ],
    }
    beats = _beats(
        {"name": "US", "sources": ["npr-politics"], "weight": 2},
        {"name": "World", "sources": ["bbc-world"]},
    )
    order = [beat.name for beat, _ in select(pool, beats, NOW)]
    # npr-politics gives at most two per beat — one outlet can't fill it.
    assert order == ["US", "US", "World", "World"]


def test_select_puts_keyword_matches_first_and_tops_up_with_the_newest() -> None:
    pool = {
        "npr-politics": [
            _story("Budget talks resume", hours_ago=1),
            _story("AOC rallies voters in the Bronx", hours_ago=5),
        ],
        "pbs-politics": [_story("Senate passes farm bill", "pbs-politics", hours_ago=2)],
    }
    beats = _beats({"name": "US", "sources": ["npr-politics", "pbs-politics"], "keywords": ["AOC"]})
    titles = [s.title for _, s in select(pool, beats, NOW)]
    assert titles == [
        "AOC rallies voters in the Bronx",
        "Budget talks resume",
        "Senate passes farm bill",
    ]


def test_select_drops_old_excluded_and_duplicate_stories() -> None:
    pool = {
        "npr-science": [
            _story("Telescope spots a new exoplanet", "npr-science"),
            _story("Telescope funding cuts loom", "npr-science", hours_ago=2),
            _story("Old comet news", "npr-science", hours_ago=80),
        ],
        "bbc-science": [
            _story("New exoplanet spotted by telescope", "bbc-science", outlet="BBC"),
        ],
    }
    beats = _beats(
        {
            "name": "Good news",
            "sources": ["npr-science", "bbc-science"],
            "exclude": ["cuts"],
            "maxAgeHours": 72,
        }
    )
    titles = [s.title for _, s in select(pool, beats, NOW)]
    assert titles == ["Telescope spots a new exoplanet"]


def test_softened_mornings_leave_out_graphic_headlines() -> None:
    pool = {
        "bbc-world": [
            _story("Airstrike kills 20 in Zaporizhzhia", "bbc-world"),
            _story("Hurricane Simon strengthens off Mexico", "bbc-world"),
        ]
    }
    beats = _beats({"name": "World", "sources": ["bbc-world"]})
    assert len(select(pool, beats, NOW)) == 2
    softened = [s.title for _, s in select(pool, beats, NOW, soften=True)]
    assert softened == ["Hurricane Simon strengthens off Mexico"]


# ── provider ────────────────────────────────────────────────────────────────

Handler = Callable[[httpx.Request], httpx.Response]

_FEEDS = {
    "feeds.npr.org": _rss(
        _item(
            "AOC rallies voters",
            "https://www.npr.org/a?utm_source=rss",
            extra='<media:content url="https://media.npr.org/a.jpg"/>',
        ),
    ),
    "www.aljazeera.com": _rss(_item("Hurricane nears coast", "https://www.aljazeera.com/b")),
}


def _handler(seen: list[str]) -> Handler:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        host = request.url.host
        if request.url.path.endswith(".jpg"):
            return httpx.Response(200, content=_jpeg(), headers={"content-type": "image/jpeg"})
        if host == "www.aljazeera.com" and request.url.path == "/b":
            page = (
                '<html><head><meta property="og:image" content="https://www.aljazeera.com/b.jpg"/>'
            )
            return httpx.Response(200, text=page, headers={"content-type": "text/html"})
        return httpx.Response(200, text=_FEEDS[host], headers={"content-type": "application/xml"})

    return handle


def _ctx(handler: Handler, **values: Any) -> ProviderContext:
    card = {
        "beats": [
            {"name": "US", "sources": ["npr-politics"], "keywords": ["AOC"]},
            {"name": "World", "sources": ["aljazeera"]},
        ],
        "quietHours": NEVER,
        "softenMornings": False,
        **values,
    }
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ProviderContext(Settings(), StoreRegistry(), card_settings={"news": card}, client=client)


async def test_poll_serves_stories_with_blurred_pictures_and_clean_links() -> None:
    seen: list[str] = []
    cache = NewsCache()
    value = await NewsProvider(cache=cache, clock=lambda: NOW).poll(_ctx(_handler(seen)))
    assert value is not None
    us, world = value["stories"]
    assert (us["beat"], us["outlet"], us["url"]) == ("US", "NPR", "https://www.npr.org/a")
    assert us["image"] == f"/api/news/{us['id']}.jpg"
    # The feed had no picture for this one; the article page's did.
    assert world["image"] == f"/api/news/{world['id']}.jpg"
    assert "https://www.aljazeera.com/b" in seen
    picture = cache.get(us["id"])
    assert picture is not None
    with Image.open(io.BytesIO(picture)) as image:
        assert max(image.size) <= 480
    # The tint is the picture's own colour, for the card's panel.
    red, green, _ = (int(us["tint"][i : i + 2], 16) for i in (1, 3, 5))
    assert red > 150 and green < 90


async def test_quiet_hours_reuse_the_stories_in_hand_without_fetching() -> None:
    seen: list[str] = []
    cache = NewsCache()
    provider = NewsProvider(cache=cache, clock=lambda: NOW)
    await provider.poll(_ctx(_handler(seen)))
    seen.clear()
    quiet = _ctx(_handler(seen), quietHours="00:00-23:59")
    value = await NewsProvider(cache=cache, clock=lambda: NOW).poll(quiet)
    assert value is not None and len(value["stories"]) == 2
    assert seen == []


async def test_quiet_hours_still_fetch_when_nothing_is_in_hand() -> None:
    seen: list[str] = []
    value = await NewsProvider(cache=NewsCache(), clock=lambda: NOW).poll(
        _ctx(_handler(seen), quietHours="00:00-23:59")
    )
    assert value is not None and len(value["stories"]) == 2
    # Feeds read, but no pictures fetched overnight.
    assert not any(url.endswith(".jpg") for url in seen)


async def test_a_story_that_leaves_the_rotation_takes_its_picture_with_it() -> None:
    cache = NewsCache()
    value = await NewsProvider(cache=cache, clock=lambda: NOW).poll(_ctx(_handler([])))
    assert value is not None
    world_id = value["stories"][1]["id"]
    assert cache.get(world_id) is not None
    only_us = [{"name": "US", "sources": ["npr-politics"]}]
    await NewsProvider(cache=cache, clock=lambda: NOW).poll(_ctx(_handler([]), beats=only_us))
    assert cache.get(world_id) is None


def test_the_manifest_offers_exactly_the_known_sources() -> None:
    spec = json.loads(MANIFEST.read_text())["settings"]["beats"]
    assert spec["enum"] == list(SOURCES)
    assert set(spec["labels"]) == set(SOURCES)
    for beat in spec["default"]:
        assert set(beat["sources"]) <= set(SOURCES)


async def test_api_serves_a_cached_picture_and_404s_otherwise(client: httpx.AsyncClient) -> None:
    from pinedaview.providers.news import NEWS_CACHE, _Picture

    NEWS_CACHE.put("0123456789ab", _Picture(b"\xff\xd8jpeg", "#000000"))
    try:
        ok = await client.get("/api/news/0123456789ab.jpg")
        assert ok.status_code == 200
        assert ok.headers["content-type"] == "image/jpeg"
        assert (await client.get("/api/news/ffffffffffff.jpg")).status_code == 404
        assert (await client.get("/api/news/..%2Fsecrets.jpg")).status_code == 404
    finally:
        NEWS_CACHE.keep_only(set())
