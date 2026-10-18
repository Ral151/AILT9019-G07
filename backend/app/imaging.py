"""Server-side image re-validation (FR-1). Everything stays in memory (R8):
bytes are never written to disk, logged, or cached."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

_MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


class ImageRejected(ValueError):
    pass


@dataclass(frozen=True)
class CleanImage:
    data: bytes  # re-encoded JPEG, metadata stripped
    mime: str = "image/jpeg"


def sniff_mime(data: bytes) -> str | None:
    for mime, prefixes in _MAGIC.items():
        if any(data.startswith(p) for p in prefixes):
            if mime == "image/webp" and data[8:12] != b"WEBP":
                continue
            return mime
    return None


def validate_and_reencode(data: bytes, *, max_bytes: int, max_pixels: int, max_edge: int) -> CleanImage:
    if len(data) > max_bytes:
        raise ImageRejected("Image is larger than 5 MB.")
    if sniff_mime(data) is None:
        raise ImageRejected("Only JPEG, PNG or WebP photos are accepted.")
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.width * img.height > max_pixels:
                raise ImageRejected("Image has too many pixels.")
            img.load()
            rgb = img.convert("RGB")  # drops alpha, palette and EXIF/GPS
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ImageRejected("The photo could not be read.") from exc
    rgb.thumbnail((max_edge, max_edge))
    out = io.BytesIO()
    rgb.save(out, format="JPEG", quality=85)
    return CleanImage(data=out.getvalue())
