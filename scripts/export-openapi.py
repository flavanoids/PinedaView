# SPDX-License-Identifier: Apache-2.0
"""Emit the API's OpenAPI schema to packages/protocol/openapi.json.

Run from the repo root:  uv run --project core python scripts/export-openapi.py
Pass --check to fail (non-zero) when the committed file is stale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pinedaview.api import create_app

_OUT = Path(__file__).resolve().parent.parent / "packages" / "protocol" / "openapi.json"


def render() -> str:
    spec = create_app().openapi()
    return json.dumps(spec, indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        current = _OUT.read_text() if _OUT.exists() else ""
        if current != text:
            print("packages/protocol/openapi.json is stale — regenerate it", file=sys.stderr)
            return 1
        print("openapi.json is up to date")
        return 0
    _OUT.write_text(text)
    print(f"wrote {_OUT.relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
