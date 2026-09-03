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
import csv
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


def export_schematic_bom(sch_path: str) -> list:
    """Every component in a schematic, read from the FILE (SPEC-325 §2.2).

    `kicad-cli sch export bom` works on a closed `.kicad_sch` -- no GUI,
    no IPC, no running KiCad. That matters: `kicad_bridge`'s existing
    path derives a schematic from whatever board KiCad currently has
    open, and KiCad's IPC server has never implemented a
    schematic-listing handler at all (see `list_project_schematics`).

    Returns `[{"reference", "value", "footprint", "quantity", "dnp"}, ...]`,
    one entry per reference -- kicad-cli groups identical parts onto one
    row with a comma-separated `Refs` field, which is a BOM's shape, not
    a component list's. Ungrouped here so a caller can key by reference
    designator, which is what every downstream consumer actually wants.

    Fails loudly on an unrecognised shape rather than returning an empty
    list. `kicad-cli`'s CSV columns are a CLI contract that can change
    between KiCad majors, and an empty list would read to a user as
    "your schematic has no components" -- a silent wrong answer, which
    SPEC-325 §3 names as the specific risk here.
    """
    cli = find_kicad_cli()
    if not os.path.exists(sch_path):
        raise KicadCliError(f"Schematic file does not exist: {sch_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "bom.csv")
        result = subprocess.run(
            [cli, "sch", "export", "bom", "--output", out, sch_path],
            capture_output=True, text=True, timeout=120,
        )
        if not os.path.exists(out):
            raise KicadCliError(
                f"kicad-cli produced no BOM (exit {result.returncode}): {result.stderr.strip()}"
            )
        with open(out, encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    if rows:
        missing = {"Refs", "Value", "Footprint"} - set(rows[0].keys())
        if missing:
            raise KicadCliError(
                f"kicad-cli's BOM is missing expected column(s): {', '.join(sorted(missing))}. "
                f"Got: {', '.join(rows[0].keys())}. This KiCad version's BOM format is not the "
                f"one this app knows how to read."
            )

    components = []
    for row in rows:
        for reference in [r.strip() for r in (row.get("Refs") or "").split(",") if r.strip()]:
            components.append({
                "reference": reference,
                "value": (row.get("Value") or "").strip() or None,
                "footprint": (row.get("Footprint") or "").strip() or None,
                "dnp": bool((row.get("DNP") or "").strip()),
            })
    return components


def run_erc(sch_path: str) -> dict:
    """Real Electrical Rules Check on a .kicad_sch file -- SPEC-309.
    Real JSON shape (confirmed by actually running this against a real
    schematic, not guessed): {..., sheets: [{path, uuid_path,
    violations: [{description, items, severity, type}]}]} -- nested per
    sheet, since a schematic can have several."""
    return _run_report(["sch", "erc"], sch_path)


def run_drc(pcb_path: str, schematic_parity: bool = False) -> dict:
    """Real Design Rules Check on a .kicad_pcb file -- SPEC-309. Real
    JSON shape (confirmed the same way): {..., unconnected_items,
    violations: [{description, items, severity, type}]} -- flat, since a
    board is one PCB, not several sheets."""
    subcommand = ["pcb", "drc"]
    if schematic_parity:
        # Off by default: parity needs the `.kicad_sch` sibling, and a board
        # checked on its own is a legitimate call. Callers that want it ask.
        subcommand.append("--schematic-parity")
    return _run_report(subcommand, pcb_path)


def check_schematic_parity(pcb_path: str) -> list:
    """Every place the board and its schematic disagree -- SPEC-326 2.7.

    KiCad performs this comparison itself, via `pcb drc
    --schematic-parity`, on a CLOSED board: it reads the `.kicad_sch`
    sitting beside the `.kicad_pcb` and reports each symbol/footprint
    disagreement under a `schematic_parity` key. We deliberately do not
    hand-roll the comparison. A hand-rolled diff of `sch export bom`
    footprints against `pcb export pos` packages was written first and
    produced FIVE findings on the maintainer's own board, of which one
    was real: the other four were the mounting holes H1-H4, which are
    board-only by design and carry no schematic symbol at all. KiCad's
    own check reports exactly the one real issue and correctly stays
    silent about the mounting holes, because it knows which absences are
    legitimate and a footprint-name diff does not.

    Returns the raw parity entries -- each {description, severity, type,
    items} -- and an empty list when the board and schematic agree.
    """
    report = _run_report(["pcb", "drc", "--schematic-parity"], pcb_path)
    return report.get("schematic_parity", [])


def export_board_glb(pcb_path: str, origin_x_mm: float = None, origin_y_mm: float = None) -> str:
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

    `origin_x_mm`/`origin_y_mm` (CTX-311.15, both required together or
    both omitted): passed as `--user-origin {x}x{y}mm`, real-verified
    live against `kicad-cli` before being wired in here -- its own
    *default* output (no origin flag) already lands in the same real,
    absolute board-layout coordinate frame `kicad_bridge.get_board_
    outline`/`kicad_pcb_import.extract_board_outline` report `x_mm`/
    `y_mm` in, and passing those same real values here re-origins the
    export to the board's own bounding-box corner -- confirmed live: the
    resulting glb's own bounds shift to start at exactly local `(0, *,
    0)`. This is what lets `EnclosureViewer.tsx` composite the real
    board glb inside the real enclosure glb with a simple, already-known
    constant translation, not a guessed offset.

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

    command = [cli, "pcb", "export", "glb", "--force", "--subst-models",
               "--output", output_path]
    if origin_x_mm is not None and origin_y_mm is not None:
        command += ["--user-origin", f"{origin_x_mm}x{origin_y_mm}mm"]
    command.append(pcb_path)

    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if not os.path.exists(output_path):
        raise KicadCliError(
            f"kicad-cli did not produce a .glb (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return output_path


def export_symbol_svg(kicad_sym_path: str) -> str:
    """Real `kicad-cli sym export svg` wrapper (CTX-306.7) -- takes the
    `.kicad_sym` file path directly, confirmed live against real KiCad
    (`test_library_store.py`'s own `TestExportSymbolKicadSym`). Unlike
    `export_board_glb`, `-o` here names an *output directory*, not a
    file -- the CLI derives the real SVG's own filename from the
    symbol, so the directory is scanned afterward for whatever it
    actually wrote rather than assuming a name."""
    cli = find_kicad_cli()
    if not os.path.exists(kicad_sym_path):
        raise KicadCliError(f"Input file does not exist: {kicad_sym_path}")

    output_dir = os.path.join(_output_dir_override or tempfile.gettempdir(), f"symsvg_{uuid.uuid4().hex}")
    os.makedirs(output_dir, exist_ok=True)

    command = [cli, "sym", "export", "svg", "-o", output_dir, kicad_sym_path]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    svgs = [f for f in os.listdir(output_dir) if f.endswith(".svg")]
    if not svgs:
        raise KicadCliError(
            f"kicad-cli did not produce an .svg (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return os.path.join(output_dir, svgs[0])


def export_footprint_svg(pretty_dir: str, footprint_id: str) -> str:
    """Real `kicad-cli fp export svg` wrapper (CTX-306.7). Unlike `sym
    export svg`, this subcommand takes the *containing `.pretty`
    directory* plus `--footprint <name>`, never the `.kicad_mod` file
    path directly -- confirmed live against real KiCad
    (`test_library_store.py`'s own `TestExportFootprintKicadMod`,
    which found this the hard way rather than assuming it from
    `--help` text alone)."""
    cli = find_kicad_cli()
    if not os.path.isdir(pretty_dir):
        raise KicadCliError(f"Input directory does not exist: {pretty_dir}")

    output_dir = os.path.join(_output_dir_override or tempfile.gettempdir(), f"fpsvg_{uuid.uuid4().hex}")
    os.makedirs(output_dir, exist_ok=True)

    command = [cli, "fp", "export", "svg", "-o", output_dir, "--footprint", footprint_id, pretty_dir]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    svgs = [f for f in os.listdir(output_dir) if f.endswith(".svg")]
    if not svgs:
        raise KicadCliError(
            f"kicad-cli did not produce an .svg (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return os.path.join(output_dir, svgs[0])
