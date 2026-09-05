#!/usr/bin/env python3
"""Build the Copperplane identity: marks, lockups, wordmarks, and PNG renders."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from text2path import build as t2p

# Resolved from this file's own location, so the generator runs wherever the
# repository is checked out. It was hardcoded to /home/claude/copperplane/brand
# -- the machine it was written on -- which meant brand/README.md documented two
# commands that could not run anywhere else, and the kit could not be
# regenerated at all.
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = "/tmp/cp/node_modules/@fontsource"
PLEX600 = f"{F}/ibm-plex-sans/files/ibm-plex-sans-latin-600-normal.woff2"
PLEX400 = f"{F}/ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff2"

C = {
    "green700": "#0B5C34",
    "green600": "#10743F",
    "green500": "#178F4E",
    "green300": "#4FC17E",
    "copper": "#C0703A",
    "ink": "#0A1410",
    "paper": "#F4F7F3",
}

# ---------------------------------------------------------------- geometry
R, CHAMFER, OPEN_HALF, W = 16.5, 9.0, 7.8, 8.5
HOLE_R = 2.7
TERM = ((48.5, 32 - OPEN_HALF), (48.5, 32 + OPEN_HALF))
# visible bounds of the mark inside the 64 box
VIS_MIN = 32 - R - W / 2
VIS_SIZE = (R + W / 2) * 2


def c_path():
    lo, hi = 32 - R, 32 + R
    pts = [(hi, 32 - OPEN_HALF), (hi - CHAMFER, lo), (lo + CHAMFER, lo), (lo, lo + CHAMFER),
           (lo, hi - CHAMFER), (lo + CHAMFER, hi), (hi - CHAMFER, hi), (hi, 32 + OPEN_HALF)]
    return "M" + " L".join(f"{x} {y}" for x, y in pts)


def c_path_small():
    """Small-size cut: heavier trace, wider mouth, so it survives 16-20px."""
    r, ch, oh = 17.5, 8.0, 9.5
    lo, hi = 32 - r, 32 + r
    pts = [(hi, 32 - oh), (hi - ch, lo), (lo + ch, lo), (lo, lo + ch),
           (lo, hi - ch), (lo + ch, hi), (hi - ch, hi), (hi, 32 + oh)]
    return "M" + " L".join(f"{x} {y}" for x, y in pts)


def mark_body(color, uid, drilled=True, small=False):
    """The mark as positive artwork in `color`."""
    if small:
        return (f'<path d="{c_path_small()}" fill="none" stroke="{color}" stroke-width="11" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
    stroke = (f'<path d="{c_path()}" fill="none" stroke="{color}" stroke-width="{W}" '
              f'stroke-linecap="round" stroke-linejoin="round"/>')
    if not drilled:
        return stroke
    holes = "".join(f'<circle cx="{x}" cy="{y}" r="{HOLE_R}" fill="#000"/>' for x, y in TERM)
    return (f'<mask id="drill{uid}" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">'
            f'<rect width="64" height="64" fill="#fff"/>{holes}</mask>'
            f'<g mask="url(#drill{uid})">{stroke}</g>')


def svg_head(w, h, vb=None):
    vb = vb or f"0 0 {w} {h}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{w}" height="{h}" '
            f'fill="none">')


def mark_svg(color, uid, drilled=True, size=64, small=False):
    return f'{svg_head(size, size, "0 0 64 64")}{mark_body(color, uid, drilled, small)}</svg>'


def tile_svg(plane, substrate, uid, size=512, bleed=True, drilled=True, small=False):
    """The plane, with the mark routed out of it. Substrate shows through the channel."""
    rx = 14 if bleed else 14
    body = mark_body("#000", uid, drilled, small)
    return (f'{svg_head(size, size, "0 0 64 64")}'
            f'<defs><mask id="plane{uid}" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">'
            f'<rect width="64" height="64" fill="#fff"/>'
            f'<g stroke="#000">{body}</g></mask></defs>'
            f'<rect width="64" height="64" rx="{rx}" fill="{substrate}"/>'
            f'<rect width="64" height="64" rx="{rx}" fill="{plane}" mask="url(#plane{uid})"/></svg>')


# ---------------------------------------------------------------- wordmark
CAP = 100.0
TRACK = 0.055


def wordmark_paths(color):
    d = t2p(PLEX600, "COPPERPLANE", CAP, TRACK)
    return d, f'<path d="{d["d"]}" fill="{color}"/>'


def wordmark_svg(color, scale=0.4):
    d, path = wordmark_paths(color)
    dw = d["width"]
    pad = CAP * 0.12
    h = CAP + pad * 2
    return (f'{svg_head(round(d["width"] * scale, 1), round(h * scale, 1), f"0 0 {dw:.1f} {h:.1f}")}'
            f'<g transform="translate(0,{CAP + pad:.1f})">{path}</g></svg>')


def lockup_h(mark_color, text_color, uid, scale=0.4, drilled=True):
    d, path = wordmark_paths(text_color)
    dw = d["width"]
    target = CAP * 1.34                     # visible mark height vs cap height
    s = target / VIS_SIZE
    box = 64 * s
    gap = CAP * 0.52
    mx = 0.0
    my = (CAP / 2) - 32 * s                 # centre the mark on the cap's midline
    tx = mx + (VIS_MIN * s) + target + gap  # start text after the mark's visible edge
    left_trim = VIS_MIN * s
    w = tx + d["width"] - left_trim
    pad = CAP * 0.12
    h = max(box, CAP) + pad * 2
    top = (h - CAP) / 2
    return (f'{svg_head(round(w * scale, 1), round(h * scale, 1), f"0 0 {w:.1f} {h:.1f}")}'
            f'<g transform="translate({-left_trim:.2f},{top + my:.2f}) scale({s:.5f})">'
            f'{mark_body(mark_color, uid, drilled)}</g>'
            f'<g transform="translate({tx - left_trim:.2f},{top + CAP:.2f})">{path}</g></svg>')


def lockup_stacked(mark_color, text_color, uid, scale=0.4, drilled=True):
    d, path = wordmark_paths(text_color)
    dw = d["width"]
    target = CAP * 2.6
    s = target / VIS_SIZE
    box = 64 * s
    gap = CAP * 0.55
    w = max(target, d["width"])
    pad = CAP * 0.12
    h = target + gap + CAP + pad * 2
    mx = (w - target) / 2 - VIS_MIN * s
    tx = (w - d["width"]) / 2
    return (f'{svg_head(round(w * scale, 1), round(h * scale, 1), f"0 0 {w:.1f} {h:.1f}")}'
            f'<g transform="translate({mx:.2f},{pad - VIS_MIN * s:.2f}) scale({s:.5f})">'
            f'{mark_body(mark_color, uid, drilled)}</g>'
            f'<g transform="translate({tx:.2f},{pad + target + gap + CAP:.2f})">{path}</g></svg>')


# ---------------------------------------------------------------- emit
def write(name, content):
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(content)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    files = {
        # marks
        "svg/mark.svg": mark_svg(C["green600"], "a"),
        "svg/mark-on-dark.svg": mark_svg(C["green300"], "b"),
        "svg/mark-small.svg": mark_svg(C["green600"], "c", drilled=False, small=True),
        "svg/mark-small-on-dark.svg": mark_svg(C["green300"], "c2", drilled=False, small=True),
        "svg/mark-mono.svg": mark_svg("currentColor", "d"),
        # app icon: green plane, ink substrate showing through the routed channel
        "svg/icon.svg": tile_svg(C["green600"], C["ink"], "e"),
        "svg/icon-inverse.svg": tile_svg(C["ink"], C["green300"], "f"),
        "svg/icon-small.svg": tile_svg(C["green600"], C["ink"], "g", drilled=False, small=True),
        "svg/favicon.svg": mark_svg(C["green600"], "fv", drilled=False, small=True),
        # wordmark
        "svg/wordmark.svg": wordmark_svg(C["ink"]),
        "svg/wordmark-on-dark.svg": wordmark_svg(C["paper"]),
        "svg/wordmark-green.svg": wordmark_svg(C["green600"]),
        # lockups
        "svg/lockup-horizontal.svg": lockup_h(C["green600"], C["ink"], "h"),
        "svg/lockup-horizontal-on-dark.svg": lockup_h(C["green300"], C["paper"], "i"),
        "svg/lockup-horizontal-mono.svg": lockup_h("currentColor", "currentColor", "j"),
        "svg/lockup-stacked.svg": lockup_stacked(C["green600"], C["ink"], "k"),
        "svg/lockup-stacked-on-dark.svg": lockup_stacked(C["green300"], C["paper"], "l"),
    }
    for name, content in files.items():
        write(name, content)
    print(f"wrote {len(files)} svg files")


if __name__ == "__main__":
    main()
