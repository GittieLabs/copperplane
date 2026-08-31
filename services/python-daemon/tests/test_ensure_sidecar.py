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
        """TEST-002: run against the four REAL committed placeholders on
        disk, not a fixture -- if any stops matching, this fails."""
        checked = 0
        for triple in ("aarch64-apple-darwin", "x86_64-apple-darwin",
                       "x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu"):
            path = os.path.join(DIST, es.sidecar_name(triple))
            if not os.path.isfile(path):
                continue
            checked += 1
            self.assertTrue(es.is_placeholder(path), f"{triple} placeholder not detected")
            ok, reason = es.inspect(path, triple)
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
