#!/usr/bin/env sh
# SPDX-License-Identifier: Apache-2.0
#
# One-liner installer:
#   curl -sSL https://raw.githubusercontent.com/flavanoids/PinedaView/main/scripts/install.sh | sh
#
# Downloads the latest .deb / .rpm for this machine's architecture from the
# GitHub Releases page and installs it. Falls back to printing the pipx command.
set -eu

REPO="flavanoids/PinedaView"
API="https://api.github.com/repos/$REPO/releases/latest"

arch="$(uname -m)"
case "$arch" in
  x86_64)  deb_arch=amd64; rpm_arch=x86_64 ;;
  aarch64) deb_arch=arm64; rpm_arch=aarch64 ;;
  *) echo "unsupported arch: $arch — try: pipx install pinedaview"; exit 1 ;;
esac

tag="$(curl -sSL "$API" 2>/dev/null | grep -m1 '"tag_name"' | cut -d'"' -f4 || echo "")"
[ -n "$tag" ] || { echo "could not find a release; see https://github.com/$REPO for install instructions"; exit 1; }
ver="${tag#v}"
base="https://github.com/$REPO/releases/download/$tag"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if command -v apt-get >/dev/null 2>&1 || command -v dpkg >/dev/null 2>&1; then
  f="pinedaview_${ver}_${deb_arch}.deb"
  if ! curl -sf -I "$base/$f" >/dev/null 2>&1; then
    f="pineda-web_${ver}_${deb_arch}.deb"
  fi
  echo "Downloading $f..."
  curl -sSL -o "$tmp/$f" "$base/$f"
  sudo apt-get install -y "$tmp/$f" 2>/dev/null || sudo dpkg -i "$tmp/$f"
elif command -v dnf >/dev/null 2>&1 || command -v rpm >/dev/null 2>&1; then
  f="pinedaview-${ver}.${rpm_arch}.rpm"
  if ! curl -sf -I "$base/$f" >/dev/null 2>&1; then
    f="pineda-web-${ver}.${rpm_arch}.rpm"
  fi
  echo "Downloading $f..."
  curl -sSL -o "$tmp/$f" "$base/$f"
  sudo dnf install -y "$tmp/$f" 2>/dev/null || sudo rpm -i "$tmp/$f"
else
  echo "No apt or dnf package manager found. Install with pipx instead:"
  echo "    pipx install pinedaview"
  exit 1
fi

echo
echo "Installed PinedaView $ver successfully."
echo "Start the service with:"
echo "    sudo systemctl start pinedaview"
echo "Then open in your browser:"
echo "    http://<device-ip>:8090"
