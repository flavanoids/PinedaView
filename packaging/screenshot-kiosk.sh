#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Grab a screenshot of a running pineda-kiosk.service display, from a
# developer machine over SSH, without touching the kiosk's Chromium process.
#
# Uses grim (https://github.com/emersion/grim), a one-shot Wayland
# screenshot tool that asks the compositor (cage) to copy its already-
# composited output buffer via the wlr-screencopy protocol. This is safe on
# single-GPU kiosk hardware: it never opens a second Chromium/browser
# process or GPU context, unlike headless-browser screenshot automation —
# see the "airplaypi kiosk safety" note in docs/OPERATIONS.md. Cost is a
# ~1-2s compositor-side buffer copy over an already-live SSH connection.
#
# Usage:
#   packaging/screenshot-kiosk.sh <ssh-host> [output-file]
#
# <ssh-host> is anything `ssh` accepts (an alias from ~/.ssh/config, or
# user@host). Requires grim to already be installed on the kiosk device
# (`sudo apt install grim`) and a normal (non-forced-command) SSH login to
# the account running pineda-kiosk.service (the split-host control key in
# docs/OPERATIONS.md is forced-command-only and can't run this).
set -eu

host="${1:?usage: screenshot-kiosk.sh <ssh-host> [output-file]}"
out="${2:-kiosk-$(date +%Y%m%d-%H%M%S).png}"

ssh "$host" '
  set -eu
  rt="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  sock=$(ls "$rt"/wayland-*.lock 2>/dev/null | head -1)
  if [ -z "$sock" ]; then
    echo "no live Wayland compositor socket found under $rt (is pineda-kiosk.service running?)" >&2
    exit 1
  fi
  wd=$(basename "$sock" .lock)
  XDG_RUNTIME_DIR="$rt" WAYLAND_DISPLAY="$wd" grim -t png -
' > "$out"

echo "wrote $out" >&2
