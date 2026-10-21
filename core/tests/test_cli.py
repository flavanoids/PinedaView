# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from pinedaview import cli
from pinedaview.config import Settings


def test_parser_requires_a_command() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["--version"])
    assert exc.value.code == 0
    assert "pineda-web" in capsys.readouterr().out


def test_flags_become_settings(tmp_path: Path) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text("")
    args = cli.build_parser().parse_args(
        [
            "serve",
            "--config",
            str(cfg),
            "--location",
            "Oslo",
            "--host",
            "127.0.0.1",
            "--port",
            "9001",
        ]
    )
    settings = cli._settings_for(args)
    assert settings.location.query == "Oslo"
    assert settings.api.host == "127.0.0.1"
    assert settings.api.port == 9001


def test_main_serve_delegates_to_run_api(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[Settings, bool]] = []

    async def fake_run_api(settings: Settings, *, watch: bool = False) -> None:
        seen.append((settings, watch))

    monkeypatch.setattr(cli, "run_api", fake_run_api)
    assert cli.main(["serve", "--location", "Rome"]) == 0
    assert cli.main(["dev", "--location", "Rome"]) == 0
    assert seen[0][0].location.query == "Rome"
    assert seen[0][1] is False
    assert seen[1][1] is True
