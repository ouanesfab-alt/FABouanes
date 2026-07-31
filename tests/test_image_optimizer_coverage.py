"""Tests unitaires pour app/core/image_optimizer.py (Vague 1.2 — couverture > 90%)."""
from __future__ import annotations

import io
from PIL import Image
from app.core.image_optimizer import optimize_uploaded_image


def test_optimize_uploaded_image_too_small():
    raw = b"short"
    data, ext = optimize_uploaded_image(raw)
    assert data == raw
    assert ext == ".jpg"


def test_optimize_uploaded_image_rgb():
    img = Image.new("RGB", (1600, 1200), color="red")
    out = io.BytesIO()
    img.save(out, format="JPEG")
    raw = out.getvalue()

    compressed, ext = optimize_uploaded_image(raw, max_dim=800, quality=80)
    assert ext == ".jpg"
    assert len(compressed) > 0

    res_img = Image.open(io.BytesIO(compressed))
    assert max(res_img.size) <= 800


def test_optimize_uploaded_image_rgba_webp():
    img = Image.new("RGBA", (400, 400), color=(255, 0, 0, 128))
    out = io.BytesIO()
    img.save(out, format="PNG")
    raw = out.getvalue()

    compressed, ext = optimize_uploaded_image(raw, quality=80)
    assert ext == ".webp"
    assert len(compressed) > 0


def test_optimize_uploaded_image_invalid_corrupted():
    corrupted = b"X" * 200
    res_bytes, ext = optimize_uploaded_image(corrupted)
    assert res_bytes == corrupted
    assert ext == ".jpg"
