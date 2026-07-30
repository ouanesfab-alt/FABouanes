from __future__ import annotations

import io
import logging
from typing import Any

from PIL import Image, ImageOps

logger = logging.getLogger("fabouanes.image")


def optimize_uploaded_image(
    input_bytes: bytes, max_dim: int = 1200, quality: int = 82
) -> tuple[bytes, str]:
    """
    Auto-resizes and compresses uploaded images for ultra-fast mobile loading.
    Converts large photos to compressed JPEG/WebP (max 1200px dimension).
    Returns (compressed_bytes, extension_with_dot).
    """
    if not input_bytes or len(input_bytes) < 100:
        return input_bytes, ".jpg"

    try:
        img = Image.open(io.BytesIO(input_bytes))
        img = ImageOps.exif_transpose(img)

        width, height = img.size
        if width > max_dim or height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        # Save as WebP if transparency exists, otherwise JPEG
        if img.mode in ("RGBA", "P") and ("transparency" in img.info or img.mode == "RGBA"):
            img.save(out, format="WEBP", quality=quality, method=4)
            ext = ".webp"
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(out, format="JPEG", quality=quality, optimize=True)
            ext = ".jpg"

        compressed = out.getvalue()
        if len(compressed) < len(input_bytes):
            logger.info("Compressed image from %d to %d bytes (%d%% reduction)", len(input_bytes), len(compressed), int(100 - (len(compressed) / len(input_bytes) * 100)))
            return compressed, ext
        return input_bytes, ext
    except Exception as exc:
        logger.warning("Image optimization fallback: %s", exc)
        return input_bytes, ".jpg"
