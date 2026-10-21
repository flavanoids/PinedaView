# SPDX-License-Identifier: Apache-2.0
"""Discover and validate ``card.json`` manifests.

Built-in manifests ship inside the package. A user ``cards/`` directory is
additive and may override a built-in by id. ``disabled_cards`` in config removes
one. An invalid manifest is logged and skipped — never fatal.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from pinedaview.cards.manifest import CardManifest

logger = logging.getLogger(__name__)

_BUILTIN_DIR = Path(__file__).parent / "builtin"


def _iter_manifest_files(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        manifest = child / "card.json"
        if manifest.is_file():
            yield manifest


def _load_one(path: Path) -> CardManifest | None:
    try:
        raw = json.loads(path.read_text())
        return CardManifest.model_validate(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("card manifest unreadable: %s (%s)", path, exc)
    except ValidationError as exc:
        logger.error("card manifest invalid: %s\n%s", path, exc)
    return None


def load_manifests(
    user_dir: Path | None = None,
    disabled: set[str] | None = None,
) -> dict[str, CardManifest]:
    disabled = disabled or set()
    manifests: dict[str, CardManifest] = {}

    sources = [_BUILTIN_DIR]
    if user_dir is not None:
        sources.append(user_dir)

    for source in sources:
        for path in _iter_manifest_files(source):
            manifest = _load_one(path)
            if manifest is None:
                continue
            if manifest.id in manifests:
                logger.info("card %s overridden by %s", manifest.id, path)
            manifests[manifest.id] = manifest

    for card_id in disabled:
        manifests.pop(card_id, None)

    logger.info("loaded %d cards: %s", len(manifests), ", ".join(sorted(manifests)))
    return manifests
