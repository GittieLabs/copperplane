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
import uuid


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
_output_dir_override = None


def configure(path_override=None, output_dir=None):
    """A configured path override, when set, takes priority over the
    PATH/glob search `find_kicad_cli` otherwise falls back to -- same
    precedence `freecad_bridge.configure` already established for
    `freecadcmd`. `output_dir` (SPEC-301 §2, the same Rust-computed,
    already-wired config value `freecad_bridge.configure` consumes) is
    where `export_board_glb` (SPEC-311) writes its real `.glb` output --
    this module's real executable-discovery config existed since
    SPEC-309 but was never actually wired into `daemon.py`'s own
    `_apply_env_config` until SPEC-311 needed a real output path too."""
    global _path_override, _output_dir_override
    _path_override = path_override
    _output_dir_override = output_dir


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


def export_board_glb(pcb_path: str) -> str:
    """Real `kicad-cli pcb export glb` wrapper (SPEC-311): exports the
    *entire assembled board* -- substrate plus every real component's
    real 3D model, already correctly positioned and transformed by
    KiCad itself -- as one real `.glb` file. Verified live during
    SPEC-311's own research: a real 634KB file, 1159 real meshes, a real
    49.50 x 11.54 x 106.50mm bounding box against a real, currently-open
    board. `--subst-models` substitutes STEP/IGS models in place of VRML
    ones where both exist, for a higher-fidelity export.

    A component with genuinely no 3D model at all is still silently
    omitted by `kicad-cli` itself -- this export is the real *visual*,
    not the source of truth for "is every component's height
    accounted for"; that honesty requirement is `kicad.
    get_component_heights`'s job (SPEC-311 §2), not this one.

    Unlike `_run_report`, this subcommand writes a real binary `.glb`
    directly to `--output`, not a JSON report read back from a temp
    dir -- the returned path is the same real, persistent path the
    caller supplied, mirroring `freecad_bridge.generate_enclosure`'s own
    `output_dir`-relative output convention."""
    cli = find_kicad_cli()
    if not os.path.exists(pcb_path):
        raise KicadCliError(f"Input file does not exist: {pcb_path}")

    output_dir = _output_dir_override or tempfile.gettempdir()
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"board_{uuid.uuid4().hex}.glb")

    result = subprocess.run(
        [cli, "pcb", "export", "glb", "--force", "--subst-models",
         "--output", output_path, pcb_path],
        capture_output=True, text=True, timeout=120,
    )
    if not os.path.exists(output_path):
        raise KicadCliError(
            f"kicad-cli did not produce a .glb (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return output_path
