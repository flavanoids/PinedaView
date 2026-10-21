#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Forced command for a split-host [control] setup (see
# docs/OPERATIONS.md#split-host-control) — install on the *kiosk* device
# when pineda-web itself runs on a different host. Authorize the dedicated
# control key against exactly this script in the kiosk account's
# ~/.ssh/authorized_keys:
#
#   command="/usr/local/bin/pineda-control-wrapper.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty ssh-ed25519 AAAA...
#
# so a compromised server process can reach nothing on the kiosk device
# beyond these exact actions — no shell, no arbitrary commands. The
# kiosk's own polkit rule (pineda-restart.rules) still does the actual
# privilege escalation to systemd/logind; this just gets the request here
# from a different host over SSH.
#
#   sudo install -m 755 packaging/pineda-control-wrapper.sh \
#     /usr/local/bin/pineda-control-wrapper.sh
set -eu

case "${SSH_ORIGINAL_COMMAND:-}" in
  "systemctl restart --no-block pineda-kiosk.service")
    exec systemctl restart --no-block pineda-kiosk.service
    ;;
  "systemctl reboot --no-block")
    exec systemctl reboot --no-block
    ;;
  # The phone menu's mini screen: one raw frame of what cage has on screen
  # (grim copies the composited buffer; no second browser). PNG at the
  # fastest level: ~0.3 s of Pi CPU for 1.5 MB, where a raw frame is 7.8 MB
  # and takes seconds over the kiosk's WiFi. The server shrinks it.
  "pineda-snapshot")
    rt="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    sock=$(ls "$rt"/wayland-*.lock 2>/dev/null | head -1)
    [ -n "$sock" ] || { echo "pineda-control-wrapper: no compositor" >&2; exit 1; }
    XDG_RUNTIME_DIR="$rt" WAYLAND_DISPLAY="$(basename "$sock" .lock)" exec grim -t png -l 1 -
    ;;
  *)
    echo "pineda-control-wrapper: command not allowed" >&2
    exit 1
    ;;
esac
