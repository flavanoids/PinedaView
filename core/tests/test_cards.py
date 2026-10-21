# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pinedaview.cards.duration import parse_duration
from pinedaview.cards.loader import load_manifests
from pinedaview.cards.manifest import CardManifest
from pinedaview.cards.needs import NeedsEnv, resolve_status
from pinedaview.cards.providers import build_providers
from pinedaview.cards.registry import CardRegistry
from pinedaview.config import Settings
from pinedaview.secrets import SecretStore


def _write_card(root: Path, card_id: str, body: dict[str, object]) -> None:
    folder = root / card_id
    folder.mkdir(parents=True)
    (folder / "card.json").write_text(json.dumps({"id": card_id, "name": card_id.title(), **body}))


# ── duration ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "seconds"), [("90s", 90), ("15m", 900), ("1h", 3600), ("2d", 172800)]
)
def test_parse_duration(text: str, seconds: float) -> None:
    assert parse_duration(text) == seconds


def test_parse_duration_rejects_junk() -> None:
    with pytest.raises(ValueError, match="not a duration"):
        parse_duration("soon")


# ── manifest ─────────────────────────────────────────────────────────────────


def test_manifest_rejects_bad_id() -> None:
    with pytest.raises(ValidationError):
        CardManifest.model_validate({"id": "Not Valid", "name": "x"})


def test_manifest_rejects_unknown_need() -> None:
    with pytest.raises(ValidationError):
        CardManifest.model_validate({"id": "x", "name": "x", "needs": ["moon-dust"]})


def test_manifest_reads_fetch_hosts_alias_and_refresh() -> None:
    manifest = CardManifest.model_validate(
        {
            "id": "x",
            "name": "X",
            "permissions": {"fetchHosts": ["example.com"]},
            "refresh": {"interval": "5m"},
        }
    )
    assert manifest.permissions.fetch_hosts == ["example.com"]
    assert manifest.refresh.interval_s == 300


# ── loader ───────────────────────────────────────────────────────────────────


def test_loader_includes_builtins() -> None:
    manifests = load_manifests()
    assert {"clock", "weather", "moon", "affirmation", "commute"} <= set(manifests)


def test_loader_user_dir_adds_and_overrides(tmp_path: Path) -> None:
    _write_card(tmp_path, "hello", {})
    _write_card(tmp_path, "clock", {"description": "my clock"})
    manifests = load_manifests(tmp_path)
    assert "hello" in manifests
    assert manifests["clock"].description == "my clock"


def test_loader_disabled_removes(tmp_path: Path) -> None:
    manifests = load_manifests(tmp_path, disabled={"weather"})
    assert "weather" not in manifests


def test_loader_skips_invalid_manifest(tmp_path: Path) -> None:
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "card.json").write_text("{ not json")
    manifests = load_manifests(tmp_path)
    assert "broken" not in manifests


# ── needs + registry ─────────────────────────────────────────────────────────


def test_needs_location_blocks_without_a_place(tmp_path: Path) -> None:
    manifest = CardManifest.model_validate({"id": "x", "name": "X", "needs": ["location"]})
    env = NeedsEnv(
        settings=Settings(location={"query": ""}),
        secrets=SecretStore(tmp_path),
        provided_stores=frozenset(),
    )
    assert resolve_status(manifest, env).ready is False
    assert "location" in (resolve_status(manifest, env).reason or "")


def test_needs_secret(tmp_path: Path) -> None:
    manifest = CardManifest.model_validate(
        {"id": "x", "name": "X", "needs": ["secret:google_maps"]}
    )
    secrets = SecretStore(tmp_path)
    env = NeedsEnv(settings=Settings(), secrets=secrets, provided_stores=frozenset())
    assert resolve_status(manifest, env).ready is False
    secrets.set("google_maps", "key-123")
    assert resolve_status(manifest, env).ready is True


def test_registry_fixpoint_resolves_provider_chains(tmp_path: Path) -> None:
    registry = CardRegistry.load()
    registry.resolve(settings=Settings(), secrets=SecretStore(tmp_path))
    ready = set(registry.ready_ids())
    # weather → provider:weather chain feeds air-quality and forecast
    assert {"clock", "weather", "moon", "affirmation", "phrase", "forecast"} <= ready
    # commute needs a maps key it doesn't have
    assert "commute" not in ready
    assert "dailyContent" in registry.provided_stores()


def test_build_providers_only_for_ready_cards(tmp_path: Path) -> None:
    registry = CardRegistry.load()
    registry.resolve(settings=Settings(), secrets=SecretStore(tmp_path))
    keys = {p.key for p in build_providers(registry)}
    assert {"weather", "moon", "dailyContent"} <= keys
    assert "commute" not in keys  # blocked → not built
