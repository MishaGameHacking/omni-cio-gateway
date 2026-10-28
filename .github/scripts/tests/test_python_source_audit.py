"""The audit covers workspace sources without running their imports or bodies."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_python_sources import audit, check_source, tracked_sources


class PythonSourceAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, name, contents):
        (self.root / name).write_bytes(contents)

    def test_valid_source_is_not_executed(self):
        self.write('valid.py', b'raise RuntimeError("must not execute")\n')
        self.assertIsNone(check_source(self.root, 'valid.py'))

    def test_invalid_control_flow_is_detected(self):
        self.write('bad.py', b'return 1\n')
        result = check_source(self.root, 'bad.py')
        self.assertEqual(result['error'], 'SyntaxError')
        self.assertEqual(result['line'], 1)

    def test_encoding_cookie_is_honoured(self):
        self.write('encoded.py', b'# coding: latin-1\ntext = "caf\xe9"\n')
        self.assertIsNone(check_source(self.root, 'encoded.py'))

    def test_path_escape_fails_closed(self):
        result = check_source(self.root, '../outside.py')
        self.assertEqual(result['error'], 'ValueError')

    def test_findings_are_sorted_and_do_not_contain_source(self):
        self.write('b.py', b'private_literal = (\n')
        self.write('a.py', b'private_literal = (\n')
        report = audit(self.root, ['b.py', 'a.py', 'a.py'])
        self.assertEqual(report['files_checked'], 2)
        self.assertEqual([item['path'] for item in report['failures']], ['a.py', 'b.py'])
        self.assertNotIn('private_literal', str(report))

    def test_git_index_conflict_is_not_ignored(self):
        response = subprocess.CompletedProcess([], 0, stdout=b'unmerged\0')
        with patch('audit_python_sources.subprocess.run', return_value=response):
            with self.assertRaisesRegex(ValueError, 'unresolved conflicts'):
                tracked_sources(self.root)

    def test_tracked_paths_support_spaces_and_are_sorted(self):
        responses = [subprocess.CompletedProcess([], 0, stdout=b''),
                     subprocess.CompletedProcess([], 0, stdout=b'z.py\0a b.py\0')]
        with patch('audit_python_sources.subprocess.run', side_effect=responses):
            names = tracked_sources(self.root)
        self.assertEqual(names, ['a b.py', 'z.py'])

    def test_real_git_workspace_includes_new_source_and_excludes_ignored_outputs(self):
        subprocess.run(['git', 'init', '--quiet'], cwd=self.root,
                       capture_output=True, check=True, timeout=30)
        self.write('.gitignore', b'build/\n__pycache__/\n')
        self.write('tracked.py', b'raise RuntimeError("must not execute")\n')
        subprocess.run(['git', 'add', '--', '.gitignore', 'tracked.py'], cwd=self.root,
                       capture_output=True, check=True, timeout=30)
        (self.root / 'backend').mkdir()
        (self.root / 'build').mkdir()
        (self.root / 'backend' / '__pycache__').mkdir()
        self.write('backend/new_module.py', b'return 1\n')
        self.write('build/generated.py', b'return 2\n')
        self.write('backend/__pycache__/cached.py', b'return 3\n')

        names = tracked_sources(self.root)
        self.assertEqual(names, ['backend/new_module.py', 'tracked.py'])
        report = audit(self.root, names)
        self.assertEqual(report['files_checked'], 2)
        self.assertEqual(
            [(item['path'], item['error'], item['line']) for item in report['failures']],
            [('backend/new_module.py', 'SyntaxError', 1)],
        )


if __name__ == '__main__':
    unittest.main()
