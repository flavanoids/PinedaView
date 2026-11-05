# SPDX-License-Identifier: Apache-2.0
"""Photo storage for the photo-frame card.

A directory of originals, a ``.cache/`` of thumbnails and display copies, and
a ``metadata.json``. Rotation is stored as metadata; the original file is
never rewritten.

The display copy is what the slideshow shows: EXIF-upright, no longer than
``_DISPLAY_EDGE`` on its long side, rotation *not* baked in (the card applies
it). A kiosk decoding a 12 MP original every swap was nearly all of its CPU;
the copy is made once, when a photo is added (or by ``backfill_display`` for
a library that predates it), never on request. Sync
methods — the API layer calls them through ``asyncio.to_thread``.
"""

from __future__ import annotations

import colorsys
import gc
import hashlib
import io
import json
import logging
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from PIL import ExifTags, Image, ImageOps
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_ACCEPTED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
_THUMB_WIDTH = 480
# Covers a 2x2 hero cell on a retina tablet; ~4x fewer pixels than a 12 MP
# camera original.
_DISPLAY_EDGE = 1920
#: The width of a cutout's mask: the Photo Clock only reads where the
#: subject is on a coarse grid, so it needn't decode the whole cutout.
_MASK_WIDTH = 96
_MAGIC = (
    b"\xff\xd8\xff",  # jpeg
    b"\x89PNG\r\n\x1a\n",  # png
)


# A Live Photo saved as a video (or any short clip): its middle frame is the
# photo, and the clip plays over it. iPhone clips are HEVC, often HDR; the
# kiosk gets small SDR H.264, which the Pi decodes in hardware.
_VIDEO_BRANDS = {b"qt  ", b"isom", b"iso2", b"iso4", b"mp41", b"mp42", b"avc1", b"M4V "}
MAX_MOTION_S = 10.0
_MOTION_EDGE = 1280
_HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}
_TONEMAP = (
    "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,"
)


class DuplicatePhotoError(ValueError):
    def __init__(self, existing: str) -> None:
        super().__init__(f"already uploaded as {existing}")
        self.existing = existing


class TooLongError(ValueError):
    def __init__(self, seconds: float) -> None:
        super().__init__(f"{seconds:.0f} s clip; {MAX_MOTION_S:.0f} s at most")


class Photo(BaseModel):
    name: str
    uploaded_at: float
    rotation: int = 0
    original_filename: str = ""
    sort: int = 0
    taken_at: float | None = None
    """When the camera says the shot was taken (EXIF DateTimeOriginal), not
    when it landed on this server — the "on this day" card matches against
    this. None when the file has no usable EXIF (screenshots, edited/
    re-saved images, most PNGs)."""
    pending: bool = False
    """A guest's upload waiting for approval in Settings; kept out of the
    slideshow (and everything else that reads :meth:`PhotoStore.all`)."""
    has_subject: bool = False
    """A transparent cutout of the photo's subject exists, so the Photo
    Clock can tuck the time behind it. Read from disk, never stored."""
    colours: list[str] = []
    """Up to five dominant colours (#rrggbb), biggest share first."""
    tint: str | None = None
    """A light, vivid colour from the photo for the Photo Clock's "from the
    photo" glass tint; None for black-and-white or washed-out photos."""
    motion: bool = False
    """A short clip (a Live Photo saved as a video) plays over the photo,
    which is its middle frame. Read from disk, never stored."""
    aspect: float | None = None
    """Width over height as the photo is seen (upright by its EXIF
    orientation, before ``rotation``), so a tall screen can lean towards
    tall photos. None until read."""


def _looks_like_image(data: bytes) -> bool:
    head = data[:16]
    if any(head.startswith(sig) for sig in _MAGIC):
        return True
    return (head[:4] == b"RIFF" and head[8:12] == b"WEBP") or head[4:12].startswith(b"ftyp")


_EXT_FOR_FORMAT = {"JPEG": ".jpeg", "MPO": ".jpeg", "PNG": ".png", "WEBP": ".webp"}


def _sniffed_ext(data: bytes) -> str | None:
    """The extension the bytes deserve, for phones that send a JPEG named
    .HEIC (or with no extension at all)."""
    try:
        with Image.open(io.BytesIO(data)) as opened:
            return _EXT_FOR_FORMAT.get(opened.format or "")
    except (OSError, ValueError, SyntaxError):
        return None


def _from_raw(data: bytes) -> bytes | None:
    """A JPEG of a camera raw (iPhone ProRAW .dng): the full-size preview
    the camera embedded, else a half-size render. None if it isn't a raw."""
    if data[:4] not in (b"MM\x00*", b"II*\x00"):
        return None
    import rawpy

    try:
        with rawpy.imread(io.BytesIO(data)) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:  # type: ignore[attr-defined]
                    with Image.open(io.BytesIO(bytes(thumb.data))) as preview:
                        if max(preview.size) >= _DISPLAY_EDGE:
                            return bytes(thumb.data)
            except (rawpy.LibRawError, OSError):  # type: ignore[attr-defined]
                pass
            pixels = raw.postprocess(use_camera_wb=True, half_size=True, output_bps=8)
    except (rawpy.LibRawError, OSError, ValueError):  # type: ignore[attr-defined]
        return None
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def _is_video(data: bytes) -> bool:
    return data[4:8] == b"ftyp" and data[8:12] in _VIDEO_BRANDS


def _probe(path: Path) -> tuple[float, float | None, bool]:
    """A clip's length in seconds, when it was shot (camera-local wall time
    read as UTC, like EXIF), and whether it's HDR."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=duration:format_tags:stream=color_transfer",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    info = json.loads(out.stdout)
    fmt = info.get("format", {})
    tags = {k.lower(): v for k, v in fmt.get("tags", {}).items()}
    taken = None
    for key in ("com.apple.quicktime.creationdate", "creation_time"):
        try:
            taken = datetime.strptime(tags[key][:19], "%Y-%m-%dT%H:%M:%S")
        except (KeyError, ValueError):
            continue
        break
    streams = info.get("streams") or [{}]
    return (
        float(fmt.get("duration") or 0),
        taken.replace(tzinfo=UTC).timestamp() if taken else None,
        streams[0].get("color_transfer") in _HDR_TRANSFERS,
    )


def _from_video(data: bytes, motion: Path) -> tuple[bytes, float | None]:
    """The clip's middle frame as a JPEG and when it was shot; the clip
    itself, small and silent, written to `motion`."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in"
        src.write_bytes(data)
        try:
            seconds, taken, hdr = _probe(src)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise ValueError("unreadable video") from exc
        if seconds > MAX_MOTION_S:
            raise TooLongError(seconds)
        tone = _TONEMAP if hdr else ""
        still = Path(tmp) / "still.jpg"
        clip = Path(tmp) / "motion.mp4"
        run = ["ffmpeg", "-v", "error", "-y"]
        try:
            subprocess.run(
                [
                    *run,
                    "-ss",
                    f"{seconds / 2:.3f}",
                    "-i",
                    str(src),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"{tone}format=yuvj420p",
                    "-q:v",
                    "2",
                    str(still),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
            subprocess.run(
                [
                    *run,
                    "-i",
                    str(src),
                    "-an",
                    "-vf",
                    f"{tone}scale={_MOTION_EDGE}:{_MOTION_EDGE}"
                    ":force_original_aspect_ratio=decrease:force_divisible_by=2,format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-r",
                    "30",
                    "-movflags",
                    "+faststart",
                    str(clip),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("unreadable video") from exc
        motion.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(clip, motion)
        return still.read_bytes(), taken


def _colours(path: Path) -> tuple[list[str], str | None]:
    """A photo's dominant colours and its tint: the most vivid of them that
    holds a fair share of the frame, lifted light so glass reads over it."""
    with Image.open(path) as opened:
        opened.draft("RGB", (192, 192))
        small = opened.convert("RGB")
    small.thumbnail((96, 96))
    quantized = small.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = sorted(quantized.getcolors() or [], reverse=True)
    total = sum(n for n, _ in counts) or 1
    swatches = [
        (n / total, tuple(palette[cast(int, i) * 3 : cast(int, i) * 3 + 3])) for n, i in counts
    ]
    colours = ["#{:02x}{:02x}{:02x}".format(*rgb) for _, rgb in swatches[:5]]
    best: tuple[float, float, float] | None = None
    best_score = 0.0
    for share, rgb in swatches:
        h, sat, val = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
        if sat < 0.18 or val < 0.25:
            continue
        score = sat * val * share**0.5
        if score > best_score:
            best, best_score = (h, sat, val), score
    if best is None:
        return colours, None
    r, g, b = colorsys.hsv_to_rgb(best[0], min(max(best[1], 0.35), 0.7), 0.97)
    return colours, f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def _aspect(path: Path) -> float | None:
    """Width over height as the photo is seen: EXIF orientations 5 to 8 stand
    it on its side."""
    try:
        with Image.open(path) as opened:
            w, h = opened.size
            if opened.getexif().get(ExifTags.Base.Orientation.value, 1) in (5, 6, 7, 8):
                w, h = h, w
    except (OSError, ValueError) as exc:
        logger.warning("could not read the size of %s: %s", path.name, exc)
        return None
    return round(w / h, 3) if h else None


def _colours_or_none(path: Path) -> tuple[list[str], str | None]:
    try:
        return _colours(path)
    except (OSError, ValueError) as exc:
        logger.warning("could not read the colours of %s: %s", path.name, exc)
        return [], None


def _extract_taken_at(path: Path) -> float | None:
    try:
        with Image.open(path) as opened:
            exif = opened.getexif()
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            raw = exif_ifd.get(ExifTags.Base.DateTimeOriginal.value) or exif.get(
                ExifTags.Base.DateTime.value
            )
            if not raw or not isinstance(raw, str):
                return None
            return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
    except (OSError, ValueError, KeyError, SyntaxError):
        return None


class PhotoStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._thumbs = root / ".cache"
        self._meta_path = root / ".cache" / "metadata.json"

    def _ensure_dirs(self) -> None:
        self._thumbs.mkdir(parents=True, exist_ok=True)

    def _meta(self) -> dict[str, Any]:
        try:
            data: object = json.loads(self._meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(data) if isinstance(data, dict) else {}

    def _write_meta(self, meta: dict[str, Any]) -> None:
        self._ensure_dirs()
        self._meta_path.write_text(json.dumps(meta))

    def all(self) -> list[Photo]:
        """The approved library, in slideshow order."""
        return [p for p in self._every() if not p.pending]

    def pending(self) -> list[Photo]:
        """Guest uploads waiting for approval, oldest first."""
        return sorted((p for p in self._every() if p.pending), key=lambda p: p.uploaded_at)

    def approve(self, name: str) -> Photo:
        meta = self._meta()
        if name not in meta:
            raise KeyError(name)
        meta[name].pop("pending", None)
        self._write_meta(meta)
        return Photo.model_validate({"name": name, **meta[name]})

    def _every(self) -> list[Photo]:
        meta = self._meta()
        photos = []
        changed = False
        for name, entry in meta.items():
            path = self._root / name
            if not path.is_file():
                continue
            # Self-healing backfill: photos imported before `taken_at` existed
            # (e.g. the original bulk import) get their EXIF date read once,
            # here, and cached into metadata.json — no separate migration.
            if "taken_at" not in entry:
                entry["taken_at"] = _extract_taken_at(path)
                changed = True
            photos.append(
                Photo.model_validate(
                    {
                        **entry,
                        "name": name,
                        "has_subject": self.subject_path(name).is_file(),
                        "motion": self.motion_path(name).is_file(),
                    }
                )
            )
        if changed:
            self._write_meta(meta)
        return sorted(photos, key=lambda p: (p.sort, p.uploaded_at))

    def on_this_day(self, today: date) -> Photo | None:
        """A photo taken on this month/day in a past year, or None if the
        library has no match — most days won't, in a few hundred photos."""
        candidates = [
            p
            for p in self.all()
            if p.taken_at is not None
            and (taken := datetime.fromtimestamp(p.taken_at, tz=UTC)).month == today.month
            and taken.day == today.day
            and taken.year != today.year
        ]
        if not candidates:
            return None
        # Most recent past occurrence — "3 years ago" reads better than
        # reaching for the oldest match when several years qualify.
        return max(candidates, key=lambda p: p.taken_at or 0)

    def count(self) -> int:
        return len(self.all())

    def original_path(self, name: str) -> Path:
        return self._root / _safe_name(name)

    def thumb_path(self, name: str) -> Path:
        return self._thumbs / f"thumb_{_safe_name(name)}.jpg"

    def display_copy_path(self, name: str) -> Path:
        return self._thumbs / f"display_{_safe_name(name)}.jpg"

    def subject_path(self, name: str) -> Path:
        return self._thumbs / f"subject_{_safe_name(name)}.webp"

    def mask_path(self, name: str) -> Path:
        return self._thumbs / f"mask_{_safe_name(name)}.png"

    def mask(self, name: str) -> Path | None:
        """A small copy of the subject cutout (_MASK_WIDTH wide, alpha kept),
        made the first time it's asked for and again if the cutout is newer.
        None when there's no cutout."""
        subject = self.subject_path(name)
        if not subject.is_file():
            return None
        path = self.mask_path(name)
        if path.is_file() and path.stat().st_mtime >= subject.stat().st_mtime:
            return path
        try:
            with Image.open(subject) as opened:
                cutout = opened.convert("RGBA")
            h = max(1, round(_MASK_WIDTH * cutout.height / cutout.width))
            small = cutout.resize((_MASK_WIDTH, h), Image.Resampling.BOX)
            self._ensure_dirs()
            small.save(path, "PNG", optimize=True)
        except (OSError, ValueError) as exc:
            logger.warning("could not make the cutout mask of %s: %s", name, exc)
            return None
        return path

    def motion_path(self, name: str) -> Path:
        """The clip that plays over a photo made from a video. Kept beside
        the originals, not in the cache: it can't be made again."""
        return self._root / "motion" / f"{_safe_name(name)}.mp4"

    def display_path(self, name: str) -> Path:
        """The file the slideshow should load: the display copy when there
        is one, else the original (small photos never get a copy)."""
        copy = self.display_copy_path(name)
        return copy if copy.is_file() else self.original_path(name)

    def backfill_display(self) -> int:
        """Make any missing display copies, one photo at a time. Returns how
        many were written."""
        made = 0
        for photo in self.all():
            if not self.display_copy_path(photo.name).is_file() and self._make_display(photo.name):
                made += 1
        if made:
            logger.info("made %d photo display copies", made)
        return made

    def backfill_colours(self) -> int:
        """Read the colours of photos added before they were kept. Returns
        how many were done."""
        found: dict[str, tuple[list[str], str | None]] = {}
        for name, entry in self._meta().items():
            if "tint" in entry or not (self._root / name).is_file():
                continue
            found[name] = _colours_or_none(self._root / name)
        if found:
            # Re-read: an upload or edit may have landed meanwhile.
            meta = self._meta()
            for name, (colours, tint) in found.items():
                if name in meta:
                    meta[name]["colours"], meta[name]["tint"] = colours, tint
            self._write_meta(meta)
            logger.info("read the colours of %d photos", len(found))
        return len(found)

    def backfill_aspects(self) -> int:
        """Read the shape of photos added before it was kept. Returns how
        many were done."""
        found = {
            name: _aspect(self._root / name)
            for name, entry in self._meta().items()
            if "aspect" not in entry and (self._root / name).is_file()
        }
        if found:
            meta = self._meta()
            for name, aspect in found.items():
                if name in meta:
                    meta[name]["aspect"] = aspect
            self._write_meta(meta)
            logger.info("read the shape of %d photos", len(found))
        return len(found)

    def backfill_subjects(self) -> int:
        """Make any missing subject cutouts. Returns how many were written."""
        missing = [p.name for p in self.all() if not self.subject_path(p.name).is_file()]
        made = self.make_subjects(missing) if missing else 0
        if made:
            logger.info("made %d photo subject cutouts", made)
        return made

    def add(self, filename: str, data: bytes, *, pending: bool = False) -> Photo:
        original_filename = filename
        digest = hashlib.sha256(data).hexdigest()
        meta = self._meta()
        for name, entry in meta.items():
            if entry.get("content_hash") == digest and (self._root / name).is_file():
                raise DuplicatePhotoError(name)

        clip_taken: float | None = None
        clip: Path | None = None
        if _is_video(data):
            self._ensure_dirs()
            clip = self._thumbs / f"incoming_{digest[:16]}.mp4"
            data, clip_taken = _from_video(data, clip)
            filename = (Path(filename).stem or "clip") + ".jpeg"
        elif (rendered := _from_raw(data)) is not None:
            data = rendered
            filename = (Path(filename).stem or "photo") + ".jpeg"
        if not _looks_like_image(data):
            raise ValueError("unrecognised image format")
        ext = Path(filename).suffix.lower()
        if ext not in _ACCEPTED_EXT:
            sniffed = _sniffed_ext(data)
            if sniffed is None:
                raise ValueError(f"unsupported extension: {ext}")
            filename = (Path(filename).stem or "photo") + sniffed

        self._ensure_dirs()
        name = _unique_name(self._root, filename)
        path = self._root / name
        path.write_bytes(data)
        if clip is not None:
            self.motion_path(name).parent.mkdir(parents=True, exist_ok=True)
            clip.replace(self.motion_path(name))
        next_sort = max((int(e.get("sort", 0)) for e in meta.values()), default=-1) + 1
        entry = {
            "uploaded_at": time.time(),
            "rotation": 0,
            "original_filename": original_filename,
            "content_hash": digest,
            "sort": next_sort,
            "taken_at": _extract_taken_at(path) or clip_taken,
        }
        entry["colours"], entry["tint"] = _colours_or_none(path)
        entry["aspect"] = _aspect(path)
        if pending:
            entry["pending"] = True
        meta[name] = entry
        self._write_meta(meta)
        self._make_thumb(name)
        self._make_display(name)
        logger.info("photo added: %s%s", name, " (with motion)" if clip else "")
        return Photo.model_validate({"name": name, **entry, "motion": clip is not None})

    def rotate(self, name: str, degrees: int) -> Photo:
        meta = self._meta()
        if name not in meta:
            raise KeyError(name)
        meta[name]["rotation"] = int(degrees) % 360
        self._write_meta(meta)
        self._make_thumb(name)
        return Photo.model_validate({"name": name, **meta[name]})

    def reorder(self, names: list[str]) -> list[Photo]:
        """Set the slideshow order. Named photos go first, in the given order;
        anything unnamed keeps its place after them."""
        meta = self._meta()
        ordered = [n for n in names if n in meta]
        rest = sorted(
            (n for n in meta if n not in ordered),
            key=lambda n: int(meta[n].get("sort", 0)),
        )
        for i, n in enumerate(ordered + rest):
            meta[n]["sort"] = i
        self._write_meta(meta)
        return self.all()

    def render(self, name: str) -> bytes:
        """The photo as displayed — EXIF-normalised and rotation applied — as a
        JPEG. Used when handing a photo to the wallpaper store."""
        with Image.open(self._root / name) as opened:
            image = ImageOps.exif_transpose(opened) or opened
            rotation = self._rotation(name)
            if rotation:
                image = image.rotate(-rotation, expand=True)
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, "JPEG", quality=90)
            return buffer.getvalue()

    def _collect_delete_targets(self, name: str, safe: str, stem: str) -> set[Path]:
        targets = {
            self.original_path(name),
            self.thumb_path(name),
            self.display_copy_path(name),
            self.subject_path(name),
            self.mask_path(name),
            self.motion_path(name),
            self._thumbs / f"thumb_{stem}.jpg",
            self._thumbs / f"display_{stem}.jpg",
            self._thumbs / f"subject_{stem}.webp",
            self._root / "motion" / f"{stem}.mp4",
        }
        if self._thumbs.is_dir():
            targets.update(self._thumbs.glob(f"*_{safe}*"))
            targets.update(self._thumbs.glob(f"*_{stem}.*"))
        motion_dir = self._root / "motion"
        if motion_dir.is_dir():
            targets.update(motion_dir.glob(f"{safe}.*"))
            targets.update(motion_dir.glob(f"{stem}.*"))
        return targets

    def delete(self, name: str) -> bool:
        safe = _safe_name(name)
        stem = Path(safe).stem
        meta = self._meta()
        had_meta = meta.pop(name, None) is not None
        if not had_meta and stem in meta:
            meta.pop(stem, None)
            had_meta = True

        deleted_file = False
        for p in self._collect_delete_targets(name, safe, stem):
            if p.is_file():
                try:
                    p.unlink(missing_ok=True)
                    deleted_file = True
                except OSError:
                    pass

        if had_meta:
            self._write_meta(meta)
        return had_meta or deleted_file

    def _rotation(self, name: str) -> int:
        try:
            return int(self._meta().get(name, {}).get("rotation", 0))
        except (TypeError, ValueError):
            return 0

    def _make_thumb(self, name: str) -> None:
        try:
            with Image.open(self._root / name) as opened:
                image = ImageOps.exif_transpose(opened) or opened
                rotation = self._rotation(name)
                if rotation:
                    image = image.rotate(-rotation, expand=True)
                image.thumbnail((_THUMB_WIDTH, _THUMB_WIDTH))
                image.convert("RGB").save(self.thumb_path(name), "JPEG", quality=82)
        except (OSError, ValueError) as exc:
            logger.warning("could not thumbnail %s: %s", name, exc)

    def _make_display(self, name: str) -> bool:
        """Write the display copy if the original is bigger than the display
        edge or isn't a JPEG. Returns whether a copy was written."""
        try:
            with Image.open(self._root / name) as opened:
                if opened.format == "JPEG" and max(opened.size) <= _DISPLAY_EDGE:
                    return False
                # JPEG: decode at a reduced DCT scale, a fraction of the
                # memory of a full 12 MP decode. A no-op for other formats.
                opened.draft("RGB", (_DISPLAY_EDGE, _DISPLAY_EDGE))
                image = ImageOps.exif_transpose(opened) or opened
                image.thumbnail((_DISPLAY_EDGE, _DISPLAY_EDGE), Image.Resampling.LANCZOS)
                self._ensure_dirs()
                image.convert("RGB").save(
                    self.display_copy_path(name), "JPEG", quality=85, optimize=True
                )
                return True
        except (OSError, ValueError) as exc:
            logger.warning("could not make display copy of %s: %s", name, exc)
            return False

    def make_subjects(self, names: list[str]) -> int:
        """Write the subject cutouts (transparent WebPs the size of the
        display copy) the Photo Clock's depth effect lays over the time.
        Returns how many were written. Slow (seconds a photo on CPU), so
        callers run it in a thread. The model is loaded for the batch and
        dropped after: it holds many GB of RAM while loaded."""
        with _SUBJECT_LOCK:
            todo = [n for n in names if not self.subject_path(n).is_file()]
            if not todo:
                return 0
            try:
                from rembg import new_session, remove
            except ImportError:
                logger.info("rembg not installed; the Photo Clock depth effect is off")
                return 0
            session = new_session("bria-rmbg")
            made = 0
            for name in todo:
                src = self.display_path(name)
                try:
                    with Image.open(src) as opened:
                        image = ImageOps.exif_transpose(opened) or opened
                        cutout = remove(image.convert("RGB"), session=session)
                    self._ensure_dirs()
                    cutout.save(self.subject_path(name), "WEBP", quality=90)
                    made += 1
                except Exception as exc:  # a bad photo mustn't stop the batch
                    logger.warning("could not cut out the subject of %s: %s", name, exc)
            del session
            gc.collect()
            return made


_SUBJECT_LOCK = threading.Lock()


def _safe_name(name: str) -> str:
    return Path(name).name


def _unique_name(directory: Path, filename: str) -> str:
    stem, suffix = Path(filename).stem, Path(filename).suffix.lower()
    candidate = f"{stem}{suffix}"
    counter = 1
    while (directory / candidate).exists():
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate
