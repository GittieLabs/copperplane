"""
Blurs a personal file path out of app screenshots, and proves it worked.

Copperplane shows absolute paths in its project header, its Settings screen
and its schematic picker. On the maintainer's machine those read
`/Users/<name>/repos/...`, and documentation screenshots therefore carry a
username into a public site. Editing 40 images by hand is the kind of chore
that gets skipped once and then ships.

Why OCR rather than fixed coordinates: the path appears at a different place
in every screen, and at different sizes. Tesseract locates the text; Pillow
covers it.

Two details that were not obvious and cost a while to find:

*   Tesseract reads **nothing at all** from these screenshots as-is. The app
    is dark-first, and light-grey text on near-black defeats it completely --
    not degraded output, zero words. Thresholding to black-on-white first
    fixes it. Inverting alone is not enough: the muted text is `#737373` on
    `#0a0a0a`, which inverts to low-contrast grey on white and stays
    unreadable.
*   Both polarities are tried, because a walkthrough contains light-theme and
    dark-theme shots and deciding which is which per file is more work than
    running the OCR twice.

The redaction is pixelate-then-blur rather than a Gaussian alone: a Gaussian
over 11px text can leave letter shapes a determined reader recovers.

Usage:
    python scripts/redact_screenshots.py <dir> [--secret NAME] [--out DIRNAME]
"""
import argparse
import os
import subprocess
import sys
import tempfile

try:
    from PIL import Image, ImageFilter
except ImportError:
    sys.exit("this needs Pillow: pip install Pillow")

#: Below this, OCR did not really read the image, and "no match" would mean
#: "could not look" rather than "nothing there" -- a check that cannot fail.
_MIN_WORDS_FOR_A_TRUSTWORTHY_NEGATIVE = 25

_LIGHT_TEXT_THRESHOLD = 45
_DARK_TEXT_THRESHOLD = 128


def _binarise(grey, invert):
    if invert:
        return grey.point(lambda p: 0 if p < _DARK_TEXT_THRESHOLD else 255)
    return grey.point(lambda p: 0 if p > _LIGHT_TEXT_THRESHOLD else 255)


def _tsv(image):
    """Tesseract's word table for an already-binarised, upscaled image."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        image.save(handle.name)
        path = handle.name
    try:
        return subprocess.run(
            ["tesseract", path, "-", "--psm", "6", "tsv"],
            capture_output=True, text=True,
        ).stdout
    finally:
        os.unlink(path)


def find_boxes(grey, secret):
    """Every word box containing `secret`, in original-image pixels."""
    boxes, words_seen = [], 0
    for invert in (False, True):
        doubled = _binarise(grey, invert).resize(
            (grey.width * 2, grey.height * 2), Image.LANCZOS
        )
        for row in _tsv(doubled).splitlines()[1:]:
            cols = row.split("\t")
            if len(cols) < 12 or not cols[11].strip():
                continue
            words_seen += 1
            if secret.lower() in cols[11].lower():
                boxes.append(tuple(int(cols[i]) // 2 for i in (6, 7, 8, 9)))
    return boxes, words_seen


def redact(image, boxes, pad=4):
    out = image.convert("RGB")
    for x, y, w, h in boxes:
        box = (max(0, x - pad), max(0, y - pad),
               min(out.width, x + w + pad), min(out.height, y + h + pad))
        region = out.crop(box)
        pixelated = region.resize(
            (max(1, region.width // 12), max(1, region.height // 6)), Image.BILINEAR
        ).resize(region.size, Image.NEAREST)
        out.paste(pixelated.filter(ImageFilter.GaussianBlur(3)), box)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory")
    parser.add_argument("--secret", default=os.environ.get("USER", ""),
                        help="the string to blur out (default: $USER)")
    parser.add_argument("--out", default="redacted", help="subdirectory to write into")
    args = parser.parse_args()

    if not args.secret:
        sys.exit("no --secret given and $USER is empty")

    out_dir = os.path.join(args.directory, args.out)
    os.makedirs(out_dir, exist_ok=True)

    names = sorted(n for n in os.listdir(args.directory) if n.lower().endswith(".png"))
    redacted, untouched, leaking, unreadable = 0, 0, [], []

    for name in names:
        source = Image.open(os.path.join(args.directory, name))
        boxes, words = find_boxes(source.convert("L"), args.secret)
        target = os.path.join(out_dir, name)

        if not boxes:
            source.save(target)
            untouched += 1
            if words < _MIN_WORDS_FOR_A_TRUSTWORTHY_NEGATIVE:
                unreadable.append((name, words))
            continue

        redact(source, boxes).save(target)
        redacted += 1

        # Read the result back. Without this the script reports success for
        # a blur that landed in the wrong place.
        again, _ = find_boxes(Image.open(target).convert("L"), args.secret)
        if again:
            leaking.append(name)

    print(f"images:        {len(names)}")
    print(f"redacted:      {redacted}")
    print(f"nothing found: {untouched}")

    if unreadable:
        print(f"\nOCR barely read these, so 'nothing found' is not trustworthy -- check by eye:")
        for name, words in unreadable:
            print(f"  {words:4d} words  {name}")
    if leaking:
        print(f"\nSTILL CONTAIN THE STRING AFTER REDACTION:")
        for name in leaking:
            print(f"  {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
