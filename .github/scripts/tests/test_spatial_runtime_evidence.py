"""Regression coverage for imports and measured two-axis mesh runtime identity."""
from pathlib import Path
import ast
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import kernel_page_size
from spatial_runtime_evidence import observe_runtime
from spatial_ui_probe import _SpatialSession


def command_for(*, api='37\n', abi='x86_64\n', page='4096\n'):
    outputs = {
        ('shell', 'getprop', 'ro.build.version.sdk'): api,
        ('shell', 'getprop', 'ro.product.cpu.abi'): abi,
        ('shell', 'getconf', 'PAGE_SIZE'): page,
        ('shell', 'settings', 'put', 'system', 'font_scale', '1.0'): '',
    }
    return Mock(side_effect=lambda *args: outputs[args])


class ReachedNativeChecks(Exception):
    """Stop the fixture-entry test before touching a device or file."""


class SpatialRuntimeTests(unittest.TestCase):
    def test_four_kb_measurement_uses_four_kb_image(self):
        command = command_for()
        result = observe_runtime(command)
        self.assertEqual(result['sdk'], 37)
        self.assertEqual(result['page_size_bytes'], 4096)
        self.assertEqual(result['system_image'], 'system-images;android-37.0;google_apis;x86_64')
        self.assertEqual(command.call_count, 3)

    def test_sixteen_kb_measurement_does_not_take_default_image(self):
        result = observe_runtime(command_for(page='16384\n'))
        self.assertEqual(result['page_size_bytes'], 16384)
        self.assertEqual(result['system_image'], 'system-images;android-37.0;google_apis_ps16k;x86_64')

    def test_unsupported_page_size_does_not_certify_meshes(self):
        command = command_for(page='8192')
        with self.assertRaises(ValueError):
            observe_runtime(command)

    def test_unsupported_api_does_not_certify_meshes(self):
        command = command_for(api='36')
        with self.assertRaises(ValueError):
            observe_runtime(command)

    def test_unexpected_abi_is_rejected(self):
        command = command_for(abi='arm64-v8a')
        with self.assertRaises(AssertionError):
            observe_runtime(command)

    def test_invalid_measurements_are_not_coerced(self):
        for value in ('', '-37', '37.0', '٣٧', '37\n38', '0' * 33, None):
            command = command_for(api=value)
            with self.subTest(value=value), self.assertRaises(AssertionError):
                observe_runtime(command)

    def test_command_failure_is_not_replaced_by_a_default(self):
        command = Mock(side_effect=RuntimeError('device disconnected'))
        with self.assertRaisesRegex(RuntimeError, 'device disconnected'):
            observe_runtime(command)

    def test_spatial_entry_reaches_native_checks_on_both_profiles(self):
        for page in ('4096', '16384'):
            session = _SpatialSession(SimpleNamespace(command=command_for(page=page)))
            with self.subTest(page=page), patch.object(session, 'launch', return_value={}), \
                    patch.object(session, 'native_controls', side_effect=ReachedNativeChecks):
                with self.assertRaises(ReachedNativeChecks):
                    session.run()
            self.assertEqual(session.records, [{'scenario': 'force-stopped-fixture-startup'}])

    def test_kernel_imports_resolve_even_when_nested_inside_functions(self):
        for source in sorted(SCRIPTS.glob('*.py')):
            tree = ast.parse(source.read_text(encoding='utf-8-sig'))
            names = [alias.name for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module == 'kernel_page_size'
                     for alias in node.names]
            self.assertEqual([name for name in names if not hasattr(kernel_page_size, name)], [], source.name)


if __name__ == '__main__':
    unittest.main()
