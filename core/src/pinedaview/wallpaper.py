# SPDX-License-Identifier: Apache-2.0
"""The single background image for the Liquid Glass theme.

One file on disk (``wallpaper``) plus a sidecar holding its content type. The
Liquid Glass surface (``tokens.css``) layers it over the built-in dawn
gradient, which stays as the fallback when nothing is set.
"""

from __future__ import annotations

from pathlib import Path

MAX_BYTES = 16 * 1024 * 1024


def _sniff(data: bytes) -> str | None:
    head = data[:12]
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


class WallpaperStore:
    def __init__(self, root: Path) -> None:
        self._file = root / "wallpaper"
        self._type = root / "wallpaper.type"

    def has(self) -> bool:
        return self._file.is_file()

    def path(self) -> Path | None:
        return self._file if self._file.is_file() else None

    def content_type(self) -> str:
        try:
            return self._type.read_text().strip() or "image/jpeg"
        except OSError:
            return "image/jpeg"

    def revision(self) -> int:
        """The file mtime — a cheap cache-buster the client pins its URL to."""
        try:
            return int(self._file.stat().st_mtime)
        except OSError:
            return 0

    def set(self, data: bytes) -> str:
        if len(data) > MAX_BYTES:
            raise ValueError("image is larger than 16 MB")
        content_type = _sniff(data)
        if content_type is None:
            raise ValueError("not a JPEG, PNG or WebP image")
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_bytes(data)
        self._type.write_text(content_type)
        return content_type

    def clear(self) -> bool:
        if not self._file.is_file():
            return False
        self._file.unlink(missing_ok=True)
        self._type.unlink(missing_ok=True)
        return True
