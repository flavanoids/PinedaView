# SPDX-License-Identifier: Apache-2.0
"""Static, human-authored content: quote list, multilingual phrase list, weather
glyphs. Vendored from PinedaDisplay. The typed surface lives here; the data
modules themselves are excluded from lint and type-checking as content."""

from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

from pinedaview.content.affirmations import AFFIRMATIONS as _AFFIRMATIONS
from pinedaview.content.multilingual_words import MULTILINGUAL_WORDS as _WORDS
from pinedaview.content.spanish_phrases import SPANISH_PHRASES as _PHRASES
from pinedaview.content.weather_icons import WEATHER_ICONS as _ICONS

Affirmation = tuple[str, str, int | None]

# Display order and English names for the languages a card can cycle. Spanish is
# the anchor and is always present; the other three are optional per entry.
LANG_ORDER: tuple[str, ...] = ("es", "ar", "vi", "zh")
LANG_NAMES: dict[str, str] = {
    "es": "Spanish",
    "ar": "Arabic",
    "vi": "Vietnamese",
    "zh": "Mandarin",
}


class LangText(TypedDict):
    """One language's rendering of an entry."""

    text: str
    pron: str


class MultilingualEntry(TypedDict):
    """A single card of the phrase deck.

    ``kind`` is ``"word"`` for the legacy single-word vocabulary (always carries
    all four languages) and ``"phrase"`` for the everyday-Spanish deck (Spanish
    only, unless a natural equivalent in another language was authored).
    """

    kind: Literal["word", "phrase"]
    en: str
    literal: str | None
    note: str | None
    tags: list[str]
    level: str
    register: Literal["neutral", "informal", "crude"]
    langs: dict[str, LangText]


def _entry_from_tuple(row: tuple[str, ...]) -> MultilingualEntry:
    """Adapt a legacy ``(en, es, es_pron, ar, …)`` 9-tuple to the entry dict."""
    en, es, es_p, ar, ar_p, vi, vi_p, zh, zh_p = row
    return {
        "kind": "word",
        "en": en,
        "literal": None,
        "note": None,
        "tags": ["word"],
        "level": "B1",
        "register": "neutral",
        "langs": {
            "es": {"text": es, "pron": es_p},
            "ar": {"text": ar, "pron": ar_p},
            "vi": {"text": vi, "pron": vi_p},
            "zh": {"text": zh, "pron": zh_p},
        },
    }


def _normalize_phrase(raw: dict[str, Any]) -> MultilingualEntry:
    """Fill defaults on a loosely-authored ``spanish_phrases`` row.

    Minimum row: ``{"es", "pron", "en"}``. ``langs`` is derived from ``es`` /
    ``pron``; an ``ar`` / ``vi`` / ``zh`` key (each a ``{"text", "pron"}`` dict)
    adds that language to the entry.
    """
    langs: dict[str, LangText] = {"es": {"text": raw["es"], "pron": raw["pron"]}}
    for code in ("ar", "vi", "zh"):
        extra = raw.get(code)
        if extra:
            langs[code] = {"text": extra["text"], "pron": extra["pron"]}
    return {
        "kind": "phrase",
        "en": raw["en"],
        "literal": raw.get("literal"),
        "note": raw.get("note"),
        "tags": list(raw.get("tags", [])),
        "level": raw.get("level", "B1"),
        "register": raw.get("register", "informal"),
        "langs": langs,
    }


AFFIRMATIONS: list[Affirmation] = cast("list[Affirmation]", list(_AFFIRMATIONS))
MULTILINGUAL_WORDS: list[MultilingualEntry] = [_entry_from_tuple(row) for row in _WORDS] + [
    _normalize_phrase(raw) for raw in _PHRASES
]
WEATHER_ICONS: dict[str, str] = dict(_ICONS)

_DEFAULT_GLYPH = "\N{THERMOMETER}"


def weather_icon(code: str | int) -> str:
    """Emoji for a wttr.in weather code."""
    return WEATHER_ICONS.get(str(code), _DEFAULT_GLYPH)
