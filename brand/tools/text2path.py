#!/usr/bin/env python3
"""Convert a string to a single SVG path 'd' using a font's real outlines.

Usage: text2path.py <font.woff2> <text> <cap_height_px> [tracking_em] [weight_label]
Prints JSON: {"d":..., "width":..., "capHeight":..., "advance":...}
Path is emitted in a coordinate system where y=0 is the baseline and y grows DOWN,
scaled so that the font's cap height equals cap_height_px.
"""
import json
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.misc.transform import Transform
from fontTools.ttLib import TTFont


def build(font_path, text, cap_px, tracking_em=0.0):
    font = TTFont(font_path)
    upem = font["head"].unitsPerEm
    os2 = font["OS/2"]
    cap = getattr(os2, "sCapHeight", 0) or int(upem * 0.7)
    scale = cap_px / cap
    cmap = font.getBestCmap()
    glyphset = font.getGlyphSet()
    hmtx = font["hmtx"]

    pen = SVGPathPen(glyphset, ntos=lambda v: f"{v:.2f}")
    x = 0.0
    track_units = tracking_em * upem
    for ch in text:
        gname = cmap.get(ord(ch))
        if gname is None:
            x += upem * 0.3 + track_units
            continue
        # flip y (font y-up -> svg y-down) and scale, then place at x
        t = Transform(scale, 0, 0, -scale, x * scale, 0)
        tpen = TransformPen(pen, t)
        glyphset[gname].draw(tpen)
        x += hmtx[gname][0] + track_units
    total = (x - track_units) * scale
    return {
        "d": pen.getCommands(),
        "width": round(total, 2),
        "capHeight": cap_px,
        "upem": upem,
        "sCapHeight": cap,
    }


if __name__ == "__main__":
    fp, text, cap = sys.argv[1], sys.argv[2], float(sys.argv[3])
    tracking = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    print(json.dumps(build(fp, text, cap, tracking)))
