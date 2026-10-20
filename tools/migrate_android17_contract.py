"""Fixed publication-contract edits on the dedicated migration branch only."""
from __future__ import annotations
import ast
import textwrap
import subprocess
from migrate_android17 import BRANCH, ROOT, Changes


def replace_function(changes, path, function_name, replacement):
    source = changes.read(path)
    nodes = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.FunctionDef) and node.name == function_name]
    if len(nodes) != 1:
        raise ValueError('Expected one function: ' + path + ':' + function_name)
    node = nodes[0]
    lines = source.splitlines(keepends=True)
    body = textwrap.indent(textwrap.dedent(replacement).strip() + '\n', ' ' * node.col_offset)
    lines[node.lineno - 1:node.end_lineno] = [body]
    changes.write(path, ''.join(lines))


def add_import(changes, path, statement):
    source = changes.read(path)
    before = 0
    for node in ast.parse(source).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            before = node.end_lineno
    lines = source.splitlines(keepends=True)
    lines.insert(before, statement + '\n')
    changes.write(path, ''.join(lines))


def wrap_factory(changes, path, name):
    source = changes.read(path)
    nodes = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(nodes) != 1 or not isinstance(nodes[0].body[-1], ast.Return):
        raise ValueError('Expected one terminal factory return: ' + path)
    node = nodes[0].body[-1]
    value = ast.get_source_segment(source, node.value)
    replacement = ' ' * node.col_offset + 'return publication_report(' + value + ')\n'
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = [replacement]
    changes.write(path, ''.join(lines))
    add_import(changes, path, 'from backend.tests.android_runtime_fixtures import publication_report')


def migrate_publication(changes):
    path = 'backend/release_publication.py'
    replace_function(changes, path, '_require_supported_installation', '''
        def _require_supported_installation(report: dict, *, sha256: str) -> dict:
            tested = report.get('installation_evidence')
            if not isinstance(tested, dict) or tested.get('apk_sha256') != sha256:
                raise ReleaseUnavailable('installation_evidence_missing')
            if type(tested.get('schema_version')) is not int or tested['schema_version'] != 2:
                raise ReleaseUnavailable('installation_evidence_incomplete')
            runtimes = tested.get('runtimes')
            if not isinstance(runtimes, dict) or set(runtimes) != {'api37-4096', 'api37-16384'}:
                raise ReleaseUnavailable('installation_evidence_incomplete')
            required_checks = ('clean_install', 'upgrade', 'upgrade_launch', 'launch')
            for checks in runtimes.values():
                if not isinstance(checks, dict) or any(checks.get(key) is not True for key in required_checks):
                    raise ReleaseUnavailable('installation_evidence_incomplete')
            return tested
    ''')
    replace_function(changes, path, '_require_android_floor', '''
        def _require_android_floor(report: dict) -> None:
            for field in ('min_sdk', 'target_sdk'):
                if type(report.get(field)) is not int or report[field] != 37:
                    raise ReleaseUnavailable('unsupported_android_floor')
    ''')
    replace_function(changes, path, '_require_transcript_match', '''
        def _require_transcript_match(report: dict, tested: dict, *, sha256: str) -> None:
            if 'installation_tests' not in report:
                raise ReleaseUnavailable('runtime_installation_transcript_required')
            try:
                derived = from_ci_reports(report['installation_tests'], sha256)
            except InstallationEvidenceError as error:
                raise ReleaseUnavailable('installation_transcript_invalid') from error
            if tested != derived:
                raise ReleaseUnavailable('installation_transcript_conflict')
    ''')


def migrate_fixtures(changes):
    for path, name in (
        ('backend/tests/test_client_updates.py', 'evidence'),
        ('backend/tests/test_release_rollover.py', 'report'),
        ('backend/tests/test_release_recovery.py', 'report'),
    ):
        wrap_factory(changes, path, name)
    path = 'backend/tests/test_update_integration.py'
    changes.replace(path, "        return publish(self.root/'releases',apk,evidence,expected_certificate='c'*64)",
                    "        evidence = publication_report(evidence)\n        return publish(self.root/'releases',apk,evidence,expected_certificate='c'*64)")
    add_import(changes, path, 'from backend.tests.android_runtime_fixtures import publication_report')
    path = 'backend/tests/test_client_updates.py'
    replace_function(changes, path, 'test_android15_release_requires_both_real_transcripts', '''
        def test_current_release_requires_exact_os_and_complete_runtime_transcripts(self):
            evidence = self.evidence(24)
            incomplete = dict(evidence)
            incomplete.pop('installation_tests')
            with self.assertRaises(ReleaseUnavailable):
                publish(self.root, self.apk, incomplete, expected_certificate=CERT)
            for minimum in (34, 35, 36, 38, '37', True):
                invalid = dict(evidence, min_sdk=minimum)
                with self.subTest(minimum=minimum), self.assertRaises(ReleaseUnavailable):
                    publish(self.root, self.apk, invalid, expected_certificate=CERT)
            incomplete = dict(evidence, installation_tests=evidence['installation_tests'][:1])
            with self.assertRaises(ReleaseUnavailable):
                publish(self.root, self.apk, incomplete, expected_certificate=CERT)
            result = publish(self.root, self.apk, evidence, expected_certificate=CERT)
            self.assertEqual(result.min_android_api, 37)
    ''')
    changes.optional(path, "['36']", "['runtimes']['api37-4096']")
    path = 'backend/tests/test_release_recovery.py'
    replace_function(changes, path, 'test_retry_cannot_change_prepared_minimum_android', '''
        def test_retry_cannot_change_prepared_minimum_android(self):
            self.interrupt_before_activation()
            report = self.report()
            report['min_sdk'] = 38
            with self.assertRaisesRegex(ReleaseUnavailable, 'unsupported_android_floor'):
                publication.publish(self.root, self.apk, report,
                                    expected_certificate=CERTIFICATE, now=200)
            self.assertFalse((self.root / PACKAGE / 'current.json').exists())
    ''')


def main():
    branch = subprocess.check_output(['git', 'symbolic-ref', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
    if branch != BRANCH:
        raise ValueError('Dedicated review branch required')
    changes = Changes(ROOT)
    migrate_publication(changes)
    migrate_fixtures(changes)
    changes.finish()


if __name__ == '__main__':
    main()
