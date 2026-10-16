"""
Review sheets for one rendered cut, for the critique loop (CTX-408.7 Phase 5).

*   `<name>-phone.png`: the frame in the middle of every caption, at 360 px
    wide. That is the moment a viewer is reading, at the size they read it.
*   `<name>-contact.png`: one frame every half second, sampled by **time**
    (Cap's raw takes taught this: frame-indexed sampling misses still stretches).

*   `<name>-strip-<t0>.png` (with `--strip T0 T1`): every frame at 15 fps from
    T0 to T1. Still frames miss a flash that lasts a fifth of a second; a strip
    catches it. Rigovera's port found one this way on 2026-10-16: a faded
    highlight snapping back at full strength while its spring rang.

Usage: python3 docs/video/studio/sheets.py out/cut-15-9x16.mp4 [width]
       python3 docs/video/studio/sheets.py out/cut-15-9x16.mp4 --strip 6.0 8.6

Width defaults to 360 (a phone). LinkedIn's feed is about 390 on mobile and
555 on desktop.
"""
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw


def frame_at(video, t, width):
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as h:
        path = h.name
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', video, '-frames:v', '1',
                    '-vf', f'scale={width}:-1', path], check=True)
    im = Image.open(path).convert('RGB')
    os.unlink(path)
    return im


def main(video, width=360):
    base = video[:-4]
    timeline = json.load(open(base + '.timeline.json'))
    caps = [(s['id'], c) for s in timeline for c in s['captions']]
    tiles = []
    for sid, c in caps:
        im = frame_at(video, (c['start'] + c['end']) / 2, width)
        label = Image.new('RGB', (im.width, 34), (40, 40, 40))
        ImageDraw.Draw(label).text((6, 10), f"{(c['start'] + c['end']) / 2:5.2f}s {sid[:22]}", fill=(220, 220, 220))
        tile = Image.new('RGB', (im.width, im.height + 34))
        tile.paste(label, (0, 0)); tile.paste(im, (0, 34))
        tiles.append(tile)
    cols = min(6, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    w, h = tiles[0].size
    sheet = Image.new('RGB', (cols * (w + 8), rows * (h + 8)), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * (w + 8), (i // cols) * (h + 8)))
    sheet.save(base + f'-phone{"" if width == 360 else f"-{width}"}.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-vf', 'fps=2,scale=240:-1,tile=8x8',
                    '-frames:v', '1', base + '-contact.png'], check=True)
    print(f'{base}-phone{"" if width == 360 else f"-{width}"}.png ({len(tiles)} captions at {width} px), {base}-contact.png')


def strip(video, t0, t1, fps=15, width=180):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t0:.3f}', '-i', video, '-t', f'{t1 - t0:.3f}',
                        '-vf', f'fps={fps},scale={width}:-1', os.path.join(d, '%04d.png')], check=True)
        frames = [Image.open(os.path.join(d, f)).convert('RGB') for f in sorted(os.listdir(d))]
    tiles = []
    for i, im in enumerate(frames):
        tile = Image.new('RGB', (im.width, im.height + 18), (40, 40, 40))
        ImageDraw.Draw(tile).text((4, 4), f'{t0 + i / fps:6.2f}s', fill=(220, 220, 220))
        tile.paste(im, (0, 18))
        tiles.append(tile)
    cols = min(10, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    w, h = tiles[0].size
    sheet = Image.new('RGB', (cols * (w + 4), rows * (h + 4)), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * (w + 4), (i // cols) * (h + 4)))
    out = f'{video[:-4]}-strip-{t0:.2f}.png'
    sheet.save(out)
    print(f'{out} ({len(tiles)} frames at {fps} fps)')


if __name__ == '__main__':
    if '--strip' in sys.argv:
        i = sys.argv.index('--strip')
        strip(sys.argv[1], float(sys.argv[i + 1]), float(sys.argv[i + 2]))
    else:
        main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 360)
