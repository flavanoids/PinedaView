# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from pinedaview.config import Settings, load_settings


def test_defaults_need_no_file() -> None:
    s = load_settings()
    assert s.location.query == "New York"
    assert s.units == "imperial"
    assert s.providers.weather_interval_s == 900


def test_toml_file_is_read(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('units = "metric"\n[location]\nquery = "Berlin"\n[providers]\njitter_s = 5\n')
    s = load_settings(cfg)
    assert s.units == "metric"
    assert s.location.query == "Berlin"
    assert s.providers.jitter_s == 5


def test_env_overrides_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[location]\nquery = "Berlin"\n')
    monkeypatch.setenv("PINEDA_LOCATION__QUERY", "Tokyo")
    assert load_settings(cfg).location.query == "Tokyo"


def test_explicit_overrides_win(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[location]\nquery = "Berlin"\n')
    s = load_settings(cfg, overrides={"location": {"query": "Lisbon"}, "debug_http": True})
    assert s.location.query == "Lisbon"
    assert s.debug_http is True


def test_interval_floor_is_enforced() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 60"):
        Settings(providers={"weather_interval_s": 5})
