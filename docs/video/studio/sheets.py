"""
Review sheets for one rendered cut, for the critique loop (CTX-408.7 Phase 5).

*   `<name>-phone.png`: the frame in the middle of every caption, at 360 px
    wide. That is the moment a viewer is reading, at the size they read it.
*   `<name>-contact.png`: one frame every half second, sampled by **time**
    (Cap's raw takes taught this: frame-indexed sampling misses still stretches).

Usage: python3 docs/video/studio/sheets.py out/cut-15-9x16.mp4
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


def main(video):
    base = video[:-4]
    timeline = json.load(open(base + '.timeline.json'))
    caps = [(s['id'], c) for s in timeline for c in s['captions']]
    tiles = []
    for sid, c in caps:
        im = frame_at(video, (c['start'] + c['end']) / 2, 360)
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
    sheet.save(base + '-phone.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-vf', 'fps=2,scale=240:-1,tile=8x8',
                    '-frames:v', '1', base + '-contact.png'], check=True)
    print(f'{base}-phone.png ({len(tiles)} captions), {base}-contact.png')


if __name__ == '__main__':
    main(sys.argv[1])
