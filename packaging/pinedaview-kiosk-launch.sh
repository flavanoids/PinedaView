#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Runs inside cage, ahead of Chromium: turns the screen to its saved
# direction (written by pinedaview-control-wrapper.sh's pinedaview-rotate), then
# starts the browser with the arguments it was given. cage resets the
# output to "normal" every time it starts, so this is what makes a turn
# stick through kiosk restarts and reboots.
#
#   sudo install -m 755 packaging/pinedaview-kiosk-launch.sh \
#     /usr/local/bin/pinedaview-kiosk-launch
#
# and in pinedaview-kiosk.service:
#
#   ExecStart=/usr/bin/cage -- /usr/local/bin/pinedaview-kiosk-launch \
#     /usr/lib/chromium/chromium --kiosk ...
rot_file="$HOME/.config/pinedaview/rotation"
[ -f "$rot_file" ] || rot_file="$HOME/.config/pineda/rotation"
turn=$(cat "$rot_file" 2>/dev/null || echo "")
case "$turn" in
  90 | 180 | 270)
    # The output can take a moment to show up after cage starts.
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      out=$(wlr-randr 2>/dev/null | awk 'NR == 1 { print $1 }')
      [ -n "$out" ] && wlr-randr --output "$out" --transform "$turn" && break
      sleep 0.2
    done
    ;;
esac
exec "$@"
