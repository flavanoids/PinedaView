#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Forced command for a split-host [control] setup (see
# docs/OPERATIONS.md#split-host-control) — install on the *kiosk* device
# when pinedaview itself runs on a different host. Authorize the dedicated
# control key against exactly this script in the kiosk account's
# ~/.ssh/authorized_keys:
#
#   command="/usr/local/bin/pinedaview-control-wrapper.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty ssh-ed25519 AAAA...
#
# so a compromised server process can reach nothing on the kiosk device
# beyond these exact actions — no shell, no arbitrary commands. The
# kiosk's own polkit rule (pinedaview-restart.rules) still does the actual
# privilege escalation to systemd/logind; this just gets the request here
# from a different host over SSH.
#
#   sudo install -m 755 packaging/pinedaview-control-wrapper.sh \
#     /usr/local/bin/pinedaview-control-wrapper.sh
set -eu

case "${SSH_ORIGINAL_COMMAND:-}" in
  "systemctl restart --no-block pinedaview-kiosk.service" | "systemctl restart --no-block pineda-kiosk.service")
    exec ${SSH_ORIGINAL_COMMAND}
    ;;
  "systemctl reboot --no-block")
    exec systemctl reboot --no-block
    ;;
  # The phone menu's mini screen: one raw frame of what cage has on screen
  # (grim copies the composited buffer; no second browser). PNG at the
  # fastest level, at half scale: the server keeps 1024 px on the long side
  # anyway, and a full 2048x1280 photo frame is ~2.9 MB, seconds over the
  # kiosk's WiFi, where half is ~1.3 MB. (This grim has no JPEG.)
  "pinedaview-snapshot" | "pineda-snapshot")
    rt="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    sock=$(ls "$rt"/wayland-*.lock 2>/dev/null | head -1)
    [ -n "$sock" ] || { echo "pinedaview-control-wrapper: no compositor" >&2; exit 1; }
    XDG_RUNTIME_DIR="$rt" WAYLAND_DISPLAY="$(basename "$sock" .lock)" exec grim -t png -l 1 -s 0.5 -
    ;;
  # Which way the screen is turned. Saved here on the kiosk, so it holds
  # through reboots and whichever server is answering; pinedaview-kiosk-launch
  # puts it back each time cage starts.
  "pinedaview-rotation" | "pineda-rotation")
    rot_file="$HOME/.config/pinedaview/rotation"
    [ -f "$rot_file" ] || rot_file="$HOME/.config/pineda/rotation"
    cat "$rot_file" 2>/dev/null || echo normal
    ;;
  "pinedaview-rotate normal" | "pinedaview-rotate 90" | "pinedaview-rotate 180" | "pinedaview-rotate 270" | \
  "pineda-rotate normal" | "pineda-rotate 90" | "pineda-rotate 180" | "pineda-rotate 270")
    turn="${SSH_ORIGINAL_COMMAND##* }"
    mkdir -p "$HOME/.config/pinedaview"
    echo "$turn" > "$HOME/.config/pinedaview/rotation"
    rt="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    sock=$(ls "$rt"/wayland-*.lock 2>/dev/null | head -1)
    # No compositor yet: saved, and the next start applies it.
    [ -n "$sock" ] || exit 0
    export XDG_RUNTIME_DIR="$rt" WAYLAND_DISPLAY="$(basename "$sock" .lock)"
    out=$(wlr-randr | awk 'NR == 1 { print $1 }')
    exec wlr-randr --output "$out" --transform "$turn"
    ;;
  *)
    echo "pinedaview-control-wrapper: command not allowed" >&2
    exit 1
    ;;
esac
