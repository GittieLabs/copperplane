"""
Real ERC/DRC via KiCad's own `kicad-cli` binary (SPEC-309). Live IPC has
no check-and-report RPC at all -- confirmed by grepping kipy's installed
proto definitions before writing this: the only DRC-shaped RPC anywhere
in the protocol is `InjectDrcError`, a test utility for injecting a fake
marker, not a real "run the check" capability. `kicad-cli` is the real
tool KiCad itself ships for this, so this module shells out to it,
mirroring `freecad_bridge.py`'s own subprocess/binary-location pattern
for `freecadcmd` rather than inventing a second one.
"""
import glob
import json
import os
import platform
import shutil
import subprocess
import tempfile


class KicadCliUnavailableError(Exception):
    """Raised when the `kicad-cli` executable can't be located."""


class KicadCliError(Exception):
    """Raised when `kicad-cli` fails to produce a report at all (a
    missing/malformed input file, a crash) -- distinct from a real report
    that simply lists violations, which is a normal, successful result,
    not an error."""


# Standard per-OS install locations to fall back to if `kicad-cli` isn't
# on PATH, mirroring freecad_bridge._CANDIDATE_GLOBS's own real,
# confirmed-working pattern. The macOS path is the one actually verified
# on this machine (SPEC-309's own research); Linux/Windows are KiCad's
# own documented install conventions, not yet confirmed against a real
# install of either.
_CANDIDATE_GLOBS = {
    "Darwin": [
        "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    ],
    "Linux": [
        "/usr/bin/kicad-cli",
        "/usr/local/bin/kicad-cli",
        "/snap/kicad/current/usr/bin/kicad-cli",
    ],
    "Windows": [
        r"C:\Program Files\KiCad\*\bin\kicad-cli.exe",
    ],
}


_path_override = None


def configure(path_override=None):
    """A configured override (future SPEC-106-style setting), when set,
    takes priority over the PATH/glob search find_kicad_cli otherwise
    falls back to -- same precedence freecad_bridge.configure already
    established for freecadcmd."""
    global _path_override
    _path_override = path_override


def find_kicad_cli() -> str:
    """Locates the `kicad-cli` executable: a configured override first,
    then PATH, then real per-OS install locations. Raises a clean error
    rather than letting a caller hit a confusing FileNotFoundError from
    subprocess."""
    if _path_override:
        if os.path.isfile(_path_override):
            return _path_override
        raise KicadCliUnavailableError(
            f"Configured kicad-cli path override does not exist: {_path_override}"
        )

    on_path = shutil.which("kicad-cli")
    if on_path:
        return on_path

    for pattern in _CANDIDATE_GLOBS.get(platform.system(), []):
        matches = sorted(glob.glob(pattern), reverse=True)
        if matches:
            return matches[0]

    raise KicadCliUnavailableError(
        "Could not find the kicad-cli executable. Install KiCad 9+, or ensure it's on PATH."
    )


def _run_report(subcommand: list, input_path: str) -> dict:
    """Runs `kicad-cli <subcommand> --format json -o <tmpfile> <input_path>`
    and returns the real, parsed JSON report.

    kicad-cli's own real exit code is 0 whether or not violations were
    found -- confirmed directly by running both `sch erc` and `pcb drc`
    against real personal board files with real violations (14 and 1
    respectively) during SPEC-309's own research; both exited 0. So a
    nonzero exit here means kicad-cli itself failed to run (a malformed
    or missing input file), never "violations exist" -- surfaced as
    KicadCliError, distinct from a real, successfully-produced report
    that simply lists violations."""
    cli = find_kicad_cli()
    if not os.path.exists(input_path):
        raise KicadCliError(f"Input file does not exist: {input_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = os.path.join(tmpdir, "report.json")
        result = subprocess.run(
            [cli, *subcommand, "--format", "json", "--severity-all", "-o", report_path, input_path],
            capture_output=True, text=True, timeout=120,
        )
        if not os.path.exists(report_path):
            raise KicadCliError(
                f"kicad-cli did not produce a report (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
        with open(report_path, encoding="utf-8") as f:
            return json.load(f)


def run_erc(sch_path: str) -> dict:
    """Real Electrical Rules Check on a .kicad_sch file -- SPEC-309.
    Real JSON shape (confirmed by actually running this against a real
    schematic, not guessed): {..., sheets: [{path, uuid_path,
    violations: [{description, items, severity, type}]}]} -- nested per
    sheet, since a schematic can have several."""
    return _run_report(["sch", "erc"], sch_path)


def run_drc(pcb_path: str) -> dict:
    """Real Design Rules Check on a .kicad_pcb file -- SPEC-309. Real
    JSON shape (confirmed the same way): {..., unconnected_items,
    violations: [{description, items, severity, type}]} -- flat, since a
    board is one PCB, not several sheets."""
    return _run_report(["pcb", "drc"], pcb_path)
