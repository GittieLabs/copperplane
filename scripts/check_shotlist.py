"""
Checks the product-video shot list (`docs/video/shotlist.json`) before a frame
is rendered from it.

The video script has been wrong about a number on screen twice, and the first
shoot for `CTX-408.7` found the app showing a board check from before the fix
it was meant to demonstrate. So the rule for this shot list is the one the
script states: every number in a caption is read off the captured frame it
comes from, never copied from the script. This makes that rule a check.

Two layers:

*   **Structural**, which runs anywhere, including CI:
    -   each cut's shots add up to its target length;
    -   captions fit a phone;
    -   no phrase from the script's "Lines to avoid";
    -   every caption stays on screen long enough to read in the cut it
        appears in;
    -   every reference resolves.
*   **Against the captures** (`--captures`), which needs the gitignored stills
    and Tesseract, so it runs on the machine that shot them:
    -   each source still is the one its manifest recorded (SHA-256);
    -   each crop lies inside its frame;
    -   every number in a checked caption appears in the OCR'd text of the
        crop it points at;
    -   no crop shows a file path.

    The number check proves the number is *on screen in that crop*, not that
    the caption uses it correctly. It catches a stale or invented figure (the
    0.15 mm the script once carried), not a misreading of a present one.

Usage:
    python3 scripts/check_shotlist.py [--captures]
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SHOTLIST = os.path.join(REPO_ROOT, 'docs', 'video', 'shotlist.json')

#: Characters per caption line that still read at phone width in a 9:16 frame.
MAX_CAPTION_CHARS = 42

#: From the script's "Lines to avoid", matched as whole words, case-insensitively.
BANNED = ['ai-powered', 'leverage', 'seamless', 'seamlessly', 'revolutionise', 'revolutionize',
          'simply', 'just', 'never make a mistake', 'replaces kicad']

#: Below this many OCR'd words in a crop, "number not found" would mean
#: "could not read" rather than "not there". Same idea as redact_screenshots.py.
MIN_OCR_WORDS = 6

_NUMBER = re.compile(r'\d+(?:\.\d+)?')


class ShotlistError(Exception):
    pass


# ---------------------------------------------------------------- pure checks

def reading_seconds(text):
    """Minimum time a caption must stay up. About 3.5 words a second, plus a beat."""
    return 0.6 + 0.28 * len(text.split())


def numbers_in(text):
    return [float(n) for n in _NUMBER.findall(text)]


def missing_numbers(caption, screen_text):
    """Numbers the caption states that do not appear in the screen text, compared as values."""
    on_screen = set(numbers_in(screen_text))
    return [n for n in numbers_in(caption) if n not in on_screen]


def banned_phrases(text):
    lowered = text.lower()
    return [b for b in BANNED if re.search(r'(?<![\w-])' + re.escape(b) + r'(?![\w-])', lowered)]


def crop_inside(crop, width, height):
    x, y, w, h = crop
    return x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= width and y + h <= height


def structural_problems(shotlist):
    problems = []
    cuts = shotlist['cuts']
    shots = shotlist['shots']
    ids = [s['id'] for s in shots]
    if len(ids) != len(set(ids)):
        problems.append('shot ids are not unique')

    for cut, spec in cuts.items():
        total = sum(s['duration'].get(cut, 0) for s in shots)
        if abs(total - spec['target_seconds']) > spec['tolerance']:
            problems.append(f"cut {cut}: shots add up to {total:g}s, target {spec['target_seconds']}s "
                            f"(tolerance {spec['tolerance']}s)")

    for s in shots:
        for cut in s['duration']:
            if cut not in cuts:
                problems.append(f"{s['id']}: duration for unknown cut {cut!r}")
        for c in s['captions']:
            text = c['text']
            if len(text) > MAX_CAPTION_CHARS:
                problems.append(f"{s['id']}: caption is {len(text)} chars, over {MAX_CAPTION_CHARS}: {text!r}")
            for b in banned_phrases(text):
                problems.append(f"{s['id']}: caption uses {b!r}, which the script says to avoid: {text!r}")
            for cut in c['cuts']:
                if cut not in s['duration']:
                    problems.append(f"{s['id']}: caption shown in cut {cut} but the shot is not in that cut: {text!r}")
            if 'verify' in c:
                kind, _, index = c['verify'].partition(':')
                pullouts = s.get('pullouts', [])
                if kind != 'pullout' or not index.isdigit() or int(index) >= len(pullouts):
                    problems.append(f"{s['id']}: caption verify {c['verify']!r} does not name a pullout")
            elif numbers_in(text):
                problems.append(f"{s['id']}: caption states a number but names no frame to check it against: {text!r}")
            if 'shows' in c:
                shows, pullouts = c['shows'], s.get('pullouts', [])
                if shows == 'clip':
                    if 'clip' not in s:
                        problems.append(f"{s['id']}: caption shows the clip but the shot has none: {text!r}")
                elif not isinstance(shows, int) or not 0 <= shows < len(pullouts):
                    problems.append(f"{s['id']}: caption shows {shows!r}, which names no pullout: {text!r}")
        for i, p in enumerate(s.get('pullouts', [])):
            if p.get('continues'):
                prev = s['pullouts'][i - 1] if i else None
                same_card = (prev is not None and prev['crop'] == p['crop']
                             and prev.get('source', s.get('source')) == p.get('source', s.get('source')))
                if not same_card:
                    problems.append(f"{s['id']}: pullout {i} continues a card it does not share: "
                                    f"it needs the same source and crop as pullout {i - 1}")
        for cut, seconds in s['duration'].items():
            needed = sum(reading_seconds(c['text']) for c in s['captions'] if cut in c['cuts'])
            if needed > seconds + 1e-9:
                problems.append(f"{s['id']}: cut {cut} gives {seconds:g}s but its captions need {needed:.2f}s to read")
        for p in s.get('pullouts', []):
            if len(p['crop']) != 4 or not all(isinstance(v, int) for v in p['crop']):
                problems.append(f"{s['id']}: crop {p['crop']} is not four integers")

    site = shotlist.get('site_url', '')
    for s in shots:
        for t in s.get('card_text', []):
            if '.' in t and '/' in t and not site.endswith(t):
                problems.append(f"{s['id']}: card shows {t!r}, which is not the site URL {site!r}")
    return problems


# ------------------------------------------------------- against the captures

def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def ocr_text(image_path, crop):
    """Words Tesseract reads in a crop, over several thresholds.

    One threshold misses some text entirely. On 2026-10-10 the orange
    "KiCad reports 4 design-rule violations" line read as nothing at the two
    thresholds redact_screenshots.py uses, which would have made its numbers
    look absent.
    """
    from PIL import Image
    x, y, w, h = crop
    grey = Image.open(image_path).convert('L').crop((x, y, x + w, y + h))
    grey = grey.resize((w * 2, h * 2), Image.LANCZOS)
    words = []
    for dark_text, cut in ((False, 45), (True, 128), (True, 170), (True, 200)):
        binary = grey.point((lambda p, c=cut: 0 if p < c else 255) if dark_text
                            else (lambda p, c=cut: 0 if p > c else 255))
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as handle:
            binary.save(handle.name)
            path = handle.name
        try:
            out = subprocess.run(['tesseract', path, '-', '--psm', '6'], capture_output=True, text=True).stdout
        finally:
            os.unlink(path)
        words.extend(out.split())
    return ' '.join(words)


def capture_problems(shotlist, repo_root=REPO_ROOT):
    problems = []
    captures = os.path.join(repo_root, shotlist['captures_dir'])
    manifest_path = os.path.join(captures, 'manifest.json')
    if not os.path.exists(manifest_path):
        return [f'no manifest at {manifest_path}; the captures are not on this machine']
    with open(manifest_path, encoding='utf-8') as f:
        manifest = {e['name']: e for e in json.load(f)}

    def frame(name, who):
        entry = manifest.get(name)
        if entry is None:
            problems.append(f'{who}: no capture named {name!r} in the manifest')
            return None
        path = os.path.join(captures, entry['file'])
        if not os.path.exists(path):
            problems.append(f'{who}: {path} is missing')
            return None
        if sha256_of(path) != entry['sha256']:
            problems.append(f'{who}: {name} has changed since it was captured (SHA-256 differs from the manifest)')
        return entry, path

    for s in shotlist['shots']:
        for name in ([s['source']] if 'source' in s else []) + s.get('sources', []):
            found = frame(name, s['id'])
            if found and 'base_crop' in s and name == s.get('source'):
                width, height = found[0]['pixels']
                if not crop_inside(s['base_crop'], width, height):
                    problems.append(f"{s['id']}: base_crop {s['base_crop']} is outside the {width}x{height} frame")
        texts = []
        for i, p in enumerate(s.get('pullouts', [])):
            found = frame(p.get('source', s.get('source')), f"{s['id']} pullout {i}")
            if not found:
                texts.append(None)
                continue
            entry, path = found
            width, height = entry['pixels']
            if not crop_inside(p['crop'], width, height):
                problems.append(f"{s['id']} pullout {i}: crop {p['crop']} is outside the {width}x{height} frame")
                texts.append(None)
                continue
            text = ocr_text(path, p['crop'])
            if '/Users/' in text or '/home/' in text:
                problems.append(f"{s['id']} pullout {i}: the crop shows a file path; redact or re-crop it")
            texts.append(text)
        for c in s['captions']:
            if 'verify' not in c:
                continue
            index = int(c['verify'].split(':')[1])
            text = texts[index] if index < len(texts) else None
            if text is None:
                continue
            if len(text.split()) < MIN_OCR_WORDS:
                problems.append(f"{s['id']}: OCR read only {len(text.split())} words in pullout {index}, "
                                f"too few to say a number is absent")
                continue
            missing = missing_numbers(c['text'], text)
            if missing:
                shown = ', '.join(f'{n:g}' for n in missing)
                problems.append(f"{s['id']}: caption {c['text']!r} states {shown}, "
                                f"which is not on screen in pullout {index}")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument('--shotlist', default=SHOTLIST)
    parser.add_argument('--captures', action='store_true',
                        help='also check against the captured stills (needs them, and Tesseract)')
    args = parser.parse_args(argv)
    with open(args.shotlist, encoding='utf-8') as f:
        shotlist = json.load(f)
    problems = structural_problems(shotlist)
    if args.captures:
        problems += capture_problems(shotlist)
    for p in problems:
        print(f'problem: {p}', file=sys.stderr)
    checked = 'structure and captures' if args.captures else 'structure'
    print(f"{len(shotlist['shots'])} shots, cuts {', '.join(shotlist['cuts'])}: "
          f"{'OK' if not problems else f'{len(problems)} problem(s)'} ({checked})")
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
