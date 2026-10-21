# SPDX-License-Identifier: Apache-2.0
"""The card registry: every known manifest, its resolved status, and the set of
stores that ready cards publish."""

from __future__ import annotations

from pathlib import Path

from pinedaview.cards.loader import load_manifests
from pinedaview.cards.manifest import CardManifest
from pinedaview.cards.needs import CardStatus, NeedsEnv, resolve_status
from pinedaview.config import Settings
from pinedaview.secrets import SecretStore


class CardRegistry:
    def __init__(self, manifests: dict[str, CardManifest]) -> None:
        self._manifests = manifests
        self._statuses: dict[str, CardStatus] = {card_id: CardStatus.ok() for card_id in manifests}

    @classmethod
    def load(cls, user_dir: Path | None = None, disabled: set[str] | None = None) -> CardRegistry:
        return cls(load_manifests(user_dir, disabled))

    def manifest(self, card_id: str) -> CardManifest | None:
        return self._manifests.get(card_id)

    def all(self) -> list[CardManifest]:
        return [self._manifests[cid] for cid in sorted(self._manifests)]

    def status(self, card_id: str) -> CardStatus:
        return self._statuses.get(card_id, CardStatus.blocked("unknown card"))

    def ready_ids(self) -> list[str]:
        return sorted(cid for cid, status in self._statuses.items() if status.ready)

    def provided_stores(self) -> frozenset[str]:
        return frozenset(
            store for cid in self.ready_ids() for store in self._manifests[cid].provides
        )

    def resolve(
        self,
        *,
        settings: Settings,
        secrets: SecretStore,
        mqtt_connected: bool = False,
        has_photos: bool = False,
    ) -> None:
        """Fixpoint over ``provider:<store>`` needs — a card is ready only once
        every store it depends on is published by another ready card."""
        provided: set[str] = set()
        statuses: dict[str, CardStatus] = {}
        for _ in range(len(self._manifests) + 1):
            env = NeedsEnv(
                settings=settings,
                secrets=secrets,
                provided_stores=frozenset(provided),
                mqtt_connected=mqtt_connected,
                has_photos=has_photos,
            )
            statuses = {
                cid: resolve_status(manifest, env) for cid, manifest in self._manifests.items()
            }
            next_provided = {
                store
                for cid, manifest in self._manifests.items()
                if statuses[cid].ready
                for store in manifest.provides
            }
            if next_provided == provided:
                break
            provided = next_provided
        self._statuses = statuses
