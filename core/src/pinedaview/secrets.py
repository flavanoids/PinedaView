# SPDX-License-Identifier: Apache-2.0
"""Server-only secret storage, encrypted at rest.

Values are Fernet-encrypted with a machine-local key auto-generated under the
state directory (``chmod 600``). They never appear in an API response or a view
model — only the *names* are ever exposed. Env vars ``PINEDA_SECRET_<NAME>``
override the file and are never written.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_FILENAME = "secrets.enc"
_KEYFILE = "secrets.key"
_ENV_PREFIX = "PINEDA_SECRET_"


class SecretStore:
    def __init__(self, state_dir: Path) -> None:
        self._path = state_dir / _FILENAME
        self._keypath = state_dir / _KEYFILE

    def _fernet(self) -> Fernet:
        try:
            key = self._keypath.read_bytes()
        except OSError:
            key = Fernet.generate_key()
            self._keypath.parent.mkdir(parents=True, exist_ok=True)
            self._keypath.write_bytes(key)
            self._keypath.chmod(0o600)
        return Fernet(key)

    def _load(self) -> dict[str, str]:
        try:
            blob = self._path.read_bytes()
        except OSError:
            return {}
        try:
            data: object = json.loads(self._fernet().decrypt(blob))
        except (InvalidToken, json.JSONDecodeError) as exc:
            logger.error("secrets file unreadable (%s) — treating as empty", exc)
            return {}
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def get(self, name: str) -> str | None:
        env = os.environ.get(f"{_ENV_PREFIX}{name.upper()}")
        if env:
            return env
        return self._load().get(name)

    def has(self, name: str) -> bool:
        return self.get(name) is not None

    def names(self) -> list[str]:
        env_names = [
            key[len(_ENV_PREFIX) :].lower() for key in os.environ if key.startswith(_ENV_PREFIX)
        ]
        return sorted(set(self._load()) | set(env_names))

    def set(self, name: str, value: str) -> None:
        current = self._load()
        current[name] = value
        self._write(current)

    def delete(self, name: str) -> bool:
        current = self._load()
        if current.pop(name, None) is None:
            return False
        self._write(current)
        return True

    def _write(self, data: dict[str, str]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_bytes(self._fernet().encrypt(json.dumps(data).encode()))
            self._path.chmod(0o600)
        except OSError as exc:
            logger.error("could not persist secrets: %s", exc)
