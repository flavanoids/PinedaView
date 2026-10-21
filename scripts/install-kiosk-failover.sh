#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Turn a split-host kiosk into a primary/standby one: nginx on the kiosk proxies
# 127.0.0.1:8090 to whichever pineda-web is live, pineda-failover.sh picks it,
# and the kiosk's Chromium loads the local proxy with its device id pinned.
#
# Run from a checkout on the server host:
#   scripts/install-kiosk-failover.sh kiosk@kiosk.local 3f862842aee4086a
# Undo: sudo rm /etc/systemd/system/pineda-kiosk.service.d/failover.conf,
#       sudo systemctl disable --now pineda-failover nginx, daemon-reload,
#       restart pineda-kiosk.
set -eu

target="${1:?usage: $0 user@kiosk-host device-id}"
device="${2:?usage: $0 user@kiosk-host device-id}"
primary="${PINEDA_PRIMARY:-192.0.2.171:8090}"
standby="${PINEDA_STANDBY:-192.0.2.16:8090}"
url="http://127.0.0.1:8090/?clock=contour&pi=1&device=$device"

here="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
scp -q "$here/packaging/pineda-failover.sh" "$here/packaging/pineda-failover.service" \
    "$here/packaging/pineda-failover.nginx.conf" "$target:/tmp/"

# Quoted for the remote shell: the URL's &s would background the command there.
ssh "$target" "sh -s '$primary' '$standby' '$url'" <<'REMOTE'
set -eu
primary="$1" standby="$2" url="$3"
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q nginx-light >/dev/null 2>&1 \
  || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q nginx >/dev/null
sudo install -m 755 /tmp/pineda-failover.sh /usr/local/bin/
sed -e "s|^Environment=PINEDA_PRIMARY=.*|Environment=PINEDA_PRIMARY=$primary|" \
    -e "s|^Environment=PINEDA_STANDBY=.*|Environment=PINEDA_STANDBY=$standby|" \
    /tmp/pineda-failover.service | sudo tee /etc/systemd/system/pineda-failover.service >/dev/null
sudo install -m 644 /tmp/pineda-failover.nginx.conf /etc/nginx/sites-available/pineda
sudo ln -sf ../sites-available/pineda /etc/nginx/sites-enabled/pineda
sudo rm -f /etc/nginx/sites-enabled/default
grep -q worker_shutdown_timeout /etc/nginx/nginx.conf \
  || sudo sed -i '/^pid /a worker_shutdown_timeout 3s;' /etc/nginx/nginx.conf
sudo sed -i 's/^worker_processes .*/worker_processes 1;/' /etc/nginx/nginx.conf
[ -f /etc/nginx/pineda-upstream.conf ] \
  || printf 'server %s;\nserver %s backup;\n' "$primary" "$standby" | sudo tee /etc/nginx/pineda-upstream.conf >/dev/null
sudo nginx -t
sudo systemctl enable -q nginx && sudo systemctl restart nginx

# Kiosk: load the local proxy, wait for it rather than for one server.
sudo mkdir -p /etc/systemd/system/pineda-kiosk.service.d
cur="$(systemctl show -p ExecStart --value pineda-kiosk.service | sed -n 's/.*argv\[\]=\([^;]*\);.*/\1/p' | sed 's/ *$//')"
url_sed="$(printf '%s' "$url" | sed 's/[&|\\]/\\&/g')"   # & and | are special to sed
new="$(printf '%s\n' "$cur" | sed "s|http://[^ ]*\$|$url_sed|")"
case "$new" in *"$url") ;; *) echo "couldn't rewrite the kiosk URL in: $cur" >&2; exit 1 ;; esac
sudo tee /etc/systemd/system/pineda-kiosk.service.d/failover.conf >/dev/null <<EOF
# Installed by PinedaDisplay_web scripts/install-kiosk-failover.sh
[Unit]
After=nginx.service pineda-failover.service
Wants=nginx.service pineda-failover.service
[Service]
ExecStartPre=
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 60); do curl -sf http://127.0.0.1:8090/api/health >/dev/null && exit 0; sleep 1; done; exit 1'
ExecStart=
ExecStart=$new
EOF
sudo systemctl daemon-reload
sudo systemctl enable -q --now pineda-failover
sleep 3
sudo systemctl restart pineda-kiosk
journalctl -u pineda-failover -n 2 --no-pager
REMOTE
