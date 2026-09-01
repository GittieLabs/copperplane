"""SPEC-407 §2.3: the bundle-time sidecar check that makes `tauri build`
either produce a working app or fail saying why.

The Mach-O fixtures below are synthesized headers rather than real binaries.
That is deliberate: the parser only reads the magic and cputype fields, so a
hand-built header exercises exactly the bytes it looks at, and it lets the
arch-mismatch case -- the one that shipped a broken sidecar on 2026-08-27 --
be tested on any platform including CI's Linux runner.
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import ensure_sidecar as es  # noqa: E402

_ARM64 = 0x0100000C
_X86_64 = 0x01000007

DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist")


def _macho(path, cputype):
    with open(path, "wb") as handle:
        handle.write(b"\xcf\xfa\xed\xfe")
        handle.write(struct.pack("<I", cputype))
        handle.write(b"\x00" * 24)


def _fat(path, cputypes):
    with open(path, "wb") as handle:
        handle.write(b"\xca\xfe\xba\xbe")
        handle.write(struct.pack(">I", len(cputypes)))
        for cpu in cputypes:
            handle.write(struct.pack(">I", cpu))
            handle.write(b"\x00" * 16)


def _committed_bytes(repo_relative_path):
    """The blob git has for a path, or None if git or the path is unavailable.
    Used so a working tree carrying a real freeze does not change what the
    placeholder tests are actually testing."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "show", f"HEAD:{repo_relative_path}"],
            capture_output=True, cwd=os.path.dirname(DIST), timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


class TestSidecarNaming(unittest.TestCase):
    def test_001_appends_the_target_triple_and_exe_only_on_windows(self):
        """TEST-001: Tauri's externalBin convention. Getting this wrong is
        what leaves the committed placeholder in place to be bundled."""
        self.assertEqual(
            es.sidecar_name("aarch64-apple-darwin"),
            "hardware-agent-studio-daemon-aarch64-apple-darwin",
        )
        self.assertEqual(
            es.sidecar_name("x86_64-pc-windows-msvc"),
            "hardware-agent-studio-daemon-x86_64-pc-windows-msvc.exe",
        )


class TestPlaceholderDetection(unittest.TestCase):
    def test_002_every_committed_placeholder_is_detected_for_real(self):
        """TEST-002: run against the four REAL committed placeholders, not a
        fixture -- if any stops matching, this fails.

        CTX-407.3: read each one from git rather than the working tree. A
        real local freeze overwrites the host's placeholder in dist/ -- that
        is the documented, expected state (ensure_sidecar prints a NOTE
        about it), but it used to make this test fail on any machine that
        had actually built the app, which is every machine a contributor
        runs it on. The committed blob is what this test means by
        "committed".
        """
        checked = 0
        for triple in ("aarch64-apple-darwin", "x86_64-apple-darwin",
                       "x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu"):
            name = es.sidecar_name(triple)
            blob = _committed_bytes(f"services/python-daemon/dist/{name}")
            if blob is None:
                continue
            checked += 1
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, name)
                with open(path, "wb") as handle:
                    handle.write(blob)
                self.assertTrue(es.is_placeholder(path), f"{triple} placeholder not detected")
                ok, reason = es.inspect(path, triple, daemon_dir=tmp)
                self.assertFalse(ok)
                self.assertIn("placeholder", reason)
        self.assertGreater(checked, 0, "no committed placeholders found to check")

    def test_003_a_real_binary_is_not_mistaken_for_a_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = os.path.join(tmp, "real")
            _macho(real, _ARM64)
            self.assertFalse(es.is_placeholder(real))


class TestArchMismatch(unittest.TestCase):
    """The failure that shipped a broken sidecar: a binary frozen for one
    architecture bundled for a build target expecting the other."""

    def test_004_arm64_binary_is_rejected_for_an_x86_64_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "daemon")
            _macho(path, _ARM64)
            ok, reason = es.inspect(path, "x86_64-apple-darwin")
            self.assertFalse(ok)
            self.assertIn("architecture mismatch", reason)
            self.assertIn("x86_64", reason)

    def test_005_matching_arch_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "daemon")
            _macho(path, _ARM64)
            ok, _ = es.inspect(path, "aarch64-apple-darwin")
            self.assertTrue(ok)

    def test_006_a_universal_binary_satisfies_either_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "daemon")
            _fat(path, [_ARM64, _X86_64])
            self.assertEqual(es.macho_arches(path), {"arm64", "x86_64"})
            for triple in ("aarch64-apple-darwin", "x86_64-apple-darwin"):
                self.assertTrue(es.inspect(path, triple)[0], triple)

    def test_007_non_macho_targets_skip_the_arch_check(self):
        """Windows and Linux have no Mach-O and no `arch` concept. The check
        must not inherit a rule it cannot pass there."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "daemon")
            with open(path, "wb") as handle:
                handle.write(b"\x7fELF" + b"\x00" * 32)
            self.assertEqual(es.macho_arches(path), set())
            self.assertTrue(es.inspect(path, "x86_64-unknown-linux-gnu")[0])


class TestMissingSidecar(unittest.TestCase):
    def test_008_absent_file_reports_that_rather_than_crashing(self):
        ok, reason = es.inspect("/nonexistent/daemon", "aarch64-apple-darwin")
        self.assertFalse(ok)
        self.assertIn("no sidecar", reason)


class TestTripleResolution(unittest.TestCase):
    def test_009_explicit_argument_wins_over_the_environment(self):
        """CTX-402.4: `rustc -vV`'s host is the BUILD MACHINE's arch and stays
        wrong when cross-compiling, so it must never outrank an explicit
        target. That exact bug mislabelled the x86_64 release leg."""
        os.environ["TAURI_ENV_TARGET_TRIPLE"] = "x86_64-apple-darwin"
        try:
            self.assertEqual(es.resolve_triple("aarch64-apple-darwin"), "aarch64-apple-darwin")
            self.assertEqual(es.resolve_triple(None), "x86_64-apple-darwin")
        finally:
            del os.environ["TAURI_ENV_TARGET_TRIPLE"]


if __name__ == "__main__":
    unittest.main()


class TestPlaceholderOverwriteWarning(unittest.TestCase):
    """SPEC-407 §2.1 failure mode 8, found on a real machine: a real freeze
    overwrites a TRACKED placeholder, so git reports a permanent ~50MB
    modification. `git add -A` would commit it; `git checkout -- .` would
    destroy the freeze. Neither is guarded, so the least this can do is say
    so."""

    def test_010_reports_true_when_git_calls_the_file_modified(self):
        import subprocess as sp
        real = sp.run

        class Result:
            returncode = 0
            stdout = " M services/python-daemon/dist/hardware-agent-studio-daemon-aarch64-apple-darwin\n"

        sp.run = lambda *a, **k: Result()
        try:
            self.assertTrue(es.overwrites_tracked_placeholder("dist/whatever"))
        finally:
            sp.run = real

    def test_011_reports_false_on_a_clean_file(self):
        import subprocess as sp
        real = sp.run

        class Result:
            returncode = 0
            stdout = ""

        sp.run = lambda *a, **k: Result()
        try:
            self.assertFalse(es.overwrites_tracked_placeholder("dist/whatever"))
        finally:
            sp.run = real

    def test_012_never_raises_when_git_is_unavailable(self):
        """A source tarball or a vendored copy has no git. The warning is a
        courtesy and must never be a reason a build fails."""
        import subprocess as sp
        real = sp.run

        def boom(*a, **k):
            raise OSError("git not found")

        sp.run = boom
        try:
            self.assertFalse(es.overwrites_tracked_placeholder("dist/whatever"))
        finally:
            sp.run = real


def _sources(tmp, names=("daemon.py", "llm_providers.py"), extras=("daemon.spec", "requirements.txt")):
    """A minimal stand-in for services/python-daemon's frozen sources."""
    for name in list(names) + list(extras):
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
            handle.write("# fixture\n")


def _stamp(path, when):
    os.utime(path, (when, when))


class TestStaleness(unittest.TestCase):
    """CTX-407.3. SPEC-407 §2.2's bundle-time checkpoint asks whether the
    sidecar is real and the right architecture, never whether it is CURRENT.
    A binary frozen before a source change bundles cleanly, starts, reports
    ready, and answers -32601 for every route added since -- failure mode 7's
    shape reached by a different road. Found for real on 2026-08-31: a build
    on develop bundled a sidecar frozen four days earlier, and SPEC-324's
    llm.list_models and llm.validate_model were simply absent from it.
    """

    def test_013_a_sidecar_older_than_a_source_is_stale_and_names_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            _sources(tmp)
            binary = os.path.join(tmp, "daemon-bin")
            _macho(binary, _ARM64)
            for name in os.listdir(tmp):
                if name != "daemon-bin":
                    _stamp(os.path.join(tmp, name), 500_000)
            _stamp(binary, 1_000_000)
            _stamp(os.path.join(tmp, "llm_providers.py"), 2_000_000)
            is_stale, why = es.staleness(binary, tmp)
            self.assertTrue(is_stale)
            self.assertIn("llm_providers.py", why)
            self.assertIn("stale", why)

    def test_014_a_sidecar_newer_than_every_source_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            _sources(tmp)
            binary = os.path.join(tmp, "daemon-bin")
            _macho(binary, _ARM64)
            for name in os.listdir(tmp):
                if name != "daemon-bin":
                    _stamp(os.path.join(tmp, name), 1_000_000)
            _stamp(binary, 2_000_000)
            self.assertEqual(es.staleness(binary, tmp), (False, None))

    def test_015_editing_a_script_or_a_test_does_not_force_a_refreeze(self):
        """scripts/ is build tooling and tests/ is never imported by
        daemon.py, so neither is frozen in. Counting them would charge a
        contributor several minutes for editing a comment in this file --
        exactly the friction CTX-407.2 was written to remove."""
        with tempfile.TemporaryDirectory() as tmp:
            _sources(tmp)
            binary = os.path.join(tmp, "daemon-bin")
            _macho(binary, _ARM64)
            for name in os.listdir(tmp):
                if name != "daemon-bin":
                    _stamp(os.path.join(tmp, name), 1_000_000)
            _stamp(binary, 2_000_000)
            for sub in ("scripts", "tests"):
                os.mkdir(os.path.join(tmp, sub))
                later = os.path.join(tmp, sub, "whatever.py")
                with open(later, "w", encoding="utf-8") as handle:
                    handle.write("# much newer\n")
                _stamp(later, 3_000_000)
            self.assertEqual(es.staleness(binary, tmp), (False, None))

    def test_016_no_readable_sources_never_reports_stale(self):
        """A source tarball or a vendored copy with no .py files present must
        not fail a build over a question it cannot answer."""
        with tempfile.TemporaryDirectory() as tmp:
            binary = os.path.join(tmp, "daemon-bin")
            _macho(binary, _ARM64)
            self.assertEqual(es.staleness(binary, tmp), (False, None))

    def test_017_inspect_surfaces_staleness_so_both_modes_agree(self):
        """check-only and the freeze path both route through inspect(), so
        currency has to be decided there rather than in main()."""
        with tempfile.TemporaryDirectory() as tmp:
            _sources(tmp)
            binary = os.path.join(tmp, "daemon-bin")
            _macho(binary, _ARM64)
            _stamp(binary, 1_000_000)
            _stamp(os.path.join(tmp, "daemon.py"), 2_000_000)
            ok, reason = es.inspect(binary, "aarch64-apple-darwin", daemon_dir=tmp)
            self.assertFalse(ok)
            self.assertIn("stale", reason)

    def test_018_a_current_sidecar_still_passes_inspect_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            _sources(tmp)
            binary = os.path.join(tmp, "daemon-bin")
            _macho(binary, _ARM64)
            for name in os.listdir(tmp):
                if name != "daemon-bin":
                    _stamp(os.path.join(tmp, name), 1_000_000)
            _stamp(binary, 2_000_000)
            ok, reason = es.inspect(binary, "aarch64-apple-darwin", daemon_dir=tmp)
            self.assertTrue(ok)
            self.assertIn("current", reason)
