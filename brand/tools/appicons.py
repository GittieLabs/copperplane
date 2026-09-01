#!/usr/bin/env python3
"""Generate the Tauri app icon set from the Copperplane tile.

Full-bleed art everywhere except the macOS .icns, where the tile is inset to 80.5%
of the canvas so it sits at the right optical size next to other Mac icons.
"""
import io
import os
import re
import struct

from PIL import Image
from playwright.sync_api import sync_playwright

SVG = "/home/claude/copperplane/brand/svg/icon.svg"
SVG_SMALL = "/home/claude/copperplane/brand/svg/icon-small.svg"
SMALL_AT = 48  # at or below this, use the small-size drawing, not a downscale
OUT = "/home/claude/copperplane/brand/app-icons"
os.makedirs(OUT, exist_ok=True)

MAC_INSET = 0.805          # Apple's rounded-rectoccupies 824 of 1024 on the icon grid
PNG_SIZES = {
    "32x32.png": 32, "128x128.png": 128, "128x128@2x.png": 256, "icon.png": 512,
    "Square30x30Logo.png": 30, "Square44x44Logo.png": 44, "Square71x71Logo.png": 71,
    "Square89x89Logo.png": 89, "Square107x107Logo.png": 107, "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150, "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310, "StoreLogo.png": 50,
}
ICO_SIZES = [16, 24, 32, 48, 64, 256]
# (icns type, pixel size) — PNG-carrying types only
ICNS = [(b"ic11", 32), (b"ic12", 64), (b"ic07", 128), (b"ic13", 256),
        (b"ic08", 256), (b"ic14", 512), (b"ic09", 512), (b"ic10", 1024)]


def render(size, src=None):
    """Render the tile SVG at `size` px, transparent background."""
    svg = open(src or (SVG_SMALL if size <= SMALL_AT else SVG)).read()
    svg = re.sub(r'width="[\d.]+" height="[\d.]+"', f'width="{size}" height="{size}"', svg, count=1)
    html = f"<!doctype html><style>html,body{{margin:0;background:transparent}}</style>{svg}"
    open("/tmp/_icon.html", "w").write(html)
    page = BROWSER.new_page(viewport={"width": size, "height": size})
    page.goto("file:///tmp/_icon.html")
    buf = page.screenshot(omit_background=True)
    page.close()
    return Image.open(io.BytesIO(buf)).convert("RGBA")


def inset(size, factor=MAC_INSET):
    """Art centred at `factor` of a transparent square canvas."""
    art_px = max(1, round(size * factor))
    art = render(art_px)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    off = (size - art_px) // 2
    canvas.paste(art, (off, off), art)
    return canvas


def write_icns(path, images):
    """Minimal ICNS writer: 'icns' + length, then typed PNG chunks."""
    chunks = b""
    for typ, img in images:
        blob = io.BytesIO()
        img.save(blob, format="PNG")
        data = blob.getvalue()
        chunks += typ + struct.pack(">I", len(data) + 8) + data
    with open(path, "wb") as fh:
        fh.write(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


with sync_playwright() as p:
    BROWSER = p.chromium.launch()

    for name, size in PNG_SIZES.items():
        render(size).save(os.path.join(OUT, name))

    parts = []
    for sz in ICO_SIZES:
        f = f"/tmp/_ico_{sz}.png"
        render(sz).save(f)
        parts.append(f)
    os.system("convert " + " ".join(parts) + " " + os.path.join(OUT, "icon.ico"))

    write_icns(os.path.join(OUT, "icon.icns"), [(t, inset(s)) for t, s in ICNS])

    BROWSER.close()

print("app icons:", len(os.listdir(OUT)), "files")
for f in sorted(os.listdir(OUT)):
    print("  ", f, os.path.getsize(os.path.join(OUT, f)), "bytes")
