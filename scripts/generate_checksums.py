"""
Writes a real SHA-256 manifest for the installers a release publishes
(SPEC-402, CTX-402.8), in the exact format `sha256sum -c` (Linux) and
`shasum -a 256 -c` (macOS) read back:

    <64 hex chars><two spaces><basename>

Why this exists: the Windows and Linux builds are unsigned (CTX-402.5 --
still a real Non-Goal in SPEC-402 §1), so a person downloading
`Copperplane_x64-setup.exe` has nothing to compare it against. Windows
SmartScreen will warn them, correctly, that the publisher is unknown.
A checksum does not fix that -- see the honest scope note below -- but it
does let them prove the bytes they got are the bytes CI built, which is
the part a truncated download or a bad mirror actually breaks.

Honest scope: this manifest is published to the same GitHub release as the
files it describes. It therefore proves *integrity* (your download is not
corrupt, truncated, or a different file than the one CI produced) and NOT
*authenticity* against someone who could rewrite the release itself. It is
not a substitute for code signing, and the docs must not claim it is.

Only the installers a human downloads are hashed. Updater payloads
(`.app.tar.gz`) and `latest.json` are deliberately excluded: those already
carry a real Ed25519 signature that `tauri-plugin-updater` verifies before
installing anything (CTX-402.2), which is strictly stronger than a hash
published alongside the file.

Usage:
    python scripts/generate_checksums.py artifacts/ > SHA256SUMS.txt
"""
import argparse
import hashlib
import sys
from pathlib import Path

# newline='\n' is not incidental. On Windows, text-mode output translates \n to
# \r\n, and `sha256sum -c` then looks for a file whose name ends in a carriage
# return -- it reports "No such file or directory" for every entry in a manifest
# that is otherwise perfectly correct. The publish job runs on macOS today, so
# this would not have shown up in a real release; the windows-latest test leg
# found it. A checksum manifest is a wire format, and it gets LF everywhere.
sys.stdout.reconfigure(encoding='utf-8', newline='\n')

# Every installer format this repo's release workflow actually publishes
# for a human to download. Kept in step with the `files:` list in
# .github/workflows/release.yml by a real parity test
# (tests/test_release_checksums.py) -- an artifact type added to the
# release but not to this set would otherwise be published with no
# checksum line and nothing would say so.
INSTALLER_EXTENSIONS = ('.dmg', '.msi', '.exe', '.deb', '.AppImage')

# 1 MiB. These are 50-160 MB installers; reading one into memory whole is
# pointless when hashlib is happy to be fed in chunks.
_CHUNK_BYTES = 1024 * 1024


class NoInstallersFoundError(Exception):
    """Raised when a search finds nothing to hash.

    A checksum manifest that is silently empty is worse than none at all:
    it publishes a file named SHA256SUMS.txt that verifies nothing, and
    `sha256sum -c` on it reports success having checked zero files. Fail
    the release instead.
    """


class DuplicateBasenameError(Exception):
    """Raised when two artifacts in different directories share a filename.

    The manifest records basenames, because that is what a person has
    after downloading files into one folder. Two different files claiming
    the same basename would produce a manifest where one line is
    guaranteed wrong, with nothing to indicate which.
    """


def sha256_of(path):
    """Real SHA-256 of a real file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b''):
            digest.update(chunk)
    return digest.hexdigest()


def find_installers(roots):
    """Every installer under `roots`, sorted by basename.

    Sorted so the manifest is byte-identical for the same set of inputs
    regardless of the order the build legs' artifacts happened to be
    downloaded in -- a release artifact that changes for no reason is a
    release artifact nobody trusts.
    """
    found = []
    for root in roots:
        root = Path(root)
        if root.is_file():
            candidates = [root]
        else:
            candidates = sorted(p for p in root.rglob('*') if p.is_file())
        for path in candidates:
            if path.name.endswith(INSTALLER_EXTENSIONS):
                found.append(path)

    if not found:
        raise NoInstallersFoundError(
            f"no files matching {', '.join(INSTALLER_EXTENSIONS)} found under: "
            f"{', '.join(str(r) for r in roots)}"
        )

    by_name = {}
    for path in found:
        if path.name in by_name:
            raise DuplicateBasenameError(
                f"two artifacts share the basename {path.name!r}: "
                f"{by_name[path.name]} and {path}"
            )
        by_name[path.name] = path

    return [by_name[name] for name in sorted(by_name)]


def render(paths):
    """The manifest text. Two spaces between hash and name is not
    cosmetic -- it is what coreutils writes for binary mode and what its
    own parser expects to read back."""
    return ''.join(f"{sha256_of(path)}  {path.name}\n" for path in paths)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'roots', nargs='+',
        help="directories to search (recursively) or individual files to hash",
    )
    args = parser.parse_args()

    try:
        sys.stdout.write(render(find_installers(args.roots)))
    except (NoInstallersFoundError, DuplicateBasenameError) as exc:
        print(f"generate_checksums: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
