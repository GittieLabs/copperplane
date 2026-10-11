"""
Builds everything the compositor draws, from the real captures.

The page (`index.html`) only paints. Everything that needs the stills, OCR or
ffmpeg happens here, once, and lands in `build/` (gitignored, like the
captures it is made from):

*   **Base images**, the windows behind each pullout. Several show the
    maintainer's project path, which a dimmed window still lets a viewer read.
    Each one is redacted with `scripts/redact_screenshots.py`'s own functions,
    then OCR'd again. If the path is still readable, this stops rather than
    write an image that leaks it.
*   **Pullout crops** at the source's full Retina resolution.
*   **Highlight boxes**: where the highlighted phrase sits inside each crop,
    found by OCR, so the highlight sweep lands on the words and not near them.
*   **Clip frames**, extracted from the take's raw `display.mp4`, which has no
    pointer and none of Cap's padding.
*   **The brand lockup**, copied from `brand/png/`.

Run `python3 scripts/check_shotlist.py --captures` first; this trusts what it
checks.

Usage:
    python3 docs/video/studio/prepare.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'scripts'))

from PIL import Image  # noqa: E402

import redact_screenshots as redact  # noqa: E402

BUILD = os.path.join(HERE, 'build')
SHOTLIST = os.path.join(REPO_ROOT, 'docs', 'video', 'shotlist.json')
LOCKUP = os.path.join(REPO_ROOT, 'brand', 'png', 'lockup-stacked-on-dark-1200.png')
CLIP_FPS = 30

#: What a capture of this machine shows that must not reach a viewer.
SECRETS = ['keithelliott']


class PrepareError(Exception):
    pass


def tokens(text):
    return re.findall(r'[a-z0-9]+(?:\.[0-9]+)?', text.lower())


def ocr_words(image):
    """Word boxes from the best of several thresholds, in the image's own pixels."""
    grey = image.convert('L')
    doubled_size = (grey.width * 2, grey.height * 2)
    best = []
    for dark_text, cut in ((True, 128), (True, 170), (True, 200), (False, 45)):
        binary = grey.point((lambda p, c=cut: 0 if p < c else 255) if dark_text
                            else (lambda p, c=cut: 0 if p > c else 255)).resize(doubled_size, Image.LANCZOS)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as handle:
            binary.save(handle.name)
            path = handle.name
        try:
            out = subprocess.run(['tesseract', path, '-', '--psm', '6', 'tsv'],
                                 capture_output=True, text=True).stdout
        finally:
            os.unlink(path)
        words = []
        for row in out.splitlines()[1:]:
            c = row.split('\t')
            if len(c) < 12 or not c[11].strip():
                continue
            x, y, w, h = (int(v) // 2 for v in c[6:10])
            words.append({'text': c[11], 'box': [x, y, w, h], 'line': (c[2], c[3], c[4])})
        if len(words) > len(best):
            best = words
    return best


def highlight_boxes(image, phrase):
    """One rect per text line covering the phrase, in the crop's pixels.

    Matches the phrase's tokens against the OCR'd word sequence and takes the
    window with the most tokens in common. Raises when fewer than 70% match:
    a highlight in the wrong place is worse than none.
    """
    want = tokens(phrase)
    words = ocr_words(image)
    seq = [(i, t) for i, w in enumerate(words) for t in tokens(w['text'])]
    best, best_hits = None, 0
    for start in range(len(seq)):
        window = seq[start:start + len(want)]
        hits = sum(1 for (_, got), exp in zip(window, want) if got == exp)
        if hits > best_hits:
            best, best_hits = window, hits
    if not best or best_hits < 0.7 * len(want):
        raise PrepareError(f'could not find {phrase!r} in the crop (best match {best_hits}/{len(want)} words)')
    by_line = {}
    for i in sorted({i for i, _ in best}):
        x, y, w, h = words[i]['box']
        r = by_line.setdefault(words[i]['line'], [x, y, x + w, y + h])
        r[0], r[1], r[2], r[3] = min(r[0], x), min(r[1], y), max(r[2], x + w), max(r[3], y + h)
    return [[x0, y0, x1 - x0, y1 - y0] for x0, y0, x1, y1 in sorted(by_line.values(), key=lambda r: r[1])]


def redacted(path, out_path):
    """Redact every secret, then prove it is gone. Returns the output path."""
    image = Image.open(path)
    grey = image.convert('L')
    boxes, seen = [], 0
    for secret in SECRETS:
        found, seen = redact.find_boxes(grey, secret)
        boxes += found
    if seen < redact._MIN_WORDS_FOR_A_TRUSTWORTHY_NEGATIVE:
        raise PrepareError(f'OCR read only {seen} words in {path}; cannot say it is free of the path')
    out = redact.redact(image, boxes) if boxes else image
    out.save(out_path)
    again = Image.open(out_path).convert('L')
    for secret in SECRETS:
        left, _ = redact.find_boxes(again, secret)
        if left:
            raise PrepareError(f'{out_path} still shows {secret!r} after redaction')
    return out_path


def main():
    with open(SHOTLIST, encoding='utf-8') as f:
        shotlist = json.load(f)
    captures = os.path.join(REPO_ROOT, shotlist['captures_dir'])
    with open(os.path.join(captures, 'manifest.json'), encoding='utf-8') as f:
        manifest = {e['name']: e for e in json.load(f)}

    shutil.rmtree(BUILD, ignore_errors=True)
    os.makedirs(BUILD)
    data = {'images': {}, 'shots': {}}

    def base(name):
        if name not in data['images']:
            entry = manifest[name]
            out = redacted(os.path.join(captures, entry['file']), os.path.join(BUILD, f'base-{name}.png'))
            data['images'][name] = {'file': os.path.basename(out), 'pixels': entry['pixels']}
            print(f'base   {name}: redacted and re-checked', file=sys.stderr)
        return name

    for shot in shotlist['shots']:
        prepared = {'bases': [], 'pullouts': []}
        for name in ([shot['source']] if 'source' in shot else []) + shot.get('sources', []):
            prepared['bases'].append(base(name))
        for i, p in enumerate(shot.get('pullouts', [])):
            source = p.get('source', shot['source'])
            entry = manifest[source]
            x, y, w, h = p['crop']
            crop = Image.open(os.path.join(captures, entry['file'])).crop((x, y, x + w, y + h))
            file = f"pullout-{shot['id']}-{i}.png"
            crop.save(os.path.join(BUILD, file))
            boxes = highlight_boxes(crop, p['highlight'])
            prepared['pullouts'].append({'file': file, 'source': base(source), 'crop': p['crop'],
                                         'highlights': boxes, 'accent': p.get('accent', 'green'),
                                         'continues': bool(p.get('continues'))})
            print(f"pullout {shot['id']}[{i}]: highlight on {len(boxes)} line(s)", file=sys.stderr)
        if 'clip' in shot:
            c = shot['clip']
            video = os.path.join(captures, f"{c['take']}.cap", 'content', 'segments', 'segment-0', 'display.mp4')
            x, y, w, h = c['crop']
            pattern = os.path.join(BUILD, f"clip-{shot['id']}-%04d.png")
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(c['in']), '-to', str(c['out']), '-i', video,
                            '-vf', f'crop={w}:{h}:{x}:{y},fps={CLIP_FPS}', pattern], check=True)
            frames = sorted(f for f in os.listdir(BUILD) if f.startswith(f"clip-{shot['id']}-"))
            prepared['clip'] = {'frames': frames, 'fps': CLIP_FPS, 'pixels': [w, h]}
            print(f"clip   {shot['id']}: {len(frames)} frames", file=sys.stderr)
        data['shots'][shot['id']] = prepared

    shutil.copy(LOCKUP, os.path.join(BUILD, 'lockup.png'))
    data['lockup'] = 'lockup.png'
    shutil.copy(SHOTLIST, os.path.join(BUILD, 'shotlist.json'))
    with open(os.path.join(BUILD, 'data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    print(f'prepared {len(data["images"])} base images and {sum(len(s["pullouts"]) for s in data["shots"].values())} '
          f'pullouts into {os.path.relpath(BUILD, REPO_ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except PrepareError as e:
        print(f'error: {e}', file=sys.stderr)
        sys.exit(1)
