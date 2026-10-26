"""Isolated Git/tar/ZIP/process regressions for the laptop backend gate.

These fixtures use temporary files and test-only subprocesses, never WSL,
runner state, production data, credentials, or a network connection.
"""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


SCRIPTS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load('laptop_backend_ci')
guest = load('laptop_backend_guest')
IDENTITY = {'event_name': 'pull_request', 'tested_merge_sha': 'a' * 40,
            'pr_head_sha': 'b' * 40, 'pr_base_sha': 'c' * 40}
JUNIT = b'<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="synthetic" name="passes"/></testsuite></testsuites>'


class GitSourceBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='backend-ci-source-test-')
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.root = self.folder / 'checkout'
        self.root.mkdir()
        self.env = host.host_environment()
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_AUTHOR_NAME='Synthetic CI', GIT_AUTHOR_EMAIL='ci@example.invalid',
                        GIT_COMMITTER_NAME='Synthetic CI', GIT_COMMITTER_EMAIL='ci@example.invalid')
        self.git('init', '--initial-branch=main')
        self.git('config', 'core.autocrlf', 'false')
        (self.root / 'base.txt').write_bytes(b'base\n')
        self.git('add', 'base.txt')
        self.git('commit', '-m', 'synthetic base')
        base = self.git('rev-parse', 'HEAD')
        (self.root / 'backend.py').write_bytes(b'VALUE = 1\n')
        self.git('add', 'backend.py')
        self.git('commit', '-m', 'synthetic PR head')
        head = self.git('rev-parse', 'HEAD')
        tree = self.git('rev-parse', 'HEAD^{tree}')
        merge = self.git('commit-tree', tree, '-p', base, '-p', head, data=b'synthetic merge\n')
        self.git('reset', '--hard', merge)
        self.identity = {'event_name': 'pull_request', 'tested_merge_sha': merge,
                         'pr_head_sha': head, 'pr_base_sha': base}

    def git(self, *arguments, data=None):
        result = subprocess.run(['git', *arguments], cwd=self.root, env=self.env,
                                input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=True, timeout=20)
        return result.stdout.decode().strip()

    def test_real_merge_inventory_binds_both_parents_and_file_bytes(self):
        result = host.inventory(self.root, self.identity, self.env)
        for key, value in self.identity.items():
            self.assertEqual(result[key], value)
        files = {row['path']: row for row in result['files']}
        self.assertEqual(set(files), {'base.txt', 'backend.py'})
        self.assertEqual(files['backend.py']['sha256'], host.sha(b'VALUE = 1\n'))

    def test_shallow_checkout_still_verifies_raw_merge_parents(self):
        shallow = self.folder / 'shallow'
        self.git('clone', '--depth=1', self.root.as_uri(), str(shallow))
        self.assertEqual(host.command(['git', 'rev-parse', '--is-shallow-repository'],
                                      shallow, self.env).strip(), b'true')
        result = host.inventory(shallow, self.identity, self.env)
        self.assertEqual(result['tested_merge_sha'], self.identity['tested_merge_sha'])

    def test_head_checkout_cannot_replace_merge_integration(self):
        self.git('checkout', '--detach', self.identity['pr_head_sha'])
        with self.assertRaisesRegex(RuntimeError, 'checkout_is_not_exact_event_merge'):
            host.inventory(self.root, self.identity, self.env)

    def test_correct_merge_with_wrong_pr_head_or_base_is_rejected(self):
        for key in ('pr_head_sha', 'pr_base_sha'):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'test_merge_does_not_bind'):
                host.inventory(self.root, {**self.identity, key: 'f' * 40}, self.env)

    def test_changed_tracked_source_is_rejected(self):
        (self.root / 'backend.py').write_bytes(b'VALUE = 2\n')
        with self.assertRaisesRegex(RuntimeError, 'checkout_contains_changes'):
            host.inventory(self.root, self.identity, self.env)

    def test_assume_unchanged_does_not_bypass_actual_git_blob_check(self):
        self.git('update-index', '--assume-unchanged', 'backend.py')
        (self.root / 'backend.py').write_bytes(b'VALUE = 2\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        with self.assertRaisesRegex(RuntimeError, 'checkout_bytes_differ_from_commit:backend.py'):
            host.inventory(self.root, self.identity, self.env)

    def test_untracked_python_is_rejected_before_transport(self):
        (self.root / 'injected.py').write_bytes(b'VALUE = 99\n')
        with self.assertRaisesRegex(RuntimeError, 'checkout_contains_changes_or_untracked_sources'):
            host.inventory(self.root, self.identity, self.env)


class SourceArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='backend-ci-archive-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'checkout'
        self.source.mkdir()
        self.archive = self.root / 'source.tar'
        self.data = b'VALUE = 1\n'

    def fixture(self, name='backend/app.py', *, payload=None, members=None):
        payload = self.data if payload is None else payload
        manifest = {**IDENTITY, 'complete_source_sha256': 'd' * 64,
                    'files': [{'path': name, 'bytes': len(self.data), 'sha256': host.sha(self.data), 'mode': 0o644}]}
        with tarfile.open(self.archive, 'w') as archive:
            for member_name in ([name] if members is None else members):
                entry = tarfile.TarInfo(member_name)
                entry.size = len(payload)
                archive.addfile(entry, io.BytesIO(payload))
        return manifest

    def test_exact_manifest_extracts_real_source_bytes(self):
        manifest = self.fixture()
        identities = guest.extract_source(self.archive, manifest, self.source)
        self.assertEqual((self.source / 'backend/app.py').read_bytes(), self.data)
        self.assertEqual(set(identities), {'backend/app.py'})

    def test_changed_archived_file_is_rejected_before_writing(self):
        manifest = self.fixture(payload=b'VALUE = 2\n')
        with self.assertRaisesRegex(RuntimeError, 'archived_source_bytes_changed'):
            guest.extract_source(self.archive, manifest, self.source)
        self.assertEqual(list(self.source.iterdir()), [])

    def test_traversal_and_windows_escape_names_are_rejected(self):
        for name in ('../outside.py', '/outside.py', '..\\outside.py', 'C:/outside.py', '.git/config'):
            with self.subTest(name=name):
                manifest = self.fixture(name)
                with self.assertRaisesRegex(RuntimeError, 'unsafe_source_archive_entry'):
                    guest.extract_source(self.archive, manifest, self.source)
                self.assertFalse((self.root / 'outside.py').exists())
                self.assertEqual(list(self.source.iterdir()), [])

    def test_missing_or_duplicate_archive_members_cannot_match_by_set_only(self):
        for members in (['other.py'], ['backend/app.py', 'backend/app.py']):
            with self.subTest(members=members):
                manifest = self.fixture(members=members)
                with self.assertRaisesRegex(RuntimeError, 'archive_source_inventory_mismatch'):
                    guest.extract_source(self.archive, manifest, self.source)

    def test_symlink_entry_is_rejected_without_creating_a_link(self):
        manifest = self.fixture()
        with tarfile.open(self.archive, 'w') as archive:
            entry = tarfile.TarInfo('backend/app.py')
            entry.type, entry.linkname = tarfile.SYMTYPE, '../outside.py'
            archive.addfile(entry)
        with self.assertRaisesRegex(RuntimeError, 'unsafe_source_archive_entry'):
            guest.extract_source(self.archive, manifest, self.source)
        self.assertEqual(list(self.source.iterdir()), [])

    def test_transport_hashes_bind_both_archive_and_manifest(self):
        manifest = self.fixture()
        path = self.root / 'manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        archive_hash, manifest_hash = host.sha(self.archive.read_bytes()), host.sha(path.read_bytes())
        self.assertEqual(guest.load_manifest(self.archive, archive_hash, path, manifest_hash), manifest)
        for wrong_archive, wrong_manifest in ((True, False), (False, True)):
            with self.subTest(archive=wrong_archive, manifest=wrong_manifest), self.assertRaises(RuntimeError):
                guest.load_manifest(self.archive, 'f' * 64 if wrong_archive else archive_hash,
                                    path, 'f' * 64 if wrong_manifest else manifest_hash)


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='backend-ci-evidence-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive = self.root / 'evidence.zip'
        self.manifest = {**IDENTITY, 'complete_source_sha256': 'd' * 64}
        self.entries = {name + '.log': ('passed:' + name).encode() for name in host.GUEST_STEPS}
        self.entries['backend-tests.xml'] = JUNIT
        self.report = {**self.manifest, 'status': 'passed', 'changed_sources': [],
                       'junit_sha256': host.sha(JUNIT),
                       'steps': [{'name': name, 'exit_code': 0, 'sha256': host.sha(self.entries[name + '.log'])}
                                 for name in host.GUEST_STEPS]}

    def save(self, *, report=None, entries=None):
        files = dict(self.entries if entries is None else entries)
        files['linux-test-report.json'] = json.dumps(self.report if report is None else report).encode()
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name, data in files.items():
                archive.writestr(name, data)

    def test_complete_pass_is_verified_and_retains_only_named_evidence(self):
        self.save()
        self.assertEqual(host.inspect_evidence(self.archive, self.manifest), self.report)
        destination = self.root / 'retained'
        host.retain_evidence(self.archive, destination)
        self.assertEqual((destination / 'backend-tests.xml').read_bytes(), JUNIT)
        self.assertEqual({path.name for path in destination.iterdir()},
                         set(self.entries) | {'linux-test-report.json'})

    def test_each_source_binding_is_independently_required(self):
        for key in ('tested_merge_sha', 'pr_head_sha', 'pr_base_sha', 'complete_source_sha256'):
            report = {**self.report, key: 'f' * len(self.report[key])}
            self.save(report=report)
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'linux_evidence_is_not_exact_source'):
                host.inspect_evidence(self.archive, self.manifest)

    def test_failed_missing_or_source_mutating_step_cannot_become_green(self):
        reports = []
        for value in ('failed', 'failed_integrity'):
            reports.append({**self.report, 'status': value})
        reports.append({**self.report, 'steps': self.report['steps'][:-1]})
        reports.append({**self.report, 'changed_sources': ['backend/app.py']})
        nonzero = copy.deepcopy(self.report)
        nonzero['steps'][-2]['exit_code'] = 1
        reports.append(nonzero)
        for report in reports:
            self.save(report=report)
            with self.subTest(report=report), self.assertRaisesRegex(RuntimeError, 'linux_backend_gate_failed'):
                host.inspect_evidence(self.archive, self.manifest)

    def test_tampered_log_and_junit_bytes_fail_their_hashes(self):
        for name in ('backend-full-suite.log', 'backend-tests.xml'):
            self.save(entries={**self.entries, name: b'changed'})
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'linux_(log|junit)_changed'):
                host.inspect_evidence(self.archive, self.manifest)

    def test_empty_failed_and_all_skipped_junit_fail_even_with_matching_hash(self):
        bad = [
            b'<testsuites/>',
            b'<testsuite tests="0" failures="0" errors="0"/>',
            b'<testsuite tests="1" failures="1" errors="0"><testcase><failure/></testcase></testsuite>',
            b'<testsuite tests="1" failures="0" errors="1"><testcase><error/></testcase></testsuite>',
            b'<testsuite tests="1" failures="0" errors="0" skipped="1"><testcase><skipped/></testcase></testsuite>',
            b'<testsuite tests="1" failures="0" errors="0"><testcase><failure/></testcase></testsuite>',
            b'not xml',
        ]
        for data in bad:
            self.save(report={**self.report, 'junit_sha256': host.sha(data)},
                      entries={**self.entries, 'backend-tests.xml': data})
            with self.subTest(junit=data, gate='host'), self.assertRaises((RuntimeError, ET.ParseError)):
                host.inspect_evidence(self.archive, self.manifest)
            with self.subTest(junit=data, gate='guest'), self.assertRaises((RuntimeError, ET.ParseError)):
                guest.validate_junit(data)

    def test_path_escape_in_evidence_cannot_write_outside_retained_folder(self):
        for name in ('../outside.log', '..\\outside.log', 'C:/outside.log'):
            self.save(entries={**self.entries, name: b'synthetic'})
            destination = self.root / 'retained'
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'invalid_linux_evidence_inventory'):
                host.retain_evidence(self.archive, destination)
            self.assertFalse(destination.exists())
            self.assertFalse((self.root / 'outside.log').exists())

    def test_failed_local_child_preserves_stderr_and_cannot_return_success_hash(self):
        log = self.root / 'failed.log'
        with self.assertRaisesRegex(RuntimeError, 'windows_test_step_failed'):
            host.test_command([sys.executable, '-c',
                               'import sys; print("synthetic failure", file=sys.stderr); sys.exit(23)'],
                              self.root, host.host_environment(), log, timeout=15)
        self.assertIn('synthetic failure', log.read_text())


if __name__ == '__main__':
    unittest.main()
