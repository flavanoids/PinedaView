#!/usr/bin/env sh
# SPDX-License-Identifier: Apache-2.0
#
# Build the web client and drop it where the Python package expects it, so a
# wheel / Docker image / .deb bundles the whole app. Run from the repo root.
set -eu

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$root"

echo "› building web client"
pnpm install --frozen-lockfile
pnpm --filter @pinedaview/client build

dest="core/src/pinedaview/webroot"
echo "› staging $dest"
rm -rf "$dest"
cp -r web/dist "$dest"
echo "✓ web client staged ($(find "$dest" -type f | wc -l | tr -d ' ') files)"
