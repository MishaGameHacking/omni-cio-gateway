"""Bounded test-fixture migration; never run old operating systems or alter real evidence."""
from __future__ import annotations
import subprocess
from migrate_android17 import BRANCH, ROOT, Changes
from migrate_android17_contract import replace_function


def migrate_runtime_tests(changes):
    path = '.github/scripts/tests/test_emulator_runtime.py'
    changes.replace(path, 'system_image(35)', 'system_image(37, 16384)')
    changes.optional(path, 'device, self.sdk, 35)', 'device, self.sdk, 37, page_size_bytes=16384)')
    changes.optional(path, 'device, self.sdk, 36)', 'device, self.sdk, 37, page_size_bytes=4096)')
    path = '.github/scripts/tests/test_installation_report.py'
    changes.replace(path, 'for api, size in ((35, 16384), (36, 4096)):', 'for api, size in ((37, 16384), (37, 4096)):')
    changes.optional(path, 'android_api=api)', 'android_api=api, page_size_bytes=size)')
    changes.replace(path, 'measured_record(api, str(size), "a" * 64)',
                    'measured_record(api, str(size), "a" * 64, page_size_bytes=size)')
    changes.replace(path, '4096 if api == 35 else 16384', '4096 if size == 16384 else 16384')
    changes.replace(path, 'measured_record(35, "16384", "a" * 64)',
                    'measured_record(37, "16384", "a" * 64, page_size_bytes=16384)')
    changes.replace(path, 'android_api=35)', 'android_api=37, page_size_bytes=16384)')


def migrate_source_contract_tests(changes):
    paths = ('.github/scripts/tests/test_android16_live_spectrum.py',
             '.github/scripts/tests/test_spectrum_brand_identity.py',
             '.github/scripts/tests/test_persistent_ui.py',
             '.github/scripts/tests/test_verify_apk.py')
    for path in paths:
        for old, new in (
            ('compileSdk = 36', 'compileSdk = 37'), ('minSdk = 35', 'minSdk = 37'),
            ('targetSdk = 36', 'targetSdk = 37'), ("sdkVersion:'35'", "sdkVersion:'37'"),
            ("targetSdkVersion:'36'", "targetSdkVersion:'37'"),
            ('android_15_plus', 'android_17_plus'), ('android_16_live_ui', 'android_17_live_ui'),
            ('Android16LiveSpectrumTests', 'Android17LiveSpectrumTests'),
        ):
            changes.optional(path, old, new)
    path = '.github/scripts/tests/test_portfolio_semantic_scroll.py'
    changes.replace(path, '        # API35 is now supported by explicit OWNER requirement. The old public\n        # method is restricted to the version-guarded branch; API36 keeps its API.\n',
                    '        # Current OS uses the public tri-state API without an obsolete fallback.\n')
    changes.replace(path, 'self.assertIn("Build.VERSION.SDK_INT >= Build.VERSION_CODES.BAKLAVA", helper)',
                    'self.assertNotIn("Build.VERSION.SDK_INT", helper)')
    changes.replace(path, 'self.assertIn("return node.isChecked();", helper)',
                    'self.assertNotIn("return node.isChecked();", helper)')
    changes.replace(path, 'self.assertEqual(source.count("node.isChecked()"), 1)',
                    'self.assertNotIn("node.isChecked()", source)')
    path = '.github/scripts/tests/test_distributable_apk_workflow.py'
    replace_function(changes, path, 'test_both_supported_android_versions_run_full_ui', '''
        def test_both_current_os_page_size_profiles_run_full_ui(self):
            for size in (4096, 16384):
                self.assertIn(f'--api 37 --page-bytes {size}', self.action)
                self.assertIn(f'install-api37-{size}', self.action)
            contract = (ROOT / 'backend/android_runtime_contract.py').read_text(encoding='utf-8')
            self.assertIn('RuntimeProfile(37, 4096, "google_apis")', contract)
            self.assertIn('RuntimeProfile(37, 16384, "google_apis_ps16k")', contract)
            validator = (ROOT / '.github/scripts/validate_distribution.py').read_text(encoding='utf-8')
            self.assertIn('checked_installation(p.api, p.page_size_bytes)', validator)
            self.assertIn('upgrade_required=True', validator)
            self.assertIn('android_api=profile.api, page_size_bytes=profile.page_size_bytes', validator)
            self.assertIn("'profile_ui_required': True", validator)
            self.assertNotIn('if api in {35, 36}', self.installer)
            self.assertIn('device("shell", "getconf", "PAGE_SIZE")', self.installer)
            self.assertLess(self.installer.index('page_size = device'),
                            self.installer.index('install("previous_clean_install", previous)'))
    ''')


def main():
    branch = subprocess.check_output(['git', 'symbolic-ref', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
    if branch != BRANCH:
        raise ValueError('Dedicated review branch required')
    changes = Changes(ROOT)
    migrate_runtime_tests(changes)
    migrate_source_contract_tests(changes)
    changes.finish()


if __name__ == '__main__':
    main()
