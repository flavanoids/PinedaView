#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -e

if ! getent passwd pineda >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/pinedaview --shell /usr/sbin/nologin \
        --comment "PinedaView" pineda || \
    adduser --system --home /var/lib/pinedaview --no-create-home pineda || true
fi

mkdir -p /var/lib/pinedaview/photos /var/lib/pinedaview/cards /var/lib/pinedaview/diagnostics
chown -R pineda:pineda /var/lib/pinedaview
chmod 750 /var/lib/pinedaview

# Provide backward-compatibility symlink if /var/lib/pineda-web doesn't exist
if [ ! -e /var/lib/pineda-web ]; then
    ln -s /var/lib/pinedaview /var/lib/pineda-web 2>/dev/null || true
fi

# Lets the "Restart display" / "Restart Raspberry Pi" menu buttons work: the
# pineda user runs NoNewPrivileges=true, so it can only reach systemctl/reboot
# via this polkit rule, never sudo. Harmless on setups without a kiosk unit —
# the rule matches pinedaview-kiosk.service, pineda-kiosk.service, and reboot.
if [ -d /etc/polkit-1/rules.d ]; then
    rules_src="/opt/pinedaview/pinedaview-restart.rules"
    [ -f "$rules_src" ] || rules_src="/opt/pineda-web/pineda-restart.rules"
    if [ -f "$rules_src" ]; then
        install -m 644 "$rules_src" /etc/polkit-1/rules.d/49-pinedaview.rules 2>/dev/null || true
        systemctl try-restart polkit 2>/dev/null || true
    fi
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
    systemctl enable pinedaview.service 2>/dev/null || systemctl enable pineda-web.service || true
    # LAN only: the guard keeps :8090 off the internet and away from tunnels
    systemctl enable --now pinedaview-guard.service 2>/dev/null || systemctl enable --now pineda-web-guard.service || true
    # Automated updates timer
    systemctl enable --now pinedaview-update.timer 2>/dev/null || true
    echo "PinedaView installed. Start it with:  sudo systemctl start pinedaview"
    echo "Then open http://<this-host>:8090 to run the setup wizard."
fi
