"""Synthetic failed-worker receipts; no runner files, network or child processes."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('bounded_ci_diagnostics_test',
    Path(__file__).resolve().parents[1] / 'ci_failure_diagnostics.py')
diag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diag)


class FailedWorkerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.state = Path('/synthetic/current-job/state')
        self.requested = []
        self.files = {'build-worker.log': b'worker failed\n',
                      'build-failure.log': b'RuntimeError: step_failed:host-tests\n'}

    def reader(self, path, limit):
        self.assertEqual(path.parent, self.state)
        self.requested.append((path.name, limit))
        if path.name not in self.files:
            raise FileNotFoundError(path.name)
        data = self.files[path.name]
        if len(data) > limit:
            raise RuntimeError('synthetic_size_limit')
        return data

    def steps(self, rows):
        self.files['build-steps.json'] = json.dumps({'steps': rows}).encode()

    def test_failing_step_uses_derived_filename_not_receipt_path(self):
        self.steps([{'label': 'prepare', 'exit_code': 0},
                    {'label': 'host-tests', 'exit_code': 1, 'log': '/private/never-read'}])
        self.files['build-steps-02-host-tests.log'] = b'actual synthetic assertion failure'
        value = diag.failure_evidence(self.state, 'build', self.reader)
        self.assertEqual(value['failed_steps'][0]['log']['tail'], 'actual synthetic assertion failure')
        self.assertEqual(value['failed_steps'][0]['exit_code'], 1)
        self.assertNotIn('prepare', [row['label'] for row in value['failed_steps']])
        self.assertTrue(all('/private/' not in name for name, _ in self.requested))

    def test_invalid_label_never_becomes_a_path(self):
        for label in ('../escape', '/absolute', 'C:drive', 'space label', 'x'*81, None):
            self.steps([{'label': label, 'exit_code': 1}])
            with self.subTest(label=label):
                value = diag.failure_evidence(self.state, 'build', self.reader)
                self.assertEqual(value['steps_error_type'], 'InvalidStepLabel')
                self.assertEqual(value['failed_steps'], [])

    def test_logs_are_bounded_and_missing_traceback_is_not_a_success(self):
        self.files['build-worker.log'] = b'x' * (diag.TAIL_CHARACTERS + 200)
        del self.files['build-failure.log']
        self.steps([])
        value = diag.failure_evidence(self.state, 'build', self.reader)
        self.assertEqual(len(value['worker']['tail']), diag.TAIL_CHARACTERS)
        self.assertFalse(value['traceback']['available'])
        self.assertEqual(value['status'], 'failed_worker_diagnostic_not_acceptance')

    def test_json_framing_does_not_emit_raw_actions_commands(self):
        self.files['build-worker.log'] = b'\n::error::untrusted synthetic output\n'
        self.steps([])
        output = io.StringIO()
        with redirect_stdout(output):
            diag.print_worker_failure(self.state, 'build', self.reader)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith('WINDOWS_ANDROID_FAILURE_EVIDENCE='))
        self.assertIn('::error::', json.loads(lines[0].partition('=')[2])['worker']['tail'])

    def test_invalid_phase_is_rejected_before_any_file_read(self):
        with self.assertRaises(ValueError):
            diag.failure_evidence(self.state, '../old-job', self.reader)
        self.assertEqual(self.requested, [])

    def test_missing_or_malformed_steps_preserve_worker_diagnostic(self):
        for raw in (b'not-json', b'[]', b'{"steps":null}', b'{"steps":[]}'):
            self.files['build-steps.json'] = raw
            with self.subTest(raw=raw):
                value = diag.failure_evidence(self.state, 'build', self.reader)
                self.assertTrue(value['worker']['available'])
                self.assertEqual(value['failed_steps'], [])

    def test_excessive_step_list_is_rejected_without_derived_log_reads(self):
        self.steps([{'label': 'host-tests', 'exit_code': 1}] * 101)
        value = diag.failure_evidence(self.state, 'build', self.reader)
        self.assertEqual(value['steps_error_type'], 'InvalidStepShape')
        self.assertEqual(len(self.requested), 3)


if __name__ == '__main__':
    unittest.main()
