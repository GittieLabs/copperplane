#!/usr/bin/env python3
"""
SPEC-407 §2.3: make `tauri build` produce a working app in one command.

Wired into `tauri.conf.json`'s own `beforeBuildCommand` hook and called by
`release.yml`, so the freeze/rename sequence has exactly ONE implementation
instead of being written out separately in CI and in prose in CONTRIBUTING.
That single-implementation property is what answers SPEC-406 §1's objection
to a wrapper ("a second thing to keep in sync with release.yml") -- this is
not a second thing, it is the only thing.

Fast path: if the target-triple sidecar already exists, is not the committed
placeholder, and matches the build target's architecture, this exits 0 having
done nothing. Only a missing, placeholder, or wrong-arch sidecar pays for a
real freeze.

Usage:
    ensure_sidecar.py [--target-triple TRIPLE] [--check-only]

`--check-only` never freezes; it reports and exits non-zero if the sidecar
is not usable. That is the mode a CI job wants when the freeze is a separate,
explicit step.
"""
import argparse
import json
import os
import struct
import subprocess
import threading
import time
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DAEMON_DIR = os.path.dirname(HERE)
DIST_DIR = os.path.join(DAEMON_DIR, "dist")
BASE_NAME = "hardware-agent-studio-daemon"

# The committed placeholders (CTX-401.2, CTX-402.5) all carry this literal
# marker and are /bin/sh text. A real PyInstaller binary is Mach-O, PE or
# ELF and never contains it, so this is an exact test rather than a heuristic.
_PLACEHOLDER_MARKER = b"PLACEHOLDER"

# Mach-O, for the macOS arch check. CPU types per <mach/machine.h>.
_MH_MAGIC_64_LE = b"\xcf\xfa\xed\xfe"
_FAT_MAGIC = b"\xca\xfe\xba\xbe"
_CPU_ARM64 = 0x0100000C
_CPU_X86_64 = 0x01000007
_CPU_NAMES = {_CPU_ARM64: "arm64", _CPU_X86_64: "x86_64"}

# Which architecture each target triple's sidecar must actually be.
_TRIPLE_ARCH = {
    "aarch64-apple-darwin": "arm64",
    "x86_64-apple-darwin": "x86_64",
}


def sidecar_name(triple: str) -> str:
    """Tauri's externalBin convention: base name plus the BUILD TARGET's
    triple (never the host's -- CTX-402.4 Plan Drift), plus .exe on Windows."""
    suffix = ".exe" if "windows" in triple else ""
    return f"{BASE_NAME}-{triple}{suffix}"


def is_placeholder(path: str) -> bool:
    """True for the committed build placeholder. Reads a bounded prefix so a
    real 32MB binary is never slurped into memory to answer this."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(4096)
    except OSError:
        return False
    return head.startswith(b"#!") and _PLACEHOLDER_MARKER in head


def macho_arches(path: str) -> set:
    """The architectures a Mach-O file actually contains. Empty set for a
    file that isn't Mach-O at all (a Linux/Windows binary, or the shell-script
    placeholder), so callers can skip the check rather than guess."""
    try:
        with open(path, "rb") as handle:
            magic = handle.read(4)
            if magic == _MH_MAGIC_64_LE:
                cpu = struct.unpack("<I", handle.read(4))[0]
                return {_CPU_NAMES.get(cpu, f"cputype-{cpu}")}
            if magic == _FAT_MAGIC:
                count = struct.unpack(">I", handle.read(4))[0]
                found = set()
                for _ in range(min(count, 16)):
                    cpu = struct.unpack(">I", handle.read(4))[0]
                    handle.read(16)  # rest of this fat_arch entry
                    found.add(_CPU_NAMES.get(cpu, f"cputype-{cpu}"))
                return found
    except (OSError, struct.error):
        return set()
    return set()


# The sources PyInstaller actually freezes: daemon.py plus every top-level
# module it imports, the spec file that drives the build, and the dependency
# pin list. Deliberately NOT scripts/ (build tooling, never frozen in) and
# NOT tests/ (never imported by daemon.py), so editing this script or a test
# does not cost anyone a multi-minute re-freeze.
_FROZEN_SOURCE_EXTRAS = ("daemon.spec", "requirements.txt")


def newest_source_mtime(daemon_dir: str):
    """(mtime, filename) of the most recently modified frozen source, or
    (None, None) if none can be read.

    mtime rather than a content hash on purpose. A hash would need a
    manifest written next to the binary, and release.yml freezes with raw
    `pyinstaller` rather than through freeze_sidecar -- it would never write
    that manifest, so every CI leg would read "no manifest", call a
    just-built sidecar stale, and re-freeze it for nothing. mtime is
    self-recording: CI checks out sources and *then* builds, so the binary
    is always newer there and the check is inert. Locally, dist/ survives
    `git pull`, which is exactly the case this catches."""
    newest, which = None, None
    paths = [
        os.path.join(daemon_dir, n) for n in os.listdir(daemon_dir) if n.endswith(".py")
    ]
    paths += [
        os.path.join(daemon_dir, n) for n in _FROZEN_SOURCE_EXTRAS
        if os.path.isfile(os.path.join(daemon_dir, n))
    ]
    # The agentflow tree is bundled by daemon.spec's own `datas`, so a prompt
    # is as much frozen source as a module is -- and was not watched here.
    # Confirmed by touching a prompt and watching this report "current":
    # raising an agent's max_tokens, or any prompt edit, would ship stale and
    # silently. That is CTX-407.4's defect exactly (`datas` the freeze did not
    # carry), reached from the other direction.
    agentflow_dir = os.path.join(daemon_dir, "agentflow")
    for root, _dirs, files in os.walk(agentflow_dir):
        paths += [
            os.path.join(root, f) for f in files
            if f.endswith((".md", ".py", ".yaml", ".yml", ".json"))
        ]

    for path in paths:
        try:
            stamp = os.path.getmtime(path)
        except OSError:
            continue
        if newest is None or stamp > newest:
            newest, which = stamp, os.path.relpath(path, daemon_dir)
    return newest, which


def staleness(path: str, daemon_dir: str):
    """(is_stale, reason). SPEC-407 s2.2 checks that a sidecar is real and
    the right architecture, but never that it is CURRENT -- so a binary
    frozen before a source change bundles cleanly, starts, reports ready,
    and answers -32601 Method not found for every route added since. That
    is failure mode 7's shape exactly (a healthy-looking daemon with routes
    missing), reached by a different road."""
    newest, which = newest_source_mtime(daemon_dir)
    if newest is None:
        return False, None
    try:
        built = os.path.getmtime(path)
    except OSError:
        return False, None
    if newest <= built:
        return False, None
    from datetime import datetime as _dt
    fmt = "%Y-%m-%d %H:%M:%S"
    return True, (
        f"stale -- frozen {_dt.fromtimestamp(built).strftime(fmt)}, but {which} "
        f"changed {_dt.fromtimestamp(newest).strftime(fmt)}. Routes or fixes added "
        f"since the freeze are absent from this binary."
    )


def overwrites_tracked_placeholder(path: str) -> bool:
    """SPEC-407 §2.1 (failure mode 8): the four placeholders are TRACKED --
    `.gitignore` ignores `dist/` broadly and then explicitly un-ignores
    them -- so a real freeze leaves git reporting a ~50MB modification to a
    committed file, permanently, on every branch.

    Two ways that bites, both found on a real machine: `git add -A` commits
    a 50MB binary into history, and `git checkout -- .` silently destroys a
    freeze that took minutes. Neither is guarded anywhere, so this at least
    says so out loud.

    Returns False rather than raising when git is unavailable or this is not
    a checkout (a source tarball, a vendored copy) -- the warning is a
    courtesy, never a reason to fail a build."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", path],
            capture_output=True, text=True, cwd=os.path.dirname(path) or ".", timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and bool(out.stdout.strip())


def inspect(path: str, triple: str, daemon_dir: str = None):
    """(ok, reason). The single place that decides whether a sidecar is
    usable, so the check-only mode and the freeze path can never disagree.

    `daemon_dir` is where the frozen sources live, defaulting to this
    checkout's own. It is a parameter rather than a module global so a test
    can point the currency check at a fixture directory instead of silently
    comparing a temp file against the real repo."""
    if daemon_dir is None:
        daemon_dir = DAEMON_DIR
    if not os.path.isfile(path):
        return False, "no sidecar at the target-triple name"
    if is_placeholder(path):
        return False, "this is the committed build placeholder, not a real daemon"
    expected = _TRIPLE_ARCH.get(triple)
    if expected:
        arches = macho_arches(path)
        if arches and expected not in arches:
            return False, (
                f"architecture mismatch -- the build target needs {expected}, "
                f"this binary is {'/'.join(sorted(arches))}"
            )
    is_stale, why = staleness(path, daemon_dir)
    if is_stale:
        return False, why
    return True, "present, real, current, and the right architecture"


def resolve_triple(explicit=None) -> str:
    """Target triple, most trustworthy source first. `rustc -vV`'s host is
    LAST on purpose: it is the build machine's own arch and stays wrong when
    cross-compiling, which is exactly the bug CTX-402.4 found in release.yml's
    rename step."""
    if explicit:
        return explicit
    for var in ("TAURI_ENV_TARGET_TRIPLE", "CARGO_BUILD_TARGET"):
        value = os.environ.get(var)
        if value:
            return value
    out = subprocess.run(
        ["rustc", "-vV"], capture_output=True, text=True, check=True,
    ).stdout
    for line in out.splitlines():
        if line.startswith("host: "):
            return line[len("host: "):].strip()
    raise RuntimeError("could not determine a target triple")


_PROBE_FAILURE_HELP = (
    "ensure_sidecar: re-freeze it:\n"
    "                .build-venv/bin/python scripts/freeze_sidecar.py --target-triple <triple>"
)


def probe_routes(path: str, timeout_s: float = 15.0, command: list = None):
    """(ok, reason). Ask the frozen artifact what it can actually do.

    SPEC-407 §1's costly failure was "a mis-frozen sidecar that starts, reports
    `daemon.ready`, passes the heartbeat shield, and runs with the entire AI
    surface disabled". `inspect()` above cannot catch that: exists, not a
    placeholder, right architecture and newer than source are all properties of
    the FILE. A binary can satisfy every one and still be missing half its
    routes because a module failed to import inside the freeze.

    So this runs it, asks `daemon.list_routes`, and compares against the routes
    this checkout defines. `CTX-407.3` and `CTX-407.4` both shipped defects of
    exactly this shape, and both were invisible to the whole test suite.

    Fails open on anything that is not a real disagreement -- a probe that
    cannot run must not block a build, or the first flaky launch turns into a
    reason to delete the check.
    """
    if DAEMON_DIR not in sys.path:
        sys.path.insert(0, DAEMON_DIR)
    try:
        import daemon as source_daemon
    except Exception as exc:  # the source tree itself is broken; not our news
        return True, f"skipped -- this checkout's daemon.py did not import ({exc})"

    expected = set(source_daemon.ROUTES)
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "daemon.list_routes",
                          "params": {}}) + "\n"
    # Read until the answer arrives, then stop -- do NOT wait for the process
    # to exit. `subprocess.run` does wait, and measured 14-17s per build against
    # a real frozen sidecar, because a daemon whose stdin has closed still takes
    # its time shutting down. SPEC-407 §2 values a build check that "exits
    # immediately"; a 15s tax on every build is how a check gets removed.
    #
    # `command` exists so a test can stand a script in for the binary. A real
    # caller never passes it -- and the alternative, a POSIX shell script as the
    # fake sidecar, made these tests fail on Windows, which is precisely the
    # platform SPEC-903's CI exists to speak for.
    proc = None
    try:
        proc = subprocess.Popen(command or [path], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, bufsize=1)
        proc.stdin.write(request)
        proc.stdin.flush()
        lines = []
        done = threading.Event()

        def _read():
            for line in iter(proc.stdout.readline, ''):
                lines.append(line)
                if '"routes"' in line:
                    break
            done.set()

        reader = threading.Thread(target=_read, daemon=True)
        reader.start()
        done.wait(timeout_s)
        proc.stdout_text = "".join(lines)
    except Exception as exc:
        return True, f"skipped -- could not run the sidecar to ask it ({exc})"
    finally:
        if proc is not None:
            proc.kill()

    reported, degraded = None, []
    for line in proc.stdout_text.splitlines():
        try:
            message = json.loads(line)
        except ValueError:
            continue
        result = message.get("result")
        if isinstance(result, dict) and "routes" in result:
            reported = set(result["routes"])
            degraded = result.get("degraded_modules") or []
            break
        if message.get("method") == "daemon.ready":
            degraded = (message.get("params") or {}).get("degraded_modules") or degraded

    if reported is None:
        # An older sidecar predates the route. Not a disagreement to fail on.
        return True, "skipped -- this sidecar does not answer daemon.list_routes"

    missing = sorted(expected - reported)
    if missing:
        shown = ", ".join(missing[:6]) + (f", and {len(missing) - 6} more" if len(missing) > 6 else "")
        return False, (
            f"the frozen sidecar is missing {len(missing)} route(s) this checkout defines: {shown}."
            + (f" It reports degraded modules: {', '.join(degraded)}." if degraded else
               " It reports no degraded modules, so a bundled data file or a hidden import is the"
               " likely cause.")
        )
    if degraded:
        return False, (
            f"the frozen sidecar started with degraded modules: {', '.join(degraded)}. Every route"
            " is present, but those modules failed to import inside the freeze."
        )
    return True, f"answers all {len(reported)} routes, no degraded modules"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-triple", default=None)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument(
        "--probe", action="store_true",
        help="also run an already-present sidecar and check it answers every route "
             "this checkout defines (costs ~15s; the freeze path always does this)",
    )
    args = parser.parse_args()

    try:
        triple = resolve_triple(args.target_triple)
    except Exception as exc:
        print(f"ensure_sidecar: cannot determine the target triple: {exc}", file=sys.stderr)
        return 1

    path = os.path.join(DIST_DIR, sidecar_name(triple))
    ok, reason = inspect(path, triple)
    print(f"ensure_sidecar: target {triple}")
    print(f"ensure_sidecar: {os.path.relpath(path, DAEMON_DIR)} -- {reason}")

    if ok:
        # Deliberately NOT probed here. Launching a frozen sidecar costs 14-17s
        # on this machine -- PyInstaller startup, not the read -- and SPEC-407
        # §2 already worried that "a build-time check that runs on every
        # `cargo build` would break the debug loop". A sidecar that passed its
        # probe when it was frozen and has not changed since (which the mtime
        # check above proves) has nothing new to say. `--probe` re-asks on
        # demand; the freeze path below always asks.
        if args.probe:
            probe_ok, probe_reason = probe_routes(path)
            print(f"ensure_sidecar: {probe_reason}")
            if not probe_ok:
                print(_PROBE_FAILURE_HELP, file=sys.stderr)
                return 1
        if overwrites_tracked_placeholder(path):
            print(
                "ensure_sidecar: NOTE -- this real sidecar sits on top of the tracked placeholder,\n"
                "                so git reports it permanently modified (~50MB). Do NOT run\n"
                "                `git add -A` here (it would commit the binary), and note that\n"
                "                `git checkout -- .` would destroy this freeze.",
                file=sys.stderr,
            )
        return 0

    if args.check_only:
        print(
            "ensure_sidecar: refusing to bundle. Freeze the daemon first:\n"
            "    cd services/python-daemon && python3 scripts/ensure_sidecar.py",
            file=sys.stderr,
        )
        return 1

    print("ensure_sidecar: freezing the daemon (this takes a few minutes the first time)")
    try:
        from freeze_sidecar import freeze  # noqa: PLC0415 -- optional at check time
    except ImportError:
        sys.path.insert(0, HERE)
        from freeze_sidecar import freeze

    try:
        freeze(triple, DAEMON_DIR, DIST_DIR, sidecar_name(triple))
    except Exception as exc:
        print(f"ensure_sidecar: freeze failed -- {exc}", file=sys.stderr)
        return 1

    ok, reason = inspect(path, triple)
    if not ok:
        print(f"ensure_sidecar: freeze produced an unusable sidecar -- {reason}", file=sys.stderr)
        return 1
    print(f"ensure_sidecar: {os.path.relpath(path, DAEMON_DIR)} -- {reason}")

    # Probe the freeze we just made, not only one we found. A bad freeze is
    # precisely when this check earns its keep, and checking only the
    # already-present case would skip the moment the artifact is created.
    # Always probe a freeze we just made. This is the moment a bad one is
    # created, and the only moment the 14-17s is unambiguously worth paying.
    probe_ok, probe_reason = probe_routes(path)
    print(f"ensure_sidecar: {probe_reason}")
    if not probe_ok:
        print(
            "ensure_sidecar: FAILING -- the freeze completed and produced a sidecar that cannot"
            " do its job.",
            file=sys.stderr,
        )
        print(_PROBE_FAILURE_HELP, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
