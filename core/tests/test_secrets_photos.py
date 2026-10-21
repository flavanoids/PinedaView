# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import io
import json
import shutil
import struct
import subprocess
import zlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pinedaview.photos import DuplicatePhotoError, PhotoStore, TooLongError
from pinedaview.secrets import SecretStore


def _png(colour: tuple[int, int, int] = (200, 120, 60)) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    row = bytes([0, *colour, *colour])
    idat = zlib.compress(row * 2)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# ── secrets ──────────────────────────────────────────────────────────────────


def test_secret_set_get_delete(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    assert store.has("x") is False
    store.set("x", "abc")
    assert store.get("x") == "abc"
    assert store.names() == ["x"]
    assert store.delete("x") is True
    assert store.delete("x") is False


def test_secret_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SecretStore(tmp_path)
    store.set("api_key", "from-file")
    monkeypatch.setenv("PINEDA_SECRET_API_KEY", "from-env")
    assert store.get("api_key") == "from-env"
    assert "api_key" in store.names()


# ── photos ───────────────────────────────────────────────────────────────────


def test_photo_add_list_thumb_delete(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    assert store.count() == 0

    photo = store.add("beach.png", _png())
    assert photo.name == "beach.png"
    assert store.count() == 1
    assert store.original_path("beach.png").is_file()
    assert store.thumb_path("beach.png").is_file()

    assert store.delete("beach.png") is True
    assert store.count() == 0
    assert store.delete("beach.png") is False


def test_photo_rejects_non_image_and_bad_extension(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    with pytest.raises(ValueError, match="unrecognised"):
        store.add("x.png", b"not an image")
    with pytest.raises(ValueError, match="extension"):
        store.add("x.txt", b"\0\0\0\x18ftypheic" + b"\0" * 32)


def test_photo_rejects_tiff_header_that_is_not_a_raw(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    with pytest.raises(ValueError, match="unrecognised"):
        store.add("IMG_1.dng", b"MM\x00*\x00\x00\x00\x12APPLEDNG" + b"\x00" * 64)


def test_photo_named_by_content_when_extension_is_wrong(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    photo = store.add("IMG_0001.HEIC.txt", _png())
    assert photo.name == "IMG_0001.HEIC.png"
    assert photo.original_filename == "IMG_0001.HEIC.txt"
    assert store.add("noext", _png((10, 20, 30))).name == "noext.png"


def test_photo_dedupes_by_content(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    store.add("a.png", _png())
    with pytest.raises(DuplicatePhotoError):
        store.add("b.png", _png())


def test_photo_rotate_updates_metadata(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    store.add("a.png", _png())
    rotated = store.rotate("a.png", 90)
    assert rotated.rotation == 90
    with pytest.raises(KeyError):
        store.rotate("missing.png", 90)


def _jpeg(size: tuple[int, int]) -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (90, 140, 200)).save(buffer, "JPEG")
    return buffer.getvalue()


def test_photo_display_copy_for_large_jpeg(tmp_path: Path) -> None:
    from PIL import Image

    store = PhotoStore(tmp_path / "photos")
    store.add("big.jpg", _jpeg((4032, 3024)))
    copy = store.display_copy_path("big.jpg")
    assert copy.is_file()
    assert store.display_path("big.jpg") == copy
    with Image.open(copy) as image:
        assert max(image.size) == 1920
        assert image.size[0] > image.size[1]  # aspect kept

    store.delete("big.jpg")
    assert not copy.exists()


def test_photo_small_jpeg_serves_the_original(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    store.add("small.jpg", _jpeg((1200, 900)))
    assert not store.display_copy_path("small.jpg").exists()
    assert store.display_path("small.jpg") == store.original_path("small.jpg")


def test_photo_non_jpeg_always_gets_a_copy(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    store.add("tiny.png", _png())
    assert store.display_path("tiny.png") == store.display_copy_path("tiny.png")


def test_photo_backfill_makes_missing_copies_once(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    store.add("big.jpg", _jpeg((3000, 2000)))
    store.display_copy_path("big.jpg").unlink()  # as if added before copies existed
    assert store.backfill_display() == 1
    assert store.display_copy_path("big.jpg").is_file()
    assert store.backfill_display() == 0


def test_photo_subject_path_and_cleanup(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    store.add("sample.jpg", _jpeg((100, 100)))
    subject = store.subject_path("sample.jpg")
    assert not subject.is_file()
    assert store.all()[0].has_subject is False
    subject.write_bytes(b"mock webp data")
    assert store.all()[0].has_subject is True
    assert store.delete("sample.jpg") is True
    assert not subject.exists()


def test_photo_delete_purges_all_versions_and_derivatives(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    photo = store.add("vacation.png", _png())
    name = photo.name
    stem = Path(name).stem

    orig = store.original_path(name)
    thumb = store.thumb_path(name)
    display = store.display_copy_path(name)
    subject = store.subject_path(name)
    subject.write_bytes(b"cutout")
    motion = store.motion_path(name)
    motion.parent.mkdir(parents=True, exist_ok=True)
    motion.write_bytes(b"motion video clip")

    stem_thumb = store._thumbs / f"thumb_{stem}.jpg"
    stem_thumb.write_bytes(b"stem thumb")
    stem_display = store._thumbs / f"display_{stem}.jpg"
    stem_display.write_bytes(b"stem display")
    stem_motion = store._root / "motion" / f"{stem}.mp4"
    stem_motion.write_bytes(b"stem motion")

    assert orig.is_file()
    assert thumb.is_file()
    assert display.is_file()
    assert subject.is_file()
    assert motion.is_file()
    assert stem_thumb.is_file()
    assert stem_display.is_file()
    assert stem_motion.is_file()

    assert store.delete(name) is True

    assert not orig.exists()
    assert not thumb.exists()
    assert not display.exists()
    assert not subject.exists()
    assert not motion.exists()
    assert not stem_thumb.exists()
    assert not stem_display.exists()
    assert not stem_motion.exists()
    assert store.count() == 0
    assert store.delete("nonexistent.jpg") is False


def _clip(tmp_path: Path, seconds: float) -> bytes:
    out = tmp_path / f"clip{seconds}.mov"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=160x120:rate=30:duration={seconds}",
            "-c:v",
            "libx264",
            "-movflags",
            "use_metadata_tags",
            "-metadata",
            "com.apple.quicktime.creationdate=2026-10-12T09:15:22-0500",
            str(out),
        ],
        check=True,
    )
    return out.read_bytes()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_photo_from_a_live_photo_clip(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    photo = store.add("IMG_7.MOV", _clip(tmp_path, 3))
    assert photo.name == "IMG_7.jpeg"
    assert photo.motion and store.all()[0].motion
    assert photo.taken_at == datetime(2026, 10, 12, 9, 15, 22, tzinfo=UTC).timestamp()
    assert store.motion_path(photo.name).read_bytes()[4:8] == b"ftyp"
    with pytest.raises(TooLongError):
        store.add("long.mov", _clip(tmp_path, 11))
    store.delete(photo.name)
    assert not store.motion_path(photo.name).exists()


def _solid(colour: tuple[int, int, int]) -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (64, 48), colour).save(out, "JPEG")
    return out.getvalue()


def test_photo_colours_and_tint(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "photos")
    red = store.add("red.jpg", _solid((200, 40, 40)))
    assert red.colours and red.tint and red.tint.startswith("#f7")
    grey = store.add("grey.jpg", _solid((128, 128, 128)))
    assert grey.tint is None
    # Photos from before colours were kept get them from the backfill.
    meta = json.loads((tmp_path / "photos/.cache/metadata.json").read_text())
    del meta["red.jpg"]["tint"], meta["red.jpg"]["colours"]
    (tmp_path / "photos/.cache/metadata.json").write_text(json.dumps(meta))
    assert store.backfill_colours() == 1
    assert store.all()[0].tint == red.tint
