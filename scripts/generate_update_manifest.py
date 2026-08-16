"""
Assembles a real Tauri updater manifest (SPEC-402, CTX-402.2) -- the exact
`latest.json` shape `tauri-plugin-updater` expects:
{version, notes, pub_date, platforms: {<platform-key>: {signature, url}}}.

This repo's own release pipeline only ever builds for the CI runner's
single native macOS architecture (CTX-401.2's own established, real scope
-- no universal binary), so the generated manifest always carries exactly
one platform key. A real, honest, pre-existing limitation, not something
this script hides: users on the other macOS architecture get no update
entry at all until a universal build exists.

Usage:
    python scripts/generate_update_manifest.py \
        --version v0.1.0 --pub-date 2026-08-16T21:00:00Z \
        --notes-file notes.md --target-triple aarch64-apple-darwin \
        --signature-file bundle/macos/hardware-agent-studio.app.tar.gz.sig \
        --download-url https://github.com/.../hardware-agent-studio.app.tar.gz
"""
import argparse
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Tauri v2's own real platform-key convention for latest.json -- "darwin"
# (not "macos"), and "aarch64" (not "arm64"), confirmed against the
# updater plugin's own documented manifest format.
_TARGET_TRIPLE_TO_PLATFORM_KEY = {
    "aarch64-apple-darwin": "darwin-aarch64",
    "x86_64-apple-darwin": "darwin-x86_64",
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


def generate_manifest(version: str, pub_date: str, notes: str, target_triple: str,
                       signature: str, download_url: str) -> dict:
    return {
        "version": version,
        "notes": notes,
        "pub_date": pub_date,
        "platforms": {
            platform_key_for(target_triple): {
                "signature": signature,
                "url": download_url,
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', required=True, help="e.g. v0.1.0")
    parser.add_argument('--pub-date', required=True, help="ISO 8601 UTC timestamp, e.g. 2026-08-16T21:00:00Z")
    parser.add_argument('--notes-file', required=True)
    parser.add_argument('--target-triple', required=True, help="e.g. aarch64-apple-darwin")
    parser.add_argument('--signature-file', required=True, help="Tauri's own real .sig output file")
    parser.add_argument('--download-url', required=True, help="The real GitHub Release asset URL for the .app.tar.gz")
    args = parser.parse_args()

    with open(args.notes_file, encoding='utf-8') as f:
        notes = f.read()
    with open(args.signature_file, encoding='utf-8') as f:
        signature = f.read().strip()

    manifest = generate_manifest(
        args.version, args.pub_date, notes, args.target_triple, signature, args.download_url,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
