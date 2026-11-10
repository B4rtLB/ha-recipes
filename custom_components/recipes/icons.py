"""Draw the app icons with Pillow (ships with Home Assistant) instead of storing PNGs."""

from __future__ import annotations

import math
from pathlib import Path

SIZES = (180, 192, 512)


def ensure_icons(folder: Path) -> None:
    """Create icon-<size>.png files in folder if they are missing. Blocking."""
    if all((folder / f"icon-{size}.png").exists() for size in SIZES):
        return
    from PIL import Image, ImageDraw, ImageFilter  # noqa: PLC0415

    folder.mkdir(parents=True, exist_ok=True)
    big = 1024
    # warm Apple-Music-like gradient (pink red -> orange)
    vertical = Image.linear_gradient("L").resize((big, big))
    grad = Image.blend(vertical, vertical.transpose(Image.Transpose.ROTATE_90).transpose(Image.Transpose.FLIP_LEFT_RIGHT), 0.35)
    start = Image.new("RGB", (big, big), (252, 60, 90))
    end = Image.new("RGB", (big, big), (255, 128, 58))
    img = Image.composite(end, start, grad)
    # soft glossy highlight at the top
    glow = Image.new("L", (big, big), 0)
    ImageDraw.Draw(glow).ellipse((-200, -650, big + 200, 420), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    img = Image.composite(Image.new("RGB", (big, big), (255, 255, 255)), img, glow)

    # draw the white glyph at 2x for smooth edges, then scale down
    scale = 2
    glyph = Image.new("L", (big * scale, big * scale), 0)
    d = ImageDraw.Draw(glyph)

    def s(*v: float) -> tuple[float, ...]:
        return tuple(x * scale for x in v)

    d.chord(s(222, 360, 802, 820), 0, 180, fill=255)
    d.rounded_rectangle(s(180, 548, 844, 600), radius=26 * scale, fill=255)
    d.rounded_rectangle(s(420, 790, 604, 830), radius=20 * scale, fill=255)
    for i, x in enumerate((392, 512, 632)):
        pts = [s(x + 22 * math.sin(k / 6.0 + i), 470 - k * 6.5) for k in range(40)]
        d.line(pts, fill=235, width=34 * scale, joint="curve")
        for px, py in (pts[0], pts[-1]):
            r = 17 * scale
            d.ellipse((px - r, py - r, px + r, py + r), fill=235)
    glyph = glyph.resize((big, big), Image.LANCZOS)
    img.paste((255, 255, 255), (0, 0), glyph)

    for size in SIZES:
        img.resize((size, size), Image.LANCZOS).save(folder / f"icon-{size}.png", optimize=True)
