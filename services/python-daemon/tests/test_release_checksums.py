"""
CTX-402.8: real tests for scripts/generate_checksums.py.

The point of a checksum manifest is that a stranger runs `sha256sum -c` on
it and believes the answer. So the central test here does not compare the
generator's output to hashlib -- that would only prove the generator calls
hashlib, which is not in doubt. It runs the actual verification tool a
person is told to run, against a real manifest, over real files on disk,
and then flips one byte and requires that same tool to report failure.

A manifest that verifies is only evidence if a corrupted one would not.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import generate_checksums  # noqa: E402


def _verifier():
    """The real checksum tool on this machine, as (argv-prefix, name).

    GNU coreutils on Linux, `shasum -a 256` on macOS, neither on a stock
    Windows runner -- where the tests that need one skip loudly rather
    than pretending to have run.
    """
    if shutil.which('sha256sum'):
        return (['sha256sum', '-c', '--strict'], 'sha256sum')
    if shutil.which('shasum'):
        return (['shasum', '-a', '256', '-c'], 'shasum')
    return (None, None)


class ChecksumManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _artifact(self, relative_name, content=b'not really an installer'):
        path = self.root / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_001_manifest_verifies_with_the_real_tool_users_are_told_to_run(self):
        """The exact command the docs give a person must accept our file."""
        argv, name = _verifier()
        if argv is None:
            self.skipTest("no sha256sum or shasum on this machine (expected on windows-latest)")

        self._artifact('macos-aarch64-apple-darwin/Copperplane_0.9.9_aarch64.dmg', b'A' * 5000)
        self._artifact('windows-x86_64-pc-windows-msvc/Copperplane_0.9.9_x64-setup.exe', b'B' * 4096)
        self._artifact('linux-x86_64-unknown-linux-gnu/Copperplane_0.9.9_amd64.AppImage', b'C' * 33)

        manifest = self.root / 'SHA256SUMS.txt'
        manifest.write_text(generate_checksums.render(
            generate_checksums.find_installers([self.root])
        ), encoding='utf-8')

        # Run it the way a person would: from the directory holding the
        # downloaded files, with the manifest alongside them.
        flat = self.root / 'downloaded'
        flat.mkdir()
        for path in generate_checksums.find_installers([self.root]):
            shutil.copy2(path, flat / path.name)
        shutil.copy2(manifest, flat / 'SHA256SUMS.txt')

        result = subprocess.run(
            argv + ['SHA256SUMS.txt'], cwd=flat,
            capture_output=True, text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"{name} rejected a manifest we just generated:\n"
            f"{result.stdout}\n{result.stderr}"
        )
        self.assertEqual(result.stdout.count('OK'), 3, result.stdout)

    def test_002_the_same_tool_rejects_a_manifest_after_one_byte_changes(self):
        """Proves test_001 is a check and not a formality.

        If this failed -- if a corrupted download still verified -- then
        test_001 passing would mean nothing at all.
        """
        argv, name = _verifier()
        if argv is None:
            self.skipTest("no sha256sum or shasum on this machine (expected on windows-latest)")

        artifact = self._artifact('windows/Copperplane_0.9.9_x64-setup.exe', b'B' * 4096)
        manifest_text = generate_checksums.render(generate_checksums.find_installers([self.root]))

        flat = self.root / 'downloaded'
        flat.mkdir()
        shutil.copy2(artifact, flat / artifact.name)
        (flat / 'SHA256SUMS.txt').write_text(manifest_text, encoding='utf-8')

        # A single flipped byte, the size unchanged -- the exact shape of
        # damage a length check would miss.
        corrupted = bytearray((flat / artifact.name).read_bytes())
        corrupted[17] ^= 0xFF
        (flat / artifact.name).write_bytes(bytes(corrupted))

        result = subprocess.run(
            argv + ['SHA256SUMS.txt'], cwd=flat,
            capture_output=True, text=True,
        )
        self.assertNotEqual(
            result.returncode, 0,
            f"{name} accepted a corrupted file -- this manifest verifies nothing"
        )

    def test_003_hashes_are_the_real_sha256_of_the_real_bytes(self):
        """Independent of any external tool, so this still runs on Windows."""
        import hashlib
        payload = os.urandom(70000)
        self._artifact('linux/Copperplane_0.9.9_amd64.deb', payload)

        line = generate_checksums.render(generate_checksums.find_installers([self.root])).strip()
        digest, _, name = line.partition('  ')

        self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
        self.assertEqual(name, 'Copperplane_0.9.9_amd64.deb')

    def test_004_format_is_two_spaces_and_a_bare_basename(self):
        """Not cosmetic: coreutils' own parser reads this exact shape, and
        a path with directories in it would not resolve for someone who
        downloaded the files into one folder."""
        self._artifact('macos-aarch64-apple-darwin/nested/Copperplane_0.9.9_x64.dmg')

        line = generate_checksums.render(generate_checksums.find_installers([self.root]))

        self.assertRegex(line, r'^[0-9a-f]{64}  Copperplane_0\.9\.9_x64\.dmg\n$')
        self.assertNotIn('/', line)
        self.assertNotIn('\\', line)

    def test_005_updater_payloads_and_signatures_are_deliberately_not_hashed(self):
        """.app.tar.gz / .sig / latest.json carry a real Ed25519 signature
        the updater verifies (CTX-402.2). Hashing them here would imply the
        weaker check is what protects an update. It is not."""
        self._artifact('macos-aarch64-apple-darwin/Copperplane_0.9.9_aarch64.dmg')
        self._artifact('macos-aarch64-apple-darwin/Copperplane.app.tar.gz')
        self._artifact('macos-aarch64-apple-darwin/Copperplane.app.tar.gz.sig')
        self._artifact('latest.json', b'{}')

        names = [p.name for p in generate_checksums.find_installers([self.root])]

        self.assertEqual(names, ['Copperplane_0.9.9_aarch64.dmg'])

    def test_006_an_empty_search_fails_loudly_instead_of_publishing_nothing(self):
        """`sha256sum -c` on an empty manifest exits 0 having checked
        nothing. A release must not be able to ship that."""
        self._artifact('macos/Copperplane.app.tar.gz')  # present, but not an installer

        with self.assertRaises(generate_checksums.NoInstallersFoundError):
            generate_checksums.find_installers([self.root])

    def test_007_two_artifacts_with_one_basename_fail_rather_than_guess(self):
        self._artifact('leg-one/Copperplane_0.9.9_x64.dmg', b'one')
        self._artifact('leg-two/Copperplane_0.9.9_x64.dmg', b'two')

        with self.assertRaises(generate_checksums.DuplicateBasenameError):
            generate_checksums.find_installers([self.root])

    def test_008_cli_exits_nonzero_and_writes_nothing_on_an_empty_search(self):
        """The workflow runs this with `>`, so a zero exit on an empty
        search would create a real, empty, published SHA256SUMS.txt."""
        empty = self.root / 'nothing'
        empty.mkdir()

        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'generate_checksums.py'), str(empty)],
            capture_output=True, text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('no files matching', result.stderr)


class ReleaseWorkflowParityTests(unittest.TestCase):
    """The generator's idea of "an installer" and the release workflow's
    must not drift apart. If they do, a new artifact type gets published
    with no checksum line and nothing anywhere says so.
    """

    def setUp(self):
        self.workflow = (REPO_ROOT / '.github/workflows/release.yml').read_text(encoding='utf-8')
        publish = self.workflow.split('Publish the GitHub Release', 1)
        self.assertEqual(len(publish), 2, "release.yml no longer has a 'Publish the GitHub Release' step")
        self.publish_step = publish[1]

    def test_101_every_extension_the_release_publishes_is_hashed_or_deliberately_excluded(self):
        import re
        published = set()
        for match in re.finditer(r'artifacts/[^\s]*/\*\*/\*(\.[A-Za-z0-9.]+)', self.publish_step):
            published.add(match.group(1))

        self.assertTrue(published, "found no artifact globs in the publish step")

        # Everything published is either hashed, or is updater plumbing
        # excluded on purpose with a stated reason in the generator. The
        # exclusion is a rule, not a list: an Ed25519 signature is any
        # `.sig`, whatever it signs, and enumerating the compound forms by
        # hand is how `.AppImage.sig` was missed here the first time.
        def is_updater_plumbing(ext):
            return ext.endswith('.sig') or ext == '.app.tar.gz'

        unaccounted = {
            ext for ext in published
            if ext not in generate_checksums.INSTALLER_EXTENSIONS
            and not is_updater_plumbing(ext)
        }

        self.assertEqual(
            unaccounted, set(),
            f"release.yml publishes {sorted(unaccounted)} but generate_checksums.py neither "
            f"hashes it nor names it as deliberately excluded -- it would ship unverifiable"
        )

    def test_102_the_workflow_actually_generates_and_uploads_the_manifest(self):
        """Guards the other direction: a generator nobody runs."""
        self.assertIn('generate_checksums.py', self.workflow)
        self.assertIn('SHA256SUMS.txt', self.publish_step)


if __name__ == '__main__':
    unittest.main()


def _documented_verify_commands():
    """The verification commands install.md actually gives people, pulled
    out of the page itself.

    Read from the doc rather than restated here on purpose. A copy in this
    file would let the page drift into being wrong while the test went on
    passing against the version I happened to write down.
    """
    import re
    page = (REPO_ROOT / 'docs/site/src/content/docs/install.md').read_text(encoding='utf-8')
    section = page.split('## Verify your download', 1)
    if len(section) != 2:
        return {}
    body = section[1].split('\n## ', 1)[0]

    return {
        m.group(1): m.group(2).strip()
        for m in re.finditer(
            r'\*\*(macOS|Linux|Windows)\*\*[^\n]*\n+```(?:bash|powershell)\n(.*?)```',
            body, re.S,
        )
    }


_PLATFORM = {'darwin': 'macOS', 'linux': 'Linux', 'win32': 'Windows'}.get(sys.platform)


class DocumentedVerifyCommandTests(unittest.TestCase):
    """Runs the command install.md tells a person to run, on the platform
    it is written for, in the situation they are actually in.

    That last part is the whole point. A person downloads *one* installer,
    but SHA256SUMS.txt lists all six. The first version of the macOS
    command in this doc printed five FAILED lines and exited 1 on a
    completely healthy download -- it verified correctly and reported
    alarmingly, and nothing but running it this way would have shown that.
    """

    def setUp(self):
        self.commands = _documented_verify_commands()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _stage_one_download(self):
        """One installer on disk; a manifest listing all six, as published."""
        mine = self.dir / 'Copperplane_9.9.9_x64-setup.exe'
        mine.write_bytes(b'D' * 8192)

        others = [
            'Copperplane_9.9.9_aarch64.dmg', 'Copperplane_9.9.9_x64.dmg',
            'Copperplane_9.9.9_x64_en-US.msi', 'Copperplane_9.9.9_amd64.deb',
            'Copperplane_9.9.9_amd64.AppImage',
        ]
        lines = [f"{generate_checksums.sha256_of(mine)}  {mine.name}\n"]
        lines += [f"{'0' * 64}  {name}\n" for name in others]
        (self.dir / 'SHA256SUMS.txt').write_text(''.join(sorted(lines)), encoding='utf-8')
        return mine

    def _run_documented_command(self):
        command = self.commands[_PLATFORM]
        if _PLATFORM == 'Windows':
            script = self.dir / 'verify.ps1'
            script.write_text(command, encoding='utf-8')
            argv = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-File', str(script)]
            return subprocess.run(argv, cwd=self.dir, capture_output=True, text=True)
        return subprocess.run(command, cwd=self.dir, shell=True,
                              capture_output=True, text=True)

    def test_201_the_page_documents_a_command_for_every_platform_we_publish(self):
        self.assertEqual(
            sorted(self.commands), ['Linux', 'Windows', 'macOS'],
            "install.md's 'Verify your download' section no longer gives a command "
            "for every platform that has a published, downloadable installer"
        )

    def test_202_the_documented_command_succeeds_quietly_on_a_real_download(self):
        if _PLATFORM is None:
            self.skipTest(f"no documented command for sys.platform {sys.platform!r}")

        self._stage_one_download()
        result = self._run_documented_command()
        output = result.stdout + result.stderr

        self.assertIn('OK', output, f"documented command reported no success:\n{output}")
        self.assertNotIn(
            'FAILED', output,
            "the documented command reports FAILED for the installers a person did not "
            f"download -- healthy download, alarming output:\n{output}"
        )
        if _PLATFORM != 'Windows':
            self.assertEqual(result.returncode, 0, output)

    def test_203_the_documented_command_reports_a_corrupted_download(self):
        """Proves 202 is a check. If a flipped byte still passed, a quiet
        success would mean nothing at all."""
        if _PLATFORM is None:
            self.skipTest(f"no documented command for sys.platform {sys.platform!r}")

        mine = self._stage_one_download()
        damaged = bytearray(mine.read_bytes())
        damaged[64] ^= 0xFF
        mine.write_bytes(bytes(damaged))

        result = self._run_documented_command()
        output = result.stdout + result.stderr

        noticed = 'FAILED' in output or result.returncode != 0
        self.assertTrue(noticed, f"a corrupted installer verified clean:\n{output}")
