"""Complete the API37 contract migration on the exact staged checkout."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from apply import function


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--templates', type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve(strict=True)
    changes = set(json.loads((root / '.migration-result.json').read_text()))
    def read(name):
        return (root / name).read_text(encoding='utf-8')
    def write(name, text):
        if name.endswith('.py'):
            compile(text, name, 'exec')
        (root / name).write_text(text, encoding='utf-8', newline='\n')
        changes.add(name)
    def edit(name, before, after, count=1):
        text = read(name)
        if text.count(before) != count:
            raise ValueError(f'{name}: expected {count} occurrences of {before!r}, found {text.count(before)}')
        write(name, text.replace(before, after))
    def replace_fn(name, target, replacement, owner=None):
        write(name, function(read(name), target, replacement, owner))

    name = 'backend/tests/test_client_updates.py'
    replace_fn(name, 'evidence', '''
def evidence(self, version=23):
    from backend.tests.android17_fixtures import publication_evidence
    sha = hashlib.sha256(self.apk.read_bytes()).hexdigest()
    return {'sha256': sha, 'bytes': self.apk.stat().st_size, 'certificate_sha256': CERT,
            'signature_v2': True, 'zipalign_16kb': True, 'test_only': False, 'debuggable': False,
            'package': 'ru.omnicio.app.debug', 'version_code': version, 'version_name': 'test-preview',
            'min_sdk': 37, 'target_sdk': 37, **publication_evidence(sha)}
''', 'UpdateTests')
    replace_fn(name, 'test_android15_release_requires_both_real_transcripts', '''
def test_android17_requires_both_exact_runtime_transcripts(self):
    from copy import deepcopy
    valid = self.evidence(24)
    for api in (33, 35, 36):
        report = deepcopy(valid)
        report['min_sdk'] = api
        with self.subTest(api=api), self.assertRaises(updates.ReleaseUnavailable):
            publish(self.root, self.apk, report, expected_certificate=CERT)
    for index in (0, 1):
        report = deepcopy(valid)
        del report['installation_tests'][index]
        with self.subTest(missing=index), self.assertRaises(updates.ReleaseUnavailable):
            publish(self.root, self.apk, report, expected_certificate=CERT)
    release = publish(self.root, self.apk, valid, expected_certificate=CERT)
    self.assertEqual(release.min_sdk, 37)
''', 'UpdateTests')
    edit(name, "['installation_evidence']['36']", "['installation_evidence']['37-4k']", 2)
    edit(name, 'from backend.tests.android17_fixtures import adapt_publication\n', '')
    for filename in ('test_release_recovery.py', 'test_release_rollover.py'):
        edit('backend/tests/' + filename, "report['min_sdk'] = 37", "report['min_sdk'] = 38")
    name = 'backend/tests/test_update_integration.py'
    edit(name, "        return publish(self.root/'releases',apk,evidence,expected_certificate='c'*64)",
         "        from backend.tests.android17_fixtures import adapt_publication\n        evidence = adapt_publication(evidence)\n        return publish(self.root/'releases',apk,evidence,expected_certificate='c'*64)")
    edit('backend/tests/test_client_gate_efficiency.py', "'c' * 64, 33, int(time.time())", "'c' * 64, 37, int(time.time())")
    edit('backend/tests/test_release_json.py', "'b' * 64, 33, int(time.time())", "'b' * 64, 37, int(time.time())")
    edit('backend/tests/test_release_metadata_contract.py', "'min_sdk': 36,", "'min_sdk': 37,")

    name = 'backend/tests/test_release_runtime_publication.py'
    edit(name, 'minimum=35', 'minimum=37')
    edit(name, "'min_sdk': minimum,", "'min_sdk': minimum, 'target_sdk': 37,")
    replace_fn(name, 'test_version34_transcript_remains_publishable_without_runtime_page_measurement', '''
def test_older_app_code_cannot_bypass_android17_runtime_proof(tmp_path):
    apk = tmp_path / 'synthetic.apk'
    apk.write_bytes(b'publication parser fixture, not an APK')
    report = publication_report(apk, 34, runtime_reports())
    report['installation_tests'] = [android15_report()]
    with pytest.raises(ReleaseUnavailable):
        publish(tmp_path / 'releases', apk, report, expected_certificate=CERTIFICATE, now=100)
    assert not (tmp_path / 'releases' / PACKAGE / 'current.json').exists()
''')
    edit(name, 'publication_report(apk, 34, [android15_report(), *reports()])', 'publication_report(apk, 34, runtime_reports())')
    edit(name, 'runtime_reports(), minimum=36', 'runtime_reports(), minimum=37')
    edit(name, "report = publication_report(apk, 35, [android15_report(), *reports()])",
         "report['installation_tests'] = [android15_report(), *reports()]")
    for name in ('.github/scripts/tests/test_android16_live_spectrum.py',
                 '.github/scripts/tests/test_spectrum_brand_identity.py',
                 '.github/scripts/tests/test_persistent_ui.py'):
        text = read(name)
        for before, after in (('compileSdk = 36', 'compileSdk = 37'), ('minSdk = 35', 'minSdk = 37'),
                              ('targetSdk = 36', 'targetSdk = 37'), ('Android 15', 'Android 17'),
                              ('Android16', 'Android17'), ('android_15_plus', 'android_17_plus'),
                              ('android_16', 'android_17')):
            text = text.replace(before, after)
        write(name, text)
    name = '.github/scripts/tests/test_emulator_runtime.py'
    text = read(name)
    for api, size in ((35, 16384), (36, 4096)):
        text = text.replace(f'system_image({api})', f'system_image(37, {size})')
        text = text.replace(f'snapshot_runtime_environment(device, self.sdk, {api})',
                            f'snapshot_runtime_environment(device, self.sdk, 37, page_size_bytes={size})')
    write(name, text)
    name = '.github/scripts/tests/test_installation_report.py'
    edit(name, 'for api, size in ((35, 16384), (36, 4096)):', 'for api, size in ((37, 16384), (37, 4096)):')
    edit(name, 'measured_record(api, str(size), "a" * 64)', 'measured_record(api, str(size), "a" * 64, page_size_bytes=size)')
    edit(name, 'android_api=api)', 'android_api=api, page_size_bytes=size)', 3)
    edit(name, '4096 if api == 35 else 16384', '4096 if size == 16384 else 16384')
    edit(name, 'measured_record(35, "16384", "a" * 64)', 'measured_record(37, "16384", "a" * 64, page_size_bytes=16384)')
    edit(name, 'android_api=35)', 'android_api=37, page_size_bytes=16384)')
    name = '.github/scripts/tests/test_verify_apk.py'
    write(name, read(name).replace("sdkVersion:'35'", "sdkVersion:'37'").replace("targetSdkVersion:'36'", "targetSdkVersion:'37'"))
    name = '.github/scripts/tests/test_distributable_apk_workflow.py'
    replace_fn(name, 'test_both_supported_android_versions_run_full_ui', '''
def test_both_android17_page_sizes_run_full_ui(self):
    for size, key in ((16384, '37-16k'), (4096, '37-4k')):
        self.assertIn(f'--api 37 --page-size {size}', self.action)
        self.assertIn('install-api-' + key, self.action)
    self.assertNotIn('--api 35', self.action)
    self.assertNotIn('--api 36', self.action)
    validator = (ROOT / '.github/scripts/validate_distribution.py').read_text(encoding='utf-8')
    self.assertIn('[checked_installation(target) for target in RUNTIME_TARGETS]', validator)
    self.assertIn('upgrade_required=True', validator)
    self.assertIn('android_api=target.api', validator)
    self.assertIn('page_size_bytes=target.page_size_bytes', validator)
    self.assertIn('if api == 37 and os.getenv', self.installer)
    self.assertIn('device("shell", "getconf", "PAGE_SIZE")', self.installer)
    self.assertLess(self.installer.index('page_size = device'),
                    self.installer.index('install("previous_clean_install", previous)'))
''', 'DistributableApkWorkflowTests')
    name = '.github/scripts/emulator_runtime_control.py'
    edit(name, 'Android 15/16 matrix', 'Android 17 page-size matrix')
    edit(name, 'API = 35', 'API = 37')
    edit(name, 'snapshot_runtime_environment(device, sdk, API)', 'snapshot_runtime_environment(device, sdk, API, page_size_bytes=16384)')
    edit(name, 'image = system_image(API)', 'image = system_image(API, 16384)')
    text = read(name)
    start = text.index('    require_command([sdk / "cmdline-tools/latest/bin/avdmanager"')
    end = text.index('    configure_userdata(', start)
    text = text[:start] + '    from emulator_profile import create_owned_profile\n    create_owned_profile(sdk, work, name, image)\n' + text[end:]
    write(name, text)
    source = args.templates / 'test_emulator_profile.py'
    if source.is_file():
        write('.github/scripts/tests/test_emulator_profile.py', source.read_text(encoding='utf-8'))
    (root / '.migration-result.json').write_text(json.dumps(sorted(changes), indent=2), encoding='utf-8')
    print('ANDROID17_FOLLOWUP_FILES=' + json.dumps(sorted(changes)))


if __name__ == '__main__':
    main()
