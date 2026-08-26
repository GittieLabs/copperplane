"""
Assembles a real Tauri updater manifest (SPEC-402, CTX-402.2) -- the exact
`latest.json` shape `tauri-plugin-updater` expects:
{version, notes, pub_date, platforms: {<platform-key>: {signature, url}}}.

CTX-402.4 added a real second macOS build leg (Intel, x86_64-apple-darwin,
matrix-built alongside the existing Apple Silicon leg) -- this generator
takes one or more --platform groups and folds them all into a single
manifest's platforms object, rather than assuming exactly one architecture
was ever built (CTX-402.1/.2/.3's own real, honest scope at the time).
CTX-402.5 added real, unsigned Windows/Linux pre-release legs on top.

Usage:
    python scripts/generate_update_manifest.py \
        --version v0.1.0 --pub-date 2026-08-16T21:00:00Z --notes-file notes.md \
        --platform aarch64-apple-darwin bundle/macos/aarch64.app.tar.gz.sig \
            https://github.com/.../Copperplane_aarch64.app.tar.gz \
        --platform x86_64-apple-darwin bundle/macos/x86_64.app.tar.gz.sig \
            https://github.com/.../Copperplane_x86_64.app.tar.gz
"""
import argparse
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Tauri v2's own real platform-key convention for latest.json -- "{os}-{arch}",
# where os is "darwin"/"windows"/"linux" (not "macos") and arch is
# "aarch64"/"x86_64" (not "arm64") -- confirmed directly against
# tauri-plugin-updater's own real source (updater_os()/updater_arch()/
# target() in updater.rs) at the exact version pinned in this repo's
# Cargo.lock (2.10.1), not assumed from documentation.
_TARGET_TRIPLE_TO_PLATFORM_KEY = {
    "aarch64-apple-darwin": "darwin-aarch64",
    "x86_64-apple-darwin": "darwin-x86_64",
    "x86_64-pc-windows-msvc": "windows-x86_64",
    "x86_64-unknown-linux-gnu": "linux-x86_64",
}


class UnknownTargetTripleError(Exception):
    """Raised for a target triple this generator has no real Tauri
    updater platform-key mapping for -- fails loudly rather than guessing
    at a key format that would silently produce an unusable manifest."""


def platform_key_for(target_triple: str) -> str:
    try:
        return _TARGET_TRIPLE_TO_PLATFORM_KEY[target_triple]
    except KeyError:
        raise UnknownTargetTripleError(
            f"No known Tauri updater platform key for target triple '{target_triple}'. "
            f"Known triples: {', '.join(sorted(_TARGET_TRIPLE_TO_PLATFORM_KEY))}."
        ) from None


def generate_manifest(version: str, pub_date: str, notes: str, platforms: list) -> dict:
    """`platforms` is a real list of (target_triple, signature, download_url)
    tuples -- one real, independently-signed artifact per architecture
    actually built, never fabricated for one that wasn't."""
    return {
        "version": version,
        "notes": notes,
        "pub_date": pub_date,
        "platforms": {
            platform_key_for(target_triple): {
                "signature": signature,
                "url": download_url,
            }
            for target_triple, signature, download_url in platforms
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', required=True, help="e.g. v0.1.0")
    parser.add_argument('--pub-date', required=True, help="ISO 8601 UTC timestamp, e.g. 2026-08-16T21:00:00Z")
    parser.add_argument('--notes-file', required=True)
    parser.add_argument(
        '--platform', dest='platforms', nargs=3, action='append', required=True,
        metavar=('TARGET_TRIPLE', 'SIGNATURE_FILE', 'DOWNLOAD_URL'),
        help="Repeatable -- one real, independently-built architecture's Tauri .sig file and its "
             "real GitHub Release asset download URL, e.g. --platform aarch64-apple-darwin "
             "bundle/macos/aarch64.app.tar.gz.sig https://github.com/.../aarch64.app.tar.gz",
    )
    args = parser.parse_args()

    with open(args.notes_file, encoding='utf-8') as f:
        notes = f.read()

    platforms = []
    for target_triple, signature_file, download_url in args.platforms:
        with open(signature_file, encoding='utf-8') as f:
            signature = f.read().strip()
        platforms.append((target_triple, signature, download_url))

    manifest = generate_manifest(args.version, args.pub_date, notes, platforms)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
