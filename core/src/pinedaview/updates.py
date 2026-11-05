# SPDX-License-Identifier: Apache-2.0
"""Software updates management and status for PinedaView."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from pinedaview import __version__
from pinedaview.config import Settings

logger = logging.getLogger(__name__)

STATUS_FILENAME = "update_status.json"

UpdateState = Literal["idle", "checking", "updating", "success", "failed"]


class UpdateStatus(BaseModel):
    state: UpdateState = "idle"
    step: str | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    current_version: str = __version__
    current_commit: str = ""
    target_version: str | None = None
    target_commit: str | None = None
    last_checked_at: str | None = None
    updated_at: str | None = None


def _get_current_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return res.stdout.strip() if res.returncode == 0 else ""
    except Exception:
        return ""


def get_update_status(settings: Settings) -> UpdateStatus:
    status_path = settings.state_dir / STATUS_FILENAME
    current_commit = _get_current_commit()
    if status_path.is_file():
        try:
            data = json.loads(status_path.read_text())
            status = UpdateStatus.model_validate(data)
            if not status.current_commit:
                status.current_commit = current_commit
            return status
        except Exception as exc:
            logger.warning("could not read %s: %s", status_path, exc)

    return UpdateStatus(
        state="idle",
        message="Display is up to date",
        current_version=__version__,
        current_commit=current_commit,
        updated_at=datetime.now(UTC).isoformat(),
    )


def write_update_status(settings: Settings, status: UpdateStatus) -> None:
    status_path = settings.state_dir / STATUS_FILENAME
    try:
        status_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = status_path.with_suffix(".tmp")
        tmp.write_text(status.model_dump_json(indent=2))
        tmp.replace(status_path)
    except Exception as exc:
        logger.error("failed to write %s: %s", status_path, exc)


def _find_runner() -> str:
    candidates = [
        "/usr/local/bin/pinedaview-update",
        "/usr/local/bin/pineda-update",
        str(Path(__file__).resolve().parents[3] / "scripts" / "pinedaview-update.sh"),
        str(Path(__file__).resolve().parents[3] / "scripts" / "pineda-update.sh"),
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    return candidates[0]


async def run_update(settings: Settings, check_only: bool = False) -> UpdateStatus:
    """Trigger the update runner via systemd and return updated status."""
    current_commit = _get_current_commit()
    initial_status = UpdateStatus(
        state="checking" if check_only else "updating",
        step="preflight" if check_only else "fetching",
        message="Checking for updates..." if check_only else "Starting software update...",
        current_version=__version__,
        current_commit=current_commit,
        last_checked_at=datetime.now(UTC).isoformat(),
    )
    write_update_status(settings, initial_status)

    cmd = ["systemctl", "start", "--no-block", "pinedaview-update.service"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            logger.error("systemctl start returned %d: %s", proc.returncode, err_msg)
    except Exception as exc:
        logger.error("failed to run %s: %s", cmd, exc)
        err_status = UpdateStatus(
            state="failed",
            step="runner",
            message="Could not start update",
            error_code="ERR_RUNNER_START",
            error_message=str(exc),
            current_version=__version__,
            current_commit=current_commit,
            updated_at=datetime.now(UTC).isoformat(),
        )
        write_update_status(settings, err_status)
        return err_status

    return initial_status
