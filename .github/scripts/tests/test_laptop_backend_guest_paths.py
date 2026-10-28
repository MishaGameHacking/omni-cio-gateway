"""Pure guest-root grammar tests; never creates a WSL run or contacts a host."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('guest_root_grammar_test',
    Path(__file__).resolve().parents[1] / 'laptop_backend_guest.py')
guest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guest)


class GuestRunNameTests(unittest.TestCase):
    def test_existing_run_name_is_reconstructed_from_numbers(self):
        result = guest._guest_run_name('/opt/analyst-ci/runs/backend-40557208858-1')
        self.assertEqual(result, 'backend-40557208858-1')
        self.assertNotIn('/', result)
        self.assertNotIn('\\', result)

    def test_maximum_identifiers_remain_bounded(self):
        value = '/opt/analyst-ci/runs/backend-' + '9'*20 + '-' + '9'*5
        self.assertEqual(guest._guest_run_name(value), 'backend-' + '9'*20 + '-' + '9'*5)

    def test_escape_noncanonical_and_other_roots_are_refused(self):
        invalid = (
            '/tmp/backend-1-1', 'backend-1-1', '/opt/analyst-ci/runs/backend-1-1/../../outside',
            '/opt/analyst-ci/runs/../runs/backend-1-1', '/opt/analyst-ci/runs//backend-1-1',
            '/opt/analyst-ci/runs/./backend-1-1', '//opt/analyst-ci/runs/backend-1-1',
            '/opt/analyst-ci/runs/backend-1-1/', '/opt/analyst-ci/runs/backend-1-1\n',
            '/opt/analyst-ci/runs/backend-1-1\0', '/opt/analyst-ci/runs/backend-1-1:stream',
            '/opt/analyst-ci/runs/backend-1-1\\outside',
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, '^invalid_guest_run_root$'):
                    guest._guest_run_name(value)

    def test_non_ascii_zero_sign_and_overlong_identifiers_are_refused(self):
        invalid = ('0-1', '1-0', '01-1', '1-01', '-1-1', '+1-1', '1-+1',
                   '1e2-1', '1.0-1', '1１-1', '1-1１', '9'*21+'-1', '1-'+'9'*6)
        for suffix in invalid:
            value = '/opt/analyst-ci/runs/backend-' + suffix
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, '^invalid_guest_run_root$'):
                    guest._guest_run_name(value)

    def test_non_string_inputs_are_refused(self):
        for value in (None, False, 1, [], {}, Path('/opt/analyst-ci/runs/backend-1-1')):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, '^invalid_guest_run_root$'):
                    guest._guest_run_name(value)


if __name__ == '__main__':
    unittest.main()
