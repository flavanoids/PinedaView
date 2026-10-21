# SPDX-License-Identifier: Apache-2.0
"""Deterministic once-a-day content selection.

The date seeds an MD5 hash, so a given day always shows the same affirmation and
the same word — refreshes and restarts don't reshuffle it. Affirmations also
avoid repeating within a 60-day rolling window, tracked in a small JSON file
under the state directory.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pinedaview.content import (
    AFFIRMATIONS,
    LANG_NAMES,
    LANG_ORDER,
    MULTILINGUAL_WORDS,
    MultilingualEntry,
)

logger = logging.getLogger(__name__)

_HISTORY_WINDOW_DAYS = 60
_HISTORY_FILENAME = "affirmation_history.json"

# The everyday-Spanish phrases are the point of the card now; the legacy poetic
# single words still turn up, but only ~30% of days.
_PHRASE_DAY_ODDS = 7  # in 10
_PHRASES = [entry for entry in MULTILINGUAL_WORDS if entry["kind"] == "phrase"]
_WORDS_ONLY = [entry for entry in MULTILINGUAL_WORDS if entry["kind"] == "word"]


def _seed_index(seed: str, modulo: int) -> int:
    return int(hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest(), 16) % modulo


def _word_payload(entry: MultilingualEntry) -> dict[str, Any]:
    languages: list[dict[str, Any]] = []
    for code in LANG_ORDER:
        text = entry["langs"].get(code)
        if text is None:
            continue
        item: dict[str, Any] = {
            "lang": LANG_NAMES[code],
            "code": code,
            "text": text["text"],
            "pron": text["pron"],
        }
        if code == "ar":
            item["dir"] = "rtl"
        languages.append(item)
    return {
        "english": entry["en"],
        "literal": entry["literal"],
        "note": entry["note"],
        "languages": languages,
    }


def daily_word(today: date | None = None) -> dict[str, Any]:
    day = (today or date.today()).isoformat()
    pool = _PHRASES if _PHRASES and _seed_index(f"{day}:word-kind", 10) < _PHRASE_DAY_ODDS else None
    if pool is None:
        pool = _WORDS_ONLY or _PHRASES
    return _word_payload(pool[_seed_index(f"{day}:word", len(pool))])


class _History:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> dict[str, list[str]]:
        try:
            data: Any = json.loads(self._path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, history: dict[str, list[str]]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(history))
        except OSError as exc:
            logger.warning("could not persist affirmation history: %s", exc)

    @staticmethod
    def prune(history: dict[str, list[str]], today: date) -> dict[str, list[str]]:
        cutoff = timedelta(days=_HISTORY_WINDOW_DAYS)
        return {
            quote: recent
            for quote, dates in history.items()
            if (recent := [d for d in dates if today - date.fromisoformat(d) < cutoff])
        }


def _ordered_picks(day_str: str, recent: set[str]) -> list[int]:
    """Distinct affirmation indices for the day, freshest-first.

    Deterministic: the bare-day hash leads (so the first quote is stable across
    refreshes and restarts), then numbered probes fill the rest without
    clustering. Quotes shown within the history window are pushed to the back
    rather than dropped, so the list is always long enough to cycle.
    """
    total = len(AFFIRMATIONS)
    fresh: list[int] = []
    seen_in_window: list[int] = []
    seen: set[str] = set()
    for attempt in range(total * 4):
        seed = day_str if attempt == 0 else f"{day_str}:{attempt - 1}"
        index = _seed_index(seed, total)
        text = AFFIRMATIONS[index][0]
        if text in seen:
            continue
        seen.add(text)
        (seen_in_window if text in recent else fresh).append(index)
        if len(seen) == total:
            break
    if not fresh:  # every quote seen inside the window
        logger.info("affirmation history window exhausted")
    return fresh + seen_in_window


def _select(state_dir: Path, today: date | None, count: int) -> list[dict[str, Any]]:
    day = today or date.today()
    day_str = day.isoformat()
    store = _History(state_dir / _HISTORY_FILENAME)
    history = _History.prune(store.load(), day)

    # A quote shown only *today* isn't a repeat — re-selecting it keeps the day
    # stable across refreshes and restarts.
    recent = {quote for quote, dates in history.items() if any(d != day_str for d in dates)}
    picks = _ordered_picks(day_str, recent)[: max(1, count)]

    rows = [AFFIRMATIONS[i] for i in picks]
    # Only the lead quote counts against the 60-day window; the rest are that
    # day's cycle filler and shouldn't burn through the catalogue ~5x faster.
    lead = rows[0][0]
    history.setdefault(lead, [])
    if day_str not in history[lead]:
        history[lead].append(day_str)
    store.save(history)

    return [{"text": text, "author": author, "year": year} for text, author, year in rows]


def daily_affirmation(state_dir: Path, today: date | None = None) -> dict[str, Any]:
    return _select(state_dir, today, 1)[0]


def daily_affirmations(
    state_dir: Path, today: date | None = None, count: int = 5
) -> list[dict[str, Any]]:
    """The day's rotating set of quotes — the client cross-fades between them.

    The first entry equals :func:`daily_affirmation`; the rest are distinct and
    also honour the 60-day no-repeat window.
    """
    return _select(state_dir, today, count)
