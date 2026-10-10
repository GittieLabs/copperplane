"""
Captures one still of the Copperplane window, and records where it came from.

Written for the product video (`CTX-408.7`). Every still is captured with
`screencapture -l <window id>`, which returns the window's own pixels even when
other windows cover it. That is why stills, unlike Cap's video takes, need
nobody to clear the screen.

A still on its own is not enough. This script has been wrong about a number
on screen twice, and the probe for this context found the app showing a
16-day-old board check that predated the fix it was meant to demonstrate. So
every capture is appended to a manifest with:

*   the file's SHA-256, so a later edit or re-capture is visible;
*   the window bounds, because pullout crop rectangles are in these pixels;
*   **which build was on screen**: the app bundle's path, its core binary's
    modification time, and the frozen sidecar's SHA-1. A bundle's version
    string cannot tell two local builds apart. Here both still read 0.4.0.

Captures go to `video-captures/<session>/`, which is gitignored. Raw captures
are never committed (see `.gitignore`), and they can show a file path until
`scripts/redact_screenshots.py` has been run over them.

Usage (macOS only):
    python3 scripts/capture_still.py <session> <name> [--note TEXT] [--window-id N]
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CAPTURE_ROOT = os.path.join(REPO_ROOT, 'video-captures')
APP_BUNDLE = os.path.join(
    REPO_ROOT, 'core', 'tauri-rust', 'target', 'release', 'bundle', 'macos', 'Copperplane.app')

# Lists every on-screen window owned by "Copperplane", largest first. Swift is
# used because it ships with the Xcode command-line tools and reaches
# CoreGraphics directly. Python would need pyobjc, which is not installed here.
_FIND_WINDOW_SWIFT = r'''
import CoreGraphics
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as! [[String: Any]]
for w in list where (w["kCGWindowOwnerName"] as? String) == "Copperplane"
    && (w["kCGWindowLayer"] as? Int) == 0 {
  let b = w["kCGWindowBounds"] as! [String: Any]
  print(w["kCGWindowNumber"]!, b["Width"]!, b["Height"]!)
}
'''


class CaptureError(Exception):
    pass


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def sha1_of(path):
    digest = hashlib.sha1()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build_identity(bundle_path):
    """What build is on screen, in terms that differ between two local builds."""
    macos_dir = os.path.join(bundle_path, 'Contents', 'MacOS')
    core = os.path.join(macos_dir, 'copperplane-core')
    sidecar = os.path.join(macos_dir, 'hardware-agent-studio-daemon')
    if not os.path.exists(core) or not os.path.exists(sidecar):
        raise CaptureError(f'no built app at {bundle_path}; build it first (CONTRIBUTING.md, Tier 2)')
    built = datetime.datetime.fromtimestamp(os.path.getmtime(core), datetime.timezone.utc)
    return {
        'app_bundle': os.path.relpath(bundle_path, REPO_ROOT),
        'core_built_at': built.isoformat(timespec='seconds'),
        'sidecar_sha1': sha1_of(sidecar),
    }


def manifest_entry(name, file_name, file_sha256, width_px, height_px, build, note, captured_at):
    """One manifest row. Pure, so it can be tested on any platform."""
    if not name or os.sep in name or name.startswith('.'):
        raise CaptureError(f'capture name must be a plain file stem, got {name!r}')
    return {
        'name': name,
        'file': file_name,
        'sha256': file_sha256,
        'pixels': [width_px, height_px],
        'captured_at': captured_at,
        'build': build,
        'note': note or '',
    }


def append_to_manifest(manifest_path, entry):
    """Adds an entry. Refuses a duplicate name rather than overwrite a capture."""
    entries = []
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            entries = json.load(f)
    if any(e['name'] == entry['name'] for e in entries):
        raise CaptureError(f"a capture named {entry['name']!r} already exists in {manifest_path}")
    entries.append(entry)
    with open(manifest_path, 'w') as f:
        json.dump(entries, f, indent=2)
        f.write('\n')
    return entries


def find_window_id():
    out = subprocess.run(['swift', '-e', _FIND_WINDOW_SWIFT], capture_output=True, text=True, check=True).stdout
    windows = [tuple(int(float(v)) for v in line.split()) for line in out.splitlines() if line.strip()]
    if not windows:
        raise CaptureError('no on-screen Copperplane window found; is the app running?')
    windows.sort(key=lambda w: w[1] * w[2], reverse=True)
    return windows[0][0]


def png_size(path):
    with open(path, 'rb') as f:
        header = f.read(24)
    return int.from_bytes(header[16:20], 'big'), int.from_bytes(header[20:24], 'big')


def capture(session, name, note='', window_id=None):
    session_dir = os.path.join(CAPTURE_ROOT, session)
    os.makedirs(session_dir, exist_ok=True)
    out_path = os.path.join(session_dir, f'{name}.png')
    if os.path.exists(out_path):
        raise CaptureError(f'{out_path} already exists; pick a new name rather than overwrite a capture')
    build = build_identity(APP_BUNDLE)
    window_id = window_id or find_window_id()
    subprocess.run(['screencapture', '-x', '-o', f'-l{window_id}', out_path], check=True)
    width, height = png_size(out_path)
    entry = manifest_entry(
        name, os.path.basename(out_path), sha256_of(out_path), width, height, build, note,
        datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'))
    append_to_manifest(os.path.join(session_dir, 'manifest.json'), entry)
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument('session')
    parser.add_argument('name')
    parser.add_argument('--note', default='')
    parser.add_argument('--window-id', type=int)
    args = parser.parse_args(argv)
    try:
        entry = capture(args.session, args.name, args.note, args.window_id)
    except CaptureError as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    print(json.dumps(entry))
    return 0


if __name__ == '__main__':
    sys.exit(main())
