#!/usr/bin/env python3
"""
The macOS disk-image background.

Tauri lays the volume window out itself (`bundle.macOS.dmg` in
tauri.conf.json): a 660x400 window with the app at (180, 170) and the
Applications symlink at (480, 170). This draws the ground those two icons sit
on, and it must leave both of those positions clear.

Deliberately not a generic arrow. The Copperplane mark is a routed trace
broken at 45 degrees with a via at each open end, so the "drag this there"
cue is drawn in the same language: a trace leaving a via, mitred like the
mark, ending in an arrowhead under the Applications folder. It reads as an
instruction and as the brand at the same time.

Standalone on purpose. `build.py` imports `text2path`, which needs
`fontTools`, and this needs no text at all -- only `geometry.py`, which is
pure numbers.

    python3 tools/dmg_background.py          # writes svg/dmg-background.svg
    magick -background none svg/dmg-background.svg -resize 1320x800 \
        png/dmg-background.png
"""
import os

from geometry import CHANNEL, CHANNEL_W, PALETTE, VIA_A, VIA_B, VIA_HOLE_R, VIA_OUTER_R

BRAND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Must match `bundle.macOS.dmg.windowSize` exactly. The PNG is rendered at
#: twice this and Finder scales it down, which is what makes it crisp on a
#: retina display -- Tauri accepts one image, not a multi-representation TIFF.
W, H = 660, 400

#: Must match `appPosition` and `applicationFolderPosition`. These are icon
#: centres; nothing decorative may come near them.
APP = (180, 170)
APPS_FOLDER = (480, 170)
ICON_CLEAR_R = 74  # icon plus its label, generously


def mark(x, y, size, color, ground):
    """The mark, scaled and placed.

    The kit's own marks punch the two via holes with an SVG `mask`. That is
    correct SVG and ImageMagick's renderer ignores it -- the mask rectangle
    came out as a white box over the artwork. Since this sits on one known
    solid colour, the holes are overdrawn in the ground colour instead, which
    renders identically and depends on nothing.
    """
    s = size / 64.0
    return (
        f'<g transform="translate({x - size / 2:.1f},{y - size / 2:.1f}) scale({s:.4f})">'
        f'<path d="{CHANNEL}" fill="none" stroke="{color}" stroke-width="{CHANNEL_W}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{VIA_A[0]}" cy="{VIA_A[1]}" r="{VIA_HOLE_R}" fill="{ground}"/>'
        f'<circle cx="{VIA_B[0]}" cy="{VIA_B[1]}" r="{VIA_HOLE_R}" fill="{ground}"/>'
        f'</g>'
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
        + mark(W / 2, 62, 44, trace, ink)
        + trace_cue(trace)
        + f'</svg>'
    )


if __name__ == "__main__":
    out = os.path.join(BRAND, "svg", "dmg-background.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as handle:
        handle.write(background())
    print(f"wrote {out}")
