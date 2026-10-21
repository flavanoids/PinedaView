#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Build a self-contained venv and produce a .deb + .rpm with nfpm.
# Run on the target arch (or under qemu). Needs: python3, nfpm.
#
#   VERSION=0.9.0 scripts/build-package.sh
set -euo pipefail

root="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$root"

VERSION="${VERSION:-$(grep -m1 '^version' core/pyproject.toml | cut -d'"' -f2)}"
case "$(uname -m)" in
  x86_64)  ARCH=amd64 ;;
  aarch64) ARCH=arm64 ;;
  *)       ARCH="$(uname -m)" ;;
esac
export VERSION ARCH

echo "› pineda-web $VERSION ($ARCH)"
"$root/scripts/stage-web.sh"

venv=/opt/pineda-web/venv
echo "› building venv at $venv"
sudo rm -rf "$venv"
sudo python3 -m venv "$venv"
sudo "$venv/bin/pip" install --upgrade pip wheel
sudo "$venv/bin/pip" install "./core"

mkdir -p dist
nfpm pkg -f packaging/nfpm.yaml -p deb -t "dist/pineda-web_${VERSION}_${ARCH}.deb"
nfpm pkg -f packaging/nfpm.yaml -p rpm -t "dist/pineda-web-${VERSION}.${ARCH}.rpm"
echo "✓ dist/"
ls -la dist/
