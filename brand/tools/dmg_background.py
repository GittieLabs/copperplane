#!/usr/bin/env python3
"""
The macOS disk-image background.

Tauri lays the volume window out itself (`bundle.macOS.dmg` in
tauri.conf.json): a 660x400 window with the app at (180, 170) and the
Applications symlink at (480, 170). This draws the ground those two icons sit
on, leaves both positions clear, and says what to do.

Two things about this file are not obvious and both were learned the hard way:

*   **Finder sizes the background from the PNG's DPI, not from the window.**
    A 1320x800 image at the default 72 DPI is 1320x800 *points* -- twice the
    window -- so the volume opens with a scroll bar and every drawn element
    lands at double the distance from its icon. The fix is a `pHYs` chunk
    declaring 144 DPI, which makes the same pixels measure 660x400 points and
    stay crisp on a retina display. This script writes that chunk itself
    rather than leaving it to whoever runs the render.

*   **Render with `rsvg-convert`, never ImageMagick.** ImageMagick's SVG
    renderer honours `fill` and silently ignores `stroke`. The mark and the
    trace are stroke-only, so it produces a background with the artwork
    missing and no error at all.

The "drag this there" cue is deliberately not a generic arrow. The Copperplane
mark is a routed trace broken at 45 degrees with a via at each open end, so the
cue is drawn in the same language: a trace leaving a via, ending in an
arrowhead under the Applications folder. It reads as an instruction and as the
brand at the same time.

    python3 tools/dmg_background.py

writes svg/dmg-background.svg, renders png/dmg-background.png at 2x with the
right DPI, and copies it to core/tauri-rust/dmg/background.png.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib

from geometry import CHANNEL, CHANNEL_W, PALETTE, VIA_A, VIA_B, VIA_HOLE_R, VIA_OUTER_R

BRAND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BRAND)

#: Must match `bundle.macOS.dmg.windowSize` exactly, in points.
W, H = 660, 400

#: The PNG is rendered at this multiple and declares a matching DPI, so it
#: measures W x H points while carrying 2x the pixels.
SCALE = 2
DPI = 72 * SCALE

#: Must match `appPosition` and `applicationFolderPosition`. These are icon
#: centres; nothing decorative may come near them.
APP = (180, 170)
APPS_FOLDER = (480, 170)
ICON_CLEAR_R = 74  # icon plus its label, generously

#: The sentence under the icons. Body copy, not the wordmark -- the wordmark
#: is set from the kit's outlines below and is never live text.
INSTRUCTION = "Drag Copperplane into your Applications folder"
TEXT_FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"


def mark(x, y, size, color, ground):
    """The mark, scaled and placed.

    The kit's own marks punch the two via holes with an SVG `mask`. Since this
    sits on one known solid colour, the holes are overdrawn in the ground
    colour instead, which renders identically and depends on no mask support.
    """
    s = size / 64.0
    return (
        f'<g transform="translate({x - size / 2:.2f},{y - size / 2:.2f}) scale({s:.4f})">'
        f'<path d="{CHANNEL}" fill="none" stroke="{color}" stroke-width="{CHANNEL_W}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{VIA_A[0]}" cy="{VIA_A[1]}" r="{VIA_HOLE_R}" fill="{ground}"/>'
        f'<circle cx="{VIA_B[0]}" cy="{VIA_B[1]}" r="{VIA_HOLE_R}" fill="{ground}"/>'
        f'</g>'
    )


def wordmark(x, y, width, color):
    """The wordmark, lifted from the kit's own outlines.

    `build.py` converts IBM Plex to paths with fontTools, which is not
    installed here and is not needed: `svg/wordmark-on-dark.svg` is already
    outlined, so this reads the drawing rather than re-deriving it. `x, y` is
    the left edge and the vertical centre.
    """
    src = os.path.join(BRAND, "svg", "wordmark-on-dark.svg")
    with open(src) as handle:
        svg = handle.read()

    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    if not box or not inner:
        raise SystemExit(f"{src} is not the shape this expects; wordmark not embedded")

    native_w, native_h = float(box.group(1)), float(box.group(2))
    scale = width / native_w
    body = re.sub(r'fill="#[0-9A-Fa-f]{6}"', f'fill="{color}"', inner.group(1))
    top = y - native_h * scale / 2
    return f'<g transform="translate({x:.2f},{top:.2f}) scale({scale:.5f})">{body}</g>'


def lockup(cx, cy, color, ground):
    """Mark and wordmark, set as the horizontal lockup, centred on `cx`."""
    mark_size = 34.0
    word_w = 168.0
    gap = 14.0
    total = mark_size + gap + word_w
    left = cx - total / 2
    return mark(left + mark_size / 2, cy, mark_size, color, ground) + wordmark(
        left + mark_size + gap, cy, word_w, color
    )


def trace_cue(color):
    """A routed trace from beside the app icon to beneath the folder.

    Starts at a via, runs straight, and ends in an arrowhead. Both endpoints
    are held outside ICON_CLEAR_R of their neighbouring icon so the trace
    never runs under an icon or its filename.
    """
    y = APP[1]
    x0 = APP[0] + ICON_CLEAR_R
    x1 = APPS_FOLDER[0] - ICON_CLEAR_R
    head = 13.0
    return (
        f'<circle cx="{x0}" cy="{y}" r="{VIA_OUTER_R * 0.7:.1f}" fill="none" '
        f'stroke="{color}" stroke-width="3"/>'
        f'<path d="M{x0 + 10} {y} L{x1 - head} {y}" stroke="{color}" stroke-width="3" '
        f'stroke-linecap="round"/>'
        f'<path d="M{x1 - head} {y - head * 0.55} L{x1} {y} L{x1 - head} {y + head * 0.55} Z" '
        f'fill="{color}"/>'
    )


def background():
    ink = PALETTE["ink"]
    trace = PALETTE["green300"]
    faint = PALETTE["green700"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
        f'<rect width="{W}" height="{H}" fill="{ink}"/>'
        # A hairline routing grid, barely there -- texture, not decoration.
        + "".join(
            f'<path d="M0 {y} H{W}" stroke="{faint}" stroke-width="0.5" opacity="0.28"/>'
            for y in range(40, H, 40)
        )
        + lockup(W / 2, 58, trace, ink)
        + trace_cue(trace)
        + f'<text x="{W / 2}" y="292" text-anchor="middle" font-family="{TEXT_FONT}" '
        f'font-size="15" letter-spacing="0.4" fill="{trace}">{INSTRUCTION}</text>'
        + f'</svg>'
    )


def set_dpi(path, dpi):
    """Rewrite the PNG's pHYs chunk so Finder measures it in points, not pixels.

    Without this the volume window opens with a scroll bar and the artwork
    sits at twice its intended distance from the icons.
    """
    ppm = int(round(dpi / 0.0254))
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path} is not a PNG")

    chunk = struct.pack(">IIB", ppm, ppm, 1)
    phys = struct.pack(">I", len(chunk)) + b"pHYs" + chunk
    phys += struct.pack(">I", zlib.crc32(b"pHYs" + chunk) & 0xFFFFFFFF)

    out, pos = bytearray(data[:8]), 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        end = pos + 12 + length
        if kind == b"pHYs":  # drop any existing one, we write our own
            pos = end
            continue
        if kind == b"IDAT" and b"pHYs" not in out:
            out += phys
        out += data[pos:end]
        pos = end
    with open(path, "wb") as handle:
        handle.write(bytes(out))


if __name__ == "__main__":
    if not shutil.which("rsvg-convert"):
        sys.exit(
            "rsvg-convert is required. ImageMagick silently drops SVG strokes, "
            "which are most of this drawing.\n  brew install librsvg"
        )

    svg_path = os.path.join(BRAND, "svg", "dmg-background.svg")
    png_path = os.path.join(BRAND, "png", "dmg-background.png")
    shipped = os.path.join(REPO, "core", "tauri-rust", "dmg", "background.png")

    for path in (svg_path, png_path, shipped):
        os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(svg_path, "w") as handle:
        handle.write(background())

    subprocess.run(
        ["rsvg-convert", "-w", str(W * SCALE), "-h", str(H * SCALE), svg_path, "-o", png_path],
        check=True,
    )
    set_dpi(png_path, DPI)
    shutil.copyfile(png_path, shipped)

    print(f"wrote {svg_path}")
    print(f"wrote {png_path}  ({W * SCALE}x{H * SCALE}px at {DPI} dpi = {W}x{H}pt)")
    print(f"wrote {shipped}")
