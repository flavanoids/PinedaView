# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

from pinedaview.themes import (
    all_themes,
    find_theme,
    load_file_themes,
    parse_theme_dict,
    set_file_themes,
)


def test_parse_theme_dict_basic() -> None:
    data = {
        "name": "nordic_pine",
        "label": "Nordic Pine",
        "blurb": "Cool pine and slate.",
        "stage": "#2e3440",
        "accent": "#88c0d0",
        "weather": "#3b4252",
        "clock": "#434c5e",
        "affirmation": "#4c566a",
        "font": "inter",
    }
    themes = parse_theme_dict(data)
    assert len(themes) == 1
    t = themes[0]
    assert t.name == "nordic_pine"
    assert t.label == "Nordic Pine"
    assert t.accent == "#88c0d0"
    assert t.stage == "#2e3440"
    assert t.font == "inter"
    assert t.custom is True
    assert t.night is None


def test_parse_theme_dict_with_night_table() -> None:
    data = {
        "name": "ice_and_fire",
        "label": "Ice and Fire",
        "stage": "#e5edf3",
        "accent": "#e0614a",
        "weather": "#487899",
        "clock": "#365c78",
        "affirmation": "#5a829e",
        "night": {
            "stage": "#0e1720",
            "accent": "#f07560",
            "weather": "#234057",
            "clock": "#1b3347",
            "affirmation": "#284459",
        },
    }
    themes = parse_theme_dict(data)
    assert len(themes) == 2
    day = themes[0]
    night = themes[1]
    assert day.name == "ice_and_fire"
    assert day.night == "ice_and_fire_night"
    assert night.name == "ice_and_fire_night"
    assert night.label == "Ice and Fire (Night)"
    assert night.stage == "#0e1720"
    assert night.accent == "#f07560"


def test_load_file_themes_from_directory(tmp_path: Path) -> None:
    toml_content = """
name = "autumn_breeze"
label = "Autumn Breeze"
blurb = "Warm amber and rust."
stage = "#f7eee4"
accent = "#d9531e"
weather = "#c46238"
clock = "#784224"
affirmation = "#9c5b36"
"""
    (tmp_path / "autumn.toml").write_text(toml_content.strip())

    json_content = {
        "name": "cyber_glow",
        "label": "Cyber Glow",
        "stage": "#0d1117",
        "accent": "#00f0ff",
        "weather": "#1b2432",
        "clock": "#141c28",
        "affirmation": "#223044",
        "surface": "glass",
    }
    (tmp_path / "cyber.json").write_text(json.dumps(json_content))

    # Also write a corrupted file to ensure robust error handling
    (tmp_path / "broken.toml").write_text("this is not valid toml = [[[]")

    loaded = load_file_themes(tmp_path)
    assert len(loaded) == 2
    names = {t.name for t in loaded}
    assert "autumn_breeze" in names
    assert "cyber_glow" in names

    set_file_themes(loaded)
    found = find_theme("cyber_glow")
    assert found is not None
    assert found.surface == "glass"
    assert any(t.name == "autumn_breeze" for t in all_themes())
