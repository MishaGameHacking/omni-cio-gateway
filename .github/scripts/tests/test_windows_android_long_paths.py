"""Real committed long-path fixtures; no Gradle, broker or cloud calls.

Every tracked fixture is checked, including paths exceeding Windows MAX_PATH.
The existing CI runs these tests on the authorized owner laptop.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'windows_android_ci.py'
SPEC = importlib.util.spec_from_file_location('windows_android_ci_long_path_test', MODULE)
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


def fixture_path(path):
    # Independent fixture I/O; using ci.io_path here would hide its own defects.
    return Path('\\\\?\\' + str(path)) if os.name == 'nt' else path


class LongCommittedPathTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix='analyst-ci-long-path-')).resolve()
        self.addCleanup(shutil.rmtree, fixture_path(self.base))
        self.root = self.base / 'source'
        self.root.mkdir()
        self.relative = 'references/' + 'a' * 120 + '/' + 'b' * 120 + '/expected.png'
        self.file = self.root / self.relative
        self.assertGreater(len(str(self.file)), 260)
        self.assertTrue(all(len(part) <= 255 for part in self.file.parts))
        fixture_path(self.file.parent).mkdir(parents=True)
        self.data = b'fixed synthetic reference bytes\n'
        fixture_path(self.file).write_bytes(self.data)
        (self.root / 'empty.py').write_bytes(b'')
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic Test')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'core.longpaths', 'true')
        self.git('add', '--', self.relative, 'empty.py')
        self.git('commit', '-qm', 'synthetic long-path source')
        self.head = self.git('rev-parse', 'HEAD').decode().strip()
        self.identity = {'event': 'workflow_dispatch', 'tested_merge_sha': self.head}

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, stdin=subprocess.DEVNULL,
                              capture_output=True, check=True, timeout=30).stdout

    def test_long_file_is_included_with_actual_git_and_sha256_identities(self):
        inventory = ci.source_identity(self.root, self.identity)
        self.assertEqual(set(inventory['files']), {self.relative, 'empty.py'})
        expected_blob = self.git('rev-parse', 'HEAD:' + self.relative).decode().strip()
        self.assertEqual(inventory['files'][self.relative], {
            'bytes': len(self.data), 'sha256': hashlib.sha256(self.data).hexdigest(),
            'git_blob': expected_blob,
        })
        self.assertEqual(ci.read_bytes(self.file, len(self.data)), self.data)
        self.assertEqual(inventory['files']['empty.py']['bytes'], 0)

    def test_git_stat_cache_cannot_hide_changed_long_file(self):
        self.git('update-index', '--assume-unchanged', '--', self.relative)
        fixture_path(self.file).write_bytes(b'changed synthetic reference bytes\n')
        with self.assertRaisesRegex(RuntimeError, 'source_bytes_differ_from_tested_commit'):
            ci.source_identity(self.root, self.identity)

    def test_missing_long_file_identifies_only_repository_relative_path(self):
        fixture_path(self.file).unlink()
        expected = '^' + re.escape('source_file_missing:' + self.relative) + '$'
        with self.assertRaisesRegex(RuntimeError, expected):
            ci.source_identity(self.root, self.identity)

    def test_missing_ordinary_file_is_also_rejected(self):
        (self.root / 'empty.py').unlink()
        with self.assertRaisesRegex(RuntimeError, '^source_file_missing:empty.py$'):
            ci.source_identity(self.root, self.identity)

    def test_extended_path_does_not_bypass_bounded_reads(self):
        maximum = len(self.data) - 1
        with self.assertRaisesRegex(RuntimeError, 'input_size_invalid'):
            ci.read_bytes(self.file, maximum)

    def test_extended_path_does_not_accept_a_hardlink(self):
        external = self.base / 'external-reference.bin'
        external.write_bytes(self.data)
        fixture_path(self.file).unlink()
        os.link(fixture_path(external), fixture_path(self.file))
        with self.assertRaisesRegex(RuntimeError, 'hardlinked_file'):
            ci.source_identity(self.root, self.identity)

    @unittest.skipUnless(os.name == 'nt', 'Windows path grammar; the owner Windows suite executes this test')
    def test_windows_io_does_not_admit_unc_device_relative_or_ambiguous_paths(self):
        invalid = ('relative/file', r'C:relative', r'\\server\share\file',
                   r'\\?\C:\file', r'\\.\C:\file', r'C:\one\..\two',
                   'C:\\file.', 'C:\\file ', 'C:\\file:stream')
        for value in invalid:
            with self.subTest(path=value):
                with self.assertRaises(RuntimeError):
                    ci.io_path(value)


if __name__ == '__main__':
    unittest.main()
