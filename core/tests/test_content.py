# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from pinedaview.config import Settings
from pinedaview.content import weather_icon
from pinedaview.content.daily import daily_affirmation, daily_affirmations, daily_word
from pinedaview.providers.daily import DailyContentProvider
from tests.conftest import FakeContext


def test_weather_icon_falls_back() -> None:
    assert weather_icon("113")  # sunny
    assert weather_icon("does-not-exist") == "\N{THERMOMETER}"


def test_daily_word_is_stable_per_day() -> None:
    day = date(2026, 8, 28)
    first = daily_word(day)
    assert daily_word(day) == first
    assert first["english"]
    assert "literal" in first and "note" in first  # keys always present, may be None

    langs = first["languages"]
    codes = [lang["code"] for lang in langs]
    assert codes[0] == "es"  # Spanish is the anchor and always leads
    assert set(codes) <= {"es", "ar", "vi", "zh"}
    for lang in langs:
        assert lang["text"] and lang["pron"] and lang["lang"]
    # Each language carries a BCP-47 code so the client can mark up the text for
    # screen readers; Arabic, when present, is flagged right-to-left.
    arabic = next((lang for lang in langs if lang["code"] == "ar"), None)
    if arabic is not None:
        assert arabic["dir"] == "rtl"


def test_daily_word_deck_shape() -> None:
    """Legacy words keep all four languages; the Spanish deck adds usage notes."""
    from pinedaview.content import MULTILINGUAL_WORDS

    words = [e for e in MULTILINGUAL_WORDS if e["kind"] == "word"]
    phrases = [e for e in MULTILINGUAL_WORDS if e["kind"] == "phrase"]
    assert len(words) > 150
    assert len(phrases) > 40
    assert all(set(e["langs"]) == {"es", "ar", "vi", "zh"} for e in words)
    assert all("es" in e["langs"] for e in phrases)
    assert any(e["note"] for e in phrases)
    assert {e["register"] for e in phrases} <= {"neutral", "informal", "crude"}


def test_daily_word_leans_spanish() -> None:
    """Across 100 days, ~70% land on the everyday-Spanish deck."""
    from pinedaview.content import MULTILINGUAL_WORDS

    phrase_en = {e["en"] for e in MULTILINGUAL_WORDS if e["kind"] == "phrase"}
    hits = sum(
        1
        for offset in range(100)
        if daily_word(date(2026, 1, 1) + timedelta(days=offset))["english"] in phrase_en
    )
    assert 55 <= hits <= 85


def test_affirmation_is_stable_and_recorded(tmp_path: Path) -> None:
    day = date(2026, 8, 28)
    one = daily_affirmation(tmp_path, day)
    two = daily_affirmation(tmp_path, day)
    assert one == two
    assert one["text"] and one["author"]
    assert (tmp_path / "affirmation_history.json").exists()


def test_affirmation_avoids_recent_repeats(tmp_path: Path) -> None:
    seen: set[str] = set()
    for offset in range(20):
        pick = daily_affirmation(tmp_path, date(2026, 1, 1) + timedelta(days=offset))
        assert pick["text"] not in seen
        seen.add(pick["text"])


def test_daily_affirmations_is_a_distinct_stable_set(tmp_path: Path) -> None:
    day = date(2026, 8, 28)
    first = daily_affirmations(tmp_path, day, count=5)
    assert first == daily_affirmations(tmp_path, day, count=5)
    assert len(first) == 5
    texts = [q["text"] for q in first]
    assert len(set(texts)) == 5
    # The rotating set leads with the same quote the singular helper returns.
    assert first[0] == daily_affirmation(tmp_path, day)


async def test_daily_provider_publishes_both(settings: Settings) -> None:
    value = await DailyContentProvider().poll(FakeContext(settings))
    assert set(value) == {"date", "affirmation", "affirmations", "word"}
    assert value["affirmation"]["text"]
    assert value["affirmations"][0] == value["affirmation"]
    assert len(value["affirmations"]) >= 2


async def test_daily_provider_caches_within_a_day(settings: Settings) -> None:
    provider = DailyContentProvider()
    ctx = FakeContext(settings)
    first = await provider.poll(ctx)
    assert await provider.poll(ctx) is first
