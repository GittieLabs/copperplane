"""
Fails loudly if a pushed release tag doesn't match the real version recorded
in BOTH core/tauri-rust/Cargo.toml and core/tauri-rust/tauri.conf.json
(SPEC-402, CTX-402.1) -- a real, easy human mistake (Cargo.toml bumped,
tauri.conf.json or the tag forgotten) this script exists specifically to
catch before a mismatched artifact gets published under a misleading
version number, not after.

Usage: python scripts/check_release_version.py v0.1.0
"""
import json
import re
import sys


class VersionMismatchError(Exception):
    """Raised when the tag doesn't match one or both real version sources."""


def cargo_toml_version(path: str = 'core/tauri-rust/Cargo.toml') -> str:
    with open(path, encoding='utf-8') as f:
        text = f.read()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise VersionMismatchError(f"No 'version = \"...\"' line found in {path}.")
    return match.group(1)


def tauri_conf_version(path: str = 'core/tauri-rust/tauri.conf.json') -> str:
    with open(path, encoding='utf-8') as f:
        conf = json.load(f)
    version = conf.get('version')
    if not version:
        raise VersionMismatchError(f"No top-level 'version' field found in {path}.")
    return version


def check_tag_matches(tag: str) -> None:
    """Raises VersionMismatchError naming exactly which source(s)
    disagree, rather than a bare pass/fail -- the whole point of this
    check is a clear, actionable CI failure message."""
    tag_version = tag[1:] if tag.startswith('v') else tag
    cargo_version = cargo_toml_version()
    tauri_version = tauri_conf_version()

    mismatches = []
    if tag_version != cargo_version:
        mismatches.append(f"Cargo.toml has '{cargo_version}'")
    if tag_version != tauri_version:
        mismatches.append(f"tauri.conf.json has '{tauri_version}'")

    if mismatches:
        raise VersionMismatchError(
            f"Tag '{tag}' (version '{tag_version}') does not match: " + "; ".join(mismatches) + "."
        )


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_release_version.py <tag>", file=sys.stderr)
        sys.exit(2)

    try:
        check_tag_matches(sys.argv[1])
    except VersionMismatchError as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: tag '{sys.argv[1]}' matches Cargo.toml and tauri.conf.json.")


if __name__ == '__main__':
    main()
