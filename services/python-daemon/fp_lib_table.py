"""
SPEC-308/CTX-308.1: real, installed KiCad footprint-library search.

kipy's live IPC connection has no footprint-library-search capability at
all -- confirmed directly against kipy 0.7.1's own source (every class in
kipy.kicad/board/project, every proto command message), not assumed. This
module bypasses kicad_bridge.py's IPC pattern entirely and reads KiCad's
own fp-lib-table config file plus real .pretty directories on disk.

Scope, deliberate: only direct (type "KiCad") fp-lib-table entries are
resolved here. A (type "Table") entry recursively points to another
fp-lib-table file (KiCad's own ~100+ built-in libraries, each using a
${KICAD<N>_FOOTPRINT_DIR}-style placeholder) -- real, separate work,
explicitly deferred to CTX-308.2, not attempted here.
"""
from __future__ import annotations

import glob
import logging
import os
import platform
import re

logger = logging.getLogger(__name__)

_LIB_ENTRY_RE = re.compile(
    r'\(lib\s+\(name\s+"([^"]*)"\)\s+\(type\s+"([^"]*)"\)\s+\(uri\s+"([^"]*)"\)',
)


class FpLibTableNotFoundError(Exception):
    """Raised when no fp-lib-table config file can be found -- a
    different failure mode from kicad_bridge.KiCadUnavailableError, which
    is specifically about the live IPC connection, not this module's
    filesystem-only concern."""


def _version_sort_key(version_dir_name: str) -> tuple:
    """Parses a KiCad config version directory name (e.g. "10.0") into a
    sortable tuple of ints, so "10.0" correctly sorts after "9.0" -- a
    plain string sort would put "10.0" first."""
    parts = []
    for piece in version_dir_name.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def default_fp_lib_table_path() -> str | None:
    """The real, per-OS global fp-lib-table path, or None if no KiCad
    config directory exists at all. Picks the highest-versioned config
    directory if more than one is present (e.g. a prior KiCad version's
    leftover config alongside a current one).

    macOS verified directly against a real, currently-installed KiCad
    10.0.3 (~/Library/Preferences/kicad/10.0/fp-lib-table). Windows/Linux
    paths follow KiCad's own documented convention but are NOT verified
    against a real machine this session -- named honestly, not assumed."""
    system = platform.system()
    if system == "Darwin":
        config_root = os.path.expanduser("~/Library/Preferences/kicad")
    elif system == "Windows":
        config_root = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "kicad")
    else:
        config_root = os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "kicad",
        )

    candidates = [
        d for d in glob.glob(os.path.join(config_root, "*"))
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "fp-lib-table"))
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda d: _version_sort_key(os.path.basename(d)), reverse=True)
    return os.path.join(candidates[0], "fp-lib-table")


def parse_fp_lib_table(path: str) -> list[dict]:
    """Real, deliberately minimal parser for KiCad's fp-lib-table format
    -- verified directly against this machine's own real file, not a
    generic S-expression parser (the format is flat, one (lib ...) entry
    per real-world line, and neither kipy nor anything already pinned in
    requirements.txt parses S-expressions generically).

    A (type "Table") entry is recognized and skipped with a logged
    warning, not silently dropped and not a crash -- see this module's
    own docstring for why that's this context's deliberate scope, not an
    oversight."""
    if not os.path.isfile(path):
        raise FpLibTableNotFoundError(f"No fp-lib-table found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    for match in _LIB_ENTRY_RE.finditer(content):
        name, lib_type, uri = match.group(1), match.group(2), match.group(3)
        if lib_type == "Table":
            logger.info(
                "fp-lib-table entry %r is a nested Table (uri=%r) -- skipped, "
                "CTX-308.1's own scope covers direct entries only.", name, uri,
            )
            continue
        entries.append({"name": name, "type": lib_type, "uri": uri})
    return entries


def list_footprint_names(pretty_dir_path: str) -> list[str]:
    """Real .kicad_mod filenames (stem only) in a real directory. A
    missing/moved directory -- a stale fp-lib-table entry -- logs a
    warning and returns an empty list for that one library, rather than
    raising and taking every other configured library's search down with
    it."""
    if not os.path.isdir(pretty_dir_path):
        logger.warning("fp-lib-table entry points at a missing directory: %r", pretty_dir_path)
        return []

    names = []
    for entry in os.scandir(pretty_dir_path):
        if entry.is_file() and entry.name.endswith(".kicad_mod"):
            names.append(entry.name[: -len(".kicad_mod")])
    return names


def search_footprints(query: str, fp_lib_table_path: str | None = None) -> list[dict]:
    """Case-insensitive substring search for a footprint name across
    every direct-entry library in the real fp-lib-table. Returns
    [{"library": <lib name>, "footprint_name": ...}, ...]."""
    path = fp_lib_table_path if fp_lib_table_path is not None else default_fp_lib_table_path()
    if path is None:
        raise FpLibTableNotFoundError("No KiCad config directory found on this machine.")

    entries = parse_fp_lib_table(path)
    query_lower = query.lower()

    results = []
    for entry in entries:
        for footprint_name in list_footprint_names(entry["uri"]):
            if query_lower in footprint_name.lower():
                results.append({"library": entry["name"], "footprint_name": footprint_name})
    return results
