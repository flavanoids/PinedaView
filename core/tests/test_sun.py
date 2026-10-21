# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from pinedaview.config import LocationConfig, Settings
from pinedaview.sun import is_night, next_transition, resolve_coords
from pinedaview.themes import THEMES, get_theme
from pinedaview.view import _resolve_theme_name

_TZ = ZoneInfo("America/Chicago")
_HOUSTON = (29.7604,-95.3698)


def test_is_night_flips_around_sunrise_and_sunset() -> None:
    noon = datetime(2026, 9, 16, 12, 0, tzinfo=_TZ)
    midnight = datetime(2026, 9, 16, 0, 0, tzinfo=_TZ)
    assert is_night(noon, *_HOUSTON) is False
    assert is_night(midnight, *_HOUSTON) is True


def test_dst_transition_does_not_break_is_night() -> None:
    # 2026-11-01 is the US fall-back DST date — the same wall-clock hour
    # (say 18:00) sits on opposite sides of sunset before vs. after the
    # offset change. No special-casing needed: astral resolves each date's
    # sun times against that date's own UTC offset via zoneinfo.
    before = datetime(2026, 10, 31, 18, 0, tzinfo=_TZ)
    after = datetime(2026, 11, 2, 18, 0, tzinfo=_TZ)
    assert is_night(before, *_HOUSTON) is False  # still daylight pre-DST-end
    assert is_night(after, *_HOUSTON) is True  # dark by 18:00 post-DST-end


def test_next_transition_is_strictly_after_moment() -> None:
    moment = datetime(2026, 9, 16, 12, 0, tzinfo=_TZ)
    target = next_transition(moment, *_HOUSTON)
    assert target is not None
    assert target > moment
    assert target.date() == moment.date()  # sunset, same day


def test_resolve_coords_prefers_explicit_lat_lon() -> None:
    settings = Settings(location=LocationConfig(query="Houston", latitude=1.0, longitude=2.0))
    assert resolve_coords(settings) == (1.0, 2.0)


def test_resolve_coords_parses_pinned_query() -> None:
    settings = Settings(location=LocationConfig(query="29.7604,-95.3698"))
    assert resolve_coords(settings) == (29.7604,-95.3698)


def test_resolve_coords_none_without_geocode_or_store() -> None:
    settings = Settings(location=LocationConfig(query="Houston"))
    assert resolve_coords(settings) is None


def test_blush_has_a_night_variant_registered() -> None:
    assert get_theme("blush").night == "blush_night"
    assert "blush_night" in THEMES


def _contrast(a: str, b: str) -> float:
    def lum(hex_color: str) -> float:
        h = hex_color.lstrip("#")
        rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_every_light_theme_has_a_dark_readable_night_twin() -> None:
    twins = {t.night for t in THEMES.values() if t.night}
    for theme in THEMES.values():
        if theme.name in twins or _contrast(theme.stage, "#000000") < 5:
            continue  # a twin itself, or already a dark-stage theme
        assert theme.night in THEMES, theme.name
        night = THEMES[theme.night]
        assert night.night is None
        assert night.surface == theme.surface
        assert _contrast(night.stage, "#000000") < 1.5, night.name
        for slot, card in night.cards.items():
            assert _contrast(night.on_card, card) >= 4.5, (night.name, slot)


def test_resolve_theme_name_picks_night_variant_after_dark() -> None:
    settings = Settings(location=LocationConfig(query="29.7604,-95.3698"))
    from pinedaview.stores import StoreRegistry

    stores = StoreRegistry()
    day = datetime(2026, 9, 16, 12, 0, tzinfo=_TZ)
    night = datetime(2026, 9, 16, 0, 0, tzinfo=_TZ)
    assert _resolve_theme_name("blush", day, settings, stores) == "blush"
    assert _resolve_theme_name("blush", night, settings, stores) == "blush_night"


def test_resolve_theme_name_no_flip_without_coords() -> None:
    settings = Settings(location=LocationConfig(query="Houston"))  # not geocoded, no coords
    from pinedaview.stores import StoreRegistry

    stores = StoreRegistry()
    night = datetime(2026, 9, 16, 0, 0, tzinfo=_TZ)
    assert _resolve_theme_name("blush", night, settings, stores) == "blush"


def test_resolve_theme_name_no_flip_for_theme_without_night_variant() -> None:
    settings = Settings(location=LocationConfig(query="29.7604,-95.3698"))
    from pinedaview.stores import StoreRegistry

    stores = StoreRegistry()
    night = datetime(2026, 9, 16, 0, 0, tzinfo=_TZ)
    assert _resolve_theme_name("quiet_canvas", night, settings, stores) == "quiet_canvas"
