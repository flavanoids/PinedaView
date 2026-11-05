# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import pytest

from pinedaview.config import Settings
from pinedaview.updates import (
    UpdateStatus,
    get_update_status,
    run_update,
    write_update_status,
)


def test_get_update_status_default(tmp_path: Path) -> None:
    settings = Settings(state_dir=tmp_path)
    status = get_update_status(settings)
    assert status.state == "idle"
    assert status.message == "Display is up to date"


def test_write_and_read_update_status(tmp_path: Path) -> None:
    settings = Settings(state_dir=tmp_path)
    custom = UpdateStatus(
        state="updating",
        step="building_web",
        message="Compiling display assets...",
        current_version="1.0.0",
        target_version="1.0.1",
        target_commit="abcdef1",
    )
    write_update_status(settings, custom)
    read_back = get_update_status(settings)
    assert read_back.state == "updating"
    assert read_back.step == "building_web"
    assert read_back.target_version == "1.0.1"
    assert read_back.target_commit == "abcdef1"


@pytest.mark.asyncio
async def test_run_update_check_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(state_dir=tmp_path)
    # Mock systemctl subprocess so it doesn't fail on developer/test machines
    import asyncio
    from unittest.mock import AsyncMock

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.returncode = 0
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=mock_proc))

    status = await run_update(settings, check_only=True)
    assert status.state == "checking"
    assert status.step == "preflight"
    read_back = get_update_status(settings)
    assert read_back.state == "checking"
