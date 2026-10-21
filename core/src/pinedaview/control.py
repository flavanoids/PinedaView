# SPDX-License-Identifier: Apache-2.0
"""Restart controls for the physical kiosk device.

When the server runs on the same box as the kiosk, both actions shell out to
``systemctl`` directly, which talks to systemd (and, for the reboot,
``logind``) over D-Bus rather than exec'ing a setuid binary — the only way to
escalate privilege from a service hardened with ``NoNewPrivileges`` and
``ProtectSystem=strict`` (see ``pineda-web.service``). The polkit rule that
authorizes the service account to do so lives in
``packaging/pineda-restart.rules``.

When ``[control] host`` is set (the server offloaded to a different machine
than the kiosk), the same commands run over SSH against that host instead —
see docs/OPERATIONS.md#split-host-control. Either way these buttons always
act on the kiosk device, never on whatever machine happens to be running
pineda-web.
"""

from __future__ import annotations

import hmac
import io
import logging
import subprocess
import time
from pathlib import Path

from PIL import Image

from pinedaview.config import ControlConfig

logger = logging.getLogger(__name__)

# Just enough for systemctl (or ssh) to hand the job off, not for the job
# itself to finish — see --no-block below.
_TIMEOUT_S = 10


class ControlError(RuntimeError):
    """A restart/reboot command failed to even hand off to systemd."""


class PinGate:
    """Checks the restart PIN, and stops answering for a minute after five
    wrong guesses in a row so the six digits can't simply be walked."""

    MAX_MISSES = 5
    LOCKOUT_S = 60.0

    def __init__(self) -> None:
        self._misses = 0
        self._locked_until = 0.0

    def locked_for(self) -> float:
        """Seconds until guesses are accepted again (0 when open)."""
        return max(0.0, self._locked_until - time.monotonic())

    def check(self, expected: str | None, given: str | None) -> bool:
        if expected is None:
            return True
        if self.locked_for():
            return False
        if given is not None and hmac.compare_digest(given.encode(), expected.encode()):
            self._misses = 0
            return True
        self._misses += 1
        if self._misses >= self.MAX_MISSES:
            self._misses = 0
            self._locked_until = time.monotonic() + self.LOCKOUT_S
        return False


def restart_display(control: ControlConfig) -> None:
    """Queue a restart of the kiosk (cage + Chromium), not the server itself.

    ``--no-block``: without it, ``systemctl restart`` waits for the unit to
    fully stop *and* start before returning — and a wedged Chromium can take
    up to TimeoutStopUSec (90s default) to die, which would hang this whole
    HTTP request and time out here well before systemd gives up on it. Queue
    it instead: systemd escalates to SIGKILL on its own schedule regardless
    of whether anything is still waiting on the result.
    """
    archive_diagnostic_snapshot(control, reason="restart-display")
    _run(control, ["systemctl", "restart", "--no-block", control.kiosk_service])


def restart_system(control: ControlConfig) -> None:
    """Queue a reboot of the kiosk device (see restart_display for --no-block)."""
    archive_diagnostic_snapshot(control, reason="restart-system")
    _run(control, ["systemctl", "reboot", "--no-block"])


# The phone menu's mini screen is ~360 CSS px wide at up to 3x, so 1024 px
# is plenty; a JPEG this size is ~60 KB.
SNAPSHOT_WIDTH = 1024


def snapshot(control: ControlConfig) -> bytes:
    """A small JPEG of what the kiosk has on screen, for the phone menu.

    Only for a split-host setup: the kiosk-side wrapper runs grim against
    cage and sends back a raw frame, which is shrunk here rather than on
    the Pi. A single-host install has no wrapper, so there's nothing to call.
    """
    if not control.host:
        raise ControlError("snapshots need [control].host")
    cmd = _remote_wrap(control, ["pineda-snapshot"])
    try:
        raw = subprocess.run(cmd, check=True, capture_output=True, timeout=_TIMEOUT_S).stdout
        frame = Image.open(io.BytesIO(raw))
        frame.thumbnail((SNAPSHOT_WIDTH, SNAPSHOT_WIDTH))
        out = io.BytesIO()
        frame.convert("RGB").save(out, "JPEG", quality=75)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("snapshot failed: %s", exc)
        raise ControlError(str(exc)) from exc
    return out.getvalue()


DIAGNOSTICS_DIR = Path("/var/lib/pineda-web/diagnostics")
MAX_DIAGNOSTIC_SNAPSHOTS = 10


def archive_diagnostic_snapshot(
    control: ControlConfig,
    reason: str = "restart",
    dest_dir: Path | None = None,
) -> Path | None:
    """Capture a grim screenshot before restarts or during failure troubleshooting.

    Saves to a bounded FIFO directory (max 10 snapshots) to preserve visual post-mortem
    evidence without overflowing disk space. Fails softly so restarts are never blocked.
    """
    if not control.host:
        return None
    try:
        jpeg_bytes = snapshot(control)
        target_dir = dest_dir or DIAGNOSTICS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        out_file = target_dir / f"kiosk-{reason}-{ts}.jpg"
        out_file.write_bytes(jpeg_bytes)
        logger.info("archived diagnostic snapshot: %s (%d bytes)", out_file.name, len(jpeg_bytes))

        # Enforce bounded ring buffer: prune oldest beyond MAX_DIAGNOSTIC_SNAPSHOTS
        existing = sorted(target_dir.glob("kiosk-*.jpg"), key=lambda p: p.stat().st_mtime)
        while len(existing) > MAX_DIAGNOSTIC_SNAPSHOTS:
            oldest = existing.pop(0)
            oldest.unlink(missing_ok=True)
        return out_file
    except Exception as exc:
        logger.warning("could not archive diagnostic snapshot (%s): %s", reason, exc)
        return None


def _run(control: ControlConfig, systemctl_cmd: list[str]) -> None:
    cmd = _remote_wrap(control, systemctl_cmd) if control.host else systemctl_cmd
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=_TIMEOUT_S, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("control command failed: %s: %s", " ".join(cmd), exc)
        raise ControlError(str(exc)) from exc


def _remote_wrap(control: ControlConfig, systemctl_cmd: list[str]) -> list[str]:
    # -F /dev/null + an explicit known_hosts: the service account (e.g.
    # "pineda", ProtectHome=true) has no readable $HOME, so ssh must be told
    # everything explicitly rather than falling back to ~/.ssh/*.
    ssh_cmd = [
        "ssh",
        "-F",
        "/dev/null",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if control.ssh_key:
        ssh_cmd += ["-i", str(control.ssh_key)]
        ssh_cmd += ["-o", f"UserKnownHostsFile={control.ssh_key.parent}/known_hosts"]
    ssh_cmd.append(f"{control.user}@{control.host}")
    return ssh_cmd + systemctl_cmd
