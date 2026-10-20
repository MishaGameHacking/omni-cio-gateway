"""Filesystem and process-boundary regressions; no SDK download or live device."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import prepare_android_sdk as sdk


class PrepareSdkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'SDK with spaces'
        self.root.mkdir()
        self.root = self.root.resolve(strict=True)
        name = 'android.exe' if os.name == 'nt' else 'android'
        self.cli = self.root / 'cmdline-tools/latest/bin' / name
        self.cli.parent.mkdir(parents=True)
        self.cli.write_bytes(b'test-only native executable fixture')
        self.environment = patch.dict(os.environ, {'ANDROID_CLI_PATH': str(self.cli)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def install(self, command, **kwargs):
        package = command[-1].replace('/', ';')
        self.write_package(package)
        return subprocess.CompletedProcess(command, 0)

    def write_package(self, package):
        directory = self.root.joinpath(*package.split(';'))
        for payload in sdk._payloads(package):
            path = directory / payload
            path.parent.mkdir(parents=True, exist_ok=True)
            data = b'fixture payload'
            if payload == 'source.properties':
                data = b'AndroidVersion.ApiLevel=37\nSystemImage.Abi=x86_64\n'
            path.write_bytes(data)

    def test_build_packages_use_current_cli_and_verify_payloads(self):
        with patch.object(sdk.subprocess, 'run', side_effect=self.install) as run:
            sdk.prepare(self.root, runtime=False)
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:4], [str(self.cli), '--sdk=' + str(self.root), 'sdk', 'install'])
            self.assertEqual(call.kwargs['timeout'], 600)
            self.assertIs(call.kwargs['check'], True)
            self.assertNotIn('shell', call.kwargs)
        self.assertEqual([c.args[0][-1] for c in run.call_args_list],
                         [p.replace(';', '/') for p in sdk.required_sdk_packages()[:2]])

    def test_runtime_profiles_are_not_replaced_by_an_older_os(self):
        with patch.object(sdk.subprocess, 'run', side_effect=self.install) as run:
            sdk.prepare(self.root, runtime=True)
        self.assertEqual([c.args[0][-1] for c in run.call_args_list],
                         [p.replace(';', '/') for p in sdk.required_sdk_packages()[2:]])

    def test_successful_exit_without_payload_is_not_success(self):
        with patch.object(sdk.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'payload missing'):
                sdk.prepare(self.root, runtime=False)
        self.assertEqual(run.call_count, 1)

    def test_nonzero_exit_is_not_retried_or_downgraded(self):
        failure = subprocess.CalledProcessError(1, ['test-only'])
        with patch.object(sdk.subprocess, 'run', side_effect=failure) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                sdk.prepare(self.root, runtime=False)
        self.assertEqual(run.call_count, 1)

    def test_timeout_is_not_retried(self):
        failure = subprocess.TimeoutExpired(['test-only'], 600)
        with patch.object(sdk.subprocess, 'run', side_effect=failure) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                sdk.prepare(self.root, runtime=False)
        self.assertEqual(run.call_count, 1)

    def test_missing_cli_fails_before_any_process(self):
        self.cli.unlink()
        with patch.object(sdk.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'CLI is required'):
                sdk.prepare(self.root, runtime=False)
        run.assert_not_called()

    def test_explicit_external_native_cli_is_supported(self):
        other = Path(self.temp.name).resolve(strict=True) / self.cli.name
        other.write_bytes(b'test-only')
        with patch.dict(os.environ, {'ANDROID_CLI_PATH': str(other)}):
            self.assertEqual(sdk._cli(self.root), other)

    def test_relative_and_batch_cli_are_rejected(self):
        batch = self.root / 'android.cmd'
        batch.write_text('test-only', encoding='utf-8')
        for value in ('android', str(batch)):
            with self.subTest(value=value), patch.dict(os.environ, {'ANDROID_CLI_PATH': value}):
                with self.assertRaises(RuntimeError):
                    sdk._cli(self.root)

    def test_sdk_local_cli_is_default(self):
        os.environ.pop('ANDROID_CLI_PATH', None)
        self.assertEqual(sdk._cli(self.root), self.cli)

    def test_wrong_api_is_rejected(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        properties = self.root.joinpath(*package.split(';')) / 'source.properties'
        properties.write_text('AndroidVersion.ApiLevel=36\n', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'API does not match'):
            sdk._verify_package(self.root, package)

    def test_preview_is_not_release(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        properties = self.root.joinpath(*package.split(';')) / 'source.properties'
        properties.write_text('AndroidVersion.ApiLevel=37\nAndroidVersion.CodeName=Preview\n', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'Preview SDK'):
            sdk._verify_package(self.root, package)

    def test_image_abi_is_verified(self):
        package = sdk.required_sdk_packages()[-1]
        self.write_package(package)
        properties = self.root.joinpath(*package.split(';')) / 'source.properties'
        properties.write_text('AndroidVersion.ApiLevel=37\nSystemImage.Abi=arm64-v8a\n', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'unexpected ABI'):
            sdk._verify_package(self.root, package)

    def test_empty_payload_is_not_installed(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        payload = self.root.joinpath(*package.split(';')) / 'android.jar'
        payload.write_bytes(b'')
        with self.assertRaisesRegex(RuntimeError, 'payload missing'):
            sdk._verify_package(self.root, package)

    def test_property_ambiguity_and_size_are_rejected(self):
        path = self.root / 'properties'
        inputs = ('AndroidVersion.ApiLevel=37\nAndroidVersion.ApiLevel=36\n',
                  'no separator', '=no key', 'x' * (sdk.MAX_PROPERTIES_BYTES + 1))
        for text in inputs:
            with self.subTest(length=len(text)):
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(RuntimeError):
                    sdk._properties(path)

    def test_property_comments_and_whitespace_are_valid(self):
        path = self.root / 'properties'
        path.write_text('# SDK\n\n! comment\n AndroidVersion.ApiLevel = 37 \n', encoding='utf-8')
        self.assertEqual(sdk._properties(path), {'AndroidVersion.ApiLevel': '37'})

    def test_nonboolean_mode_does_not_invoke_tool(self):
        with patch.object(sdk.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                sdk.prepare(self.root, runtime='false')
        run.assert_not_called()

    def test_root_must_be_directory(self):
        with patch.object(sdk.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                sdk.prepare(self.cli, runtime=False)
        run.assert_not_called()


    def test_official_api_base_notation_is_accepted(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        properties = self.root.joinpath(*package.split(';')) / 'source.properties'
        properties.write_text('AndroidVersion.ApiLevel=37.0\nAndroidVersion.PreviewSdkInt=0\n', encoding='utf-8')
        sdk._verify_package(self.root, package)

    def test_other_api_minor_and_preview_metadata_are_rejected(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        path = self.root.joinpath(*package.split(';')) / 'source.properties'
        invalid = ('AndroidVersion.ApiLevel=37.1\n', 'AndroidVersion.ApiLevel=36.0\n',
                   'AndroidVersion.ApiLevel=37.00\n', 'AndroidVersion.ApiLevel=3.7e1\n',
                   'AndroidVersion.ApiLevel=37.0\nAndroidVersion.PreviewSdkInt=1\n',
                   'AndroidVersion.ApiLevel=37.0\nAndroidVersion.BetaVersion=beta1\n')
        for metadata in invalid:
            path.write_text(metadata, encoding='utf-8')
            with self.subTest(metadata=metadata), self.assertRaises(RuntimeError):
                sdk._verify_package(self.root, package)

    def test_equivalent_parent_alias_is_normalized(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        child = self.root / 'child'
        child.mkdir()
        sdk._verify_package(child / '..', package)



if __name__ == '__main__':
    unittest.main()
