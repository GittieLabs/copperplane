#!/usr/bin/env python3
"""Rasterise the SVGs to PNG at real pixel sizes, with transparency preserved."""
import os
import re
from playwright.sync_api import sync_playwright

# Resolved from this file's own location, so the generator runs wherever the
# repository is checked out. It was hardcoded to /home/claude/copperplane/brand
# -- the machine it was written on -- which meant brand/README.md documented two
# commands that could not run anywhere else, and the kit could not be
# regenerated at all.
BRAND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(BRAND, "svg")
PNG = os.path.join(BRAND, "png")
os.makedirs(PNG, exist_ok=True)

# (source svg, output basename, [pixel sizes by WIDTH or HEIGHT], dimension)
JOBS = [
    ("icon.svg", "icon", [1024, 512, 256, 128, 64, 32], "square"),
    ("icon-small.svg", "icon-small", [20, 16], "square"),
    ("favicon.svg", "favicon", [64, 32, 16], "square"),
    ("mark-small.svg", "mark-small", [64, 32], "square"),
    ("icon-inverse.svg", "icon-inverse", [1024, 512, 256], "square"),
    ("mark.svg", "mark", [512, 256, 128, 64], "square"),
    ("mark-on-dark.svg", "mark-on-dark", [512, 256], "square"),
    ("lockup-horizontal.svg", "lockup-horizontal", [1600, 800], "width"),
    ("lockup-horizontal-on-dark.svg", "lockup-horizontal-on-dark", [1600, 800], "width"),
    ("lockup-stacked.svg", "lockup-stacked", [1200, 600], "width"),
    ("lockup-stacked-on-dark.svg", "lockup-stacked-on-dark", [1200, 600], "width"),
    ("wordmark.svg", "wordmark", [1600], "width"),
    ("wordmark-on-dark.svg", "wordmark-on-dark", [1600], "width"),
]


def viewbox(path):
    m = re.search(r'viewBox="([\d.\- ]+)"', open(path).read())
    _, _, w, h = (float(v) for v in m.group(1).split())
    return w, h


def main():
    made = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for src, base, sizes, mode in JOBS:
            path = os.path.join(SVG, src)
            vw, vh = viewbox(path)
            svg = open(path).read()
            for s in sizes:
                if mode == "square":
                    w = h = s
                else:
                    w, h = s, round(s * vh / vw)
                sized = re.sub(r'width="[\d.]+" height="[\d.]+"',
                               f'width="{w}" height="{h}"', svg, count=1)
                html = (f'<!doctype html><style>html,body{{margin:0;background:transparent}}'
                        f'svg{{display:block}}</style>{sized}')
                tmp = f"/tmp/_r.html"
                open(tmp, "w").write(html)
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto("file://" + tmp)
                out = os.path.join(PNG, f"{base}-{w}.png" if len(sizes) > 1 else f"{base}.png")
                page.screenshot(path=out, omit_background=True)
                page.close()
                made.append(out)
        browser.close()
    print(f"rendered {len(made)} png files")


if __name__ == "__main__":
    main()
