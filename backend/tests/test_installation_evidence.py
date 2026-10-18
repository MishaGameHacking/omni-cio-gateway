"""Synthetic CI records. These tests do NOT perform an Android installation."""
from copy import deepcopy
import unittest
from backend.installation_evidence import BUSINESS_CASE_IDS, PORTFOLIO_CASE_IDS, CURRENT_UI_SUITE, InstallationEvidenceError, from_ci_reports

CANDIDATE = 'a' * 64
PREVIOUS = 'b' * 64
UI_FIXTURE = 'c' * 64


def reports():
    runs = []
    for api in (36,):
        results = [
            {'test': name, 'success': True, 'apk_sha256': CANDIDATE}
            for name in (
                'upgrade_to_candidate',
                'upgrade_bootstrap_launch',
                'candidate_clean_install',
                'activity_launch',
            )
        ]
        results.insert(0, {'test': 'previous_clean_install', 'success': True, 'apk_sha256': PREVIOUS})
        if api == 36:
            results += [
                {'test': 'debug_ui_fixture_install', 'success': True},
                {'test': 'profile_ui', 'success': True},
            ]
        runs.append({
            'android_api': api,
            'abi': 'x86_64',
            'profile_ui_required': api == 36,
            'results': results,
        })
    return runs


def android15_report():
    run = deepcopy(reports()[0])
    run['android_api'] = 35
    run['results'] = [r for r in run['results'] if r['test'] not in {
        'previous_clean_install', 'upgrade_to_candidate', 'upgrade_bootstrap_launch'}]
    return run


def runtime_reports():
    runs = []
    for api, size, tag in ((35, 16384, 'google_apis_ps16k'), (36, 4096, 'google_apis')):
        run = deepcopy(reports()[0])
        run['android_api'] = api
        next(row for row in run['results'] if row['test'] == 'debug_ui_fixture_install')['apk_sha256'] = UI_FIXTURE
        next(row for row in run['results'] if row['test'] == 'profile_ui').update(
            ui_suite=CURRENT_UI_SUITE, business_case_count=len(BUSINESS_CASE_IDS),
            business_cases=sorted(BUSINESS_CASE_IDS),
            portfolio_case_count=len(PORTFOLIO_CASE_IDS), portfolio_cases=sorted(PORTFOLIO_CASE_IDS),
            fixture_apk_sha256=UI_FIXTURE)
        run['results'].append({'test': 'kernel_page_size', 'success': True,
                               'android_api': api, 'abi': 'x86_64',
                               'system_image': f'system-images;android-{api};{tag};x86_64',
                               'page_size_bytes': size, 'command': 'getconf PAGE_SIZE',
                               'apk_sha256': CANDIDATE})
        runs.append(run)
    return runs


class EvidenceTests(unittest.TestCase):
    def reject(self, data):
        with self.assertRaises(InstallationEvidenceError):
            from_ci_reports(data, CANDIDATE)

    def test_android_16_and_exact_artifact(self):
        result = from_ci_reports(reports(), CANDIDATE)
        self.assertEqual(set(result), {'apk_sha256', '36'})
        self.assertEqual(result['36'], {
            'clean_install': True,
            'upgrade': True,
            'upgrade_launch': True,
            'launch': True,
        })

    def test_android15_clean_launch_ui_and_android16_upgrade_are_distinct(self):
        data = [android15_report(), *reports()]
        result = from_ci_reports(data, CANDIDATE)
        self.assertEqual(result['35'], {'clean_install': True, 'launch': True, 'upgrade': False, 'upgrade_launch': False})
        self.assertTrue(result['36']['upgrade'])

    def test_android15_accepts_complete_upgrade_from_the_compatible_baseline(self):
        upgraded = deepcopy(reports()[0])
        upgraded['android_api'] = 35
        result = from_ci_reports([upgraded, *reports()], CANDIDATE)
        self.assertTrue(result['35']['upgrade'])
        self.assertTrue(result['35']['upgrade_launch'])

    def test_android15_partial_upgrade_or_wrong_artifact_is_rejected(self):
        for missing in ('previous_clean_install', 'upgrade_to_candidate', 'upgrade_bootstrap_launch'):
            upgraded = deepcopy(reports()[0])
            upgraded['android_api'] = 35
            upgraded['results'] = [row for row in upgraded['results'] if row['test'] != missing]
            self.reject([upgraded, *reports()])
        for name in ('upgrade_to_candidate', 'upgrade_bootstrap_launch', 'previous_clean_install'):
            upgraded = deepcopy(reports()[0])
            upgraded['android_api'] = 35
            record = next(row for row in upgraded['results'] if row['test'] == name)
            record['apk_sha256'] = CANDIDATE if name == 'previous_clean_install' else PREVIOUS
            self.reject([upgraded, *reports()])

    def test_android15_does_not_replace_upgrade_or_allow_wrong_artifact(self):
        self.reject([android15_report()])
        for name in ('candidate_clean_install', 'activity_launch', 'profile_ui'):
            run = android15_report()
            run['results'] = [r for r in run['results'] if r['test'] != name]
            self.reject([run, *reports()])
        run = android15_report()
        run['results'][0]['apk_sha256'] = PREVIOUS
        self.reject([run, *reports()])

    def test_transcript_is_not_mutated(self):
        data = reports()
        original = deepcopy(data)
        from_ci_reports(data, CANDIDATE)
        self.assertEqual(data, original)

    def test_missing_emulator(self):
        self.reject([])

    def test_duplicate_api_does_not_replace_other_api(self):
        data = reports()
        data[0]['android_api'] = 33
        self.reject(data)

    def test_no_coercion_of_android_api(self):
        for value in ('36', 36.0, True):
            data = reports()
            data[0]['android_api'] = value
            self.reject(data)

    def test_missing_result(self):
        required = (
            'previous_clean_install',
            'upgrade_to_candidate',
            'upgrade_bootstrap_launch',
            'candidate_clean_install',
            'activity_launch',
        )
        for name in required:
            data = reports()
            data[0]['results'] = [r for r in data[0]['results'] if r['test'] != name]
            self.reject(data)

    def test_old_failure_followed_by_success_not_hidden(self):
        data = reports()
        data[0]['results'].insert(0, {'test': 'network_check', 'success': False})
        self.reject(data)

    def test_success_requires_true_boolean(self):
        for value in (1, 'true', None):
            data = reports()
            data[0]['results'][0]['success'] = value
            self.reject(data)

    def test_duplicate_result_is_ambiguous(self):
        data = reports()
        data[0]['results'].append(deepcopy(data[0]['results'][0]))
        self.reject(data)

    def test_wrong_or_missing_artifact_digest(self):
        bound = (
            'upgrade_to_candidate',
            'upgrade_bootstrap_launch',
            'candidate_clean_install',
            'activity_launch',
        )
        for name in bound:
            data = reports()
            next(r for r in data[0]['results'] if r['test'] == name)['apk_sha256'] = PREVIOUS
            self.reject(data)

    def test_unbound_old_format_is_not_new_test_evidence(self):
        data = reports()
        del data[0]['results'][1]['apk_sha256']
        self.reject(data)

    def test_same_file_reinstalled_is_not_upgrade(self):
        data = reports()
        data[0]['results'][0]['apk_sha256'] = CANDIDATE
        self.reject(data)

    def test_bootstrap_launcher_is_supported(self):
        data = reports()
        for run in data:
            next(r for r in run['results'] if r['test'] == 'activity_launch')['test'] = 'bootstrap_activity_launch'
        self.assertIn('36', from_ci_reports(data, CANDIDATE))

    def test_two_clean_launcher_results_rejected(self):
        data = reports()
        data[0]['results'].append({
            'test': 'bootstrap_activity_launch',
            'success': True,
            'apk_sha256': CANDIDATE,
        })
        self.reject(data)

    def test_profile_cannot_be_disabled_for_publication(self):
        data = reports()
        data[0]['profile_ui_required'] = False
        self.reject(data)

    def test_missing_profile_or_debug_fixture(self):
        for label in ('profile_ui', 'debug_ui_fixture_install'):
            data = reports()
            data[0]['results'] = [r for r in data[0]['results'] if r['test'] != label]
            self.reject(data)

    def test_unknown_platform_rejected(self):
        data = reports()
        data[0]['abi'] = 'unknown'
        self.reject(data)

    def test_result_container_and_entries_are_checked(self):
        for values in (None, {}, [], [None], [{'success': True, 'test': []}]):
            data = reports()
            data[0]['results'] = values
            self.reject(data)

    def test_wrong_digest_syntax_rejected(self):
        data = reports()
        with self.assertRaises(InstallationEvidenceError):
            from_ci_reports(data, '../not-a-digest')

    def test_missing_profile_flag_is_not_a_boolean(self):
        data = reports()
        del data[0]['profile_ui_required']
        self.reject(data)

    def test_new_release_requires_real_16kb_and_4kb_full_matrix(self):
        checked = from_ci_reports(runtime_reports(), CANDIDATE, require_runtime_16kb=True)
        self.assertEqual(checked['35']['page_size_bytes'], 16384)
        self.assertTrue(checked['35']['runtime_16kb'])
        self.assertEqual(checked['36']['page_size_bytes'], 4096)
        self.assertFalse(checked['36']['runtime_16kb'])
        self.assertEqual(checked['35']['business_case_count'], 52)
        self.assertEqual(checked['36']['business_case_count'], 52)
        self.assertEqual(checked['35']['portfolio_case_count'], 14)
        self.assertEqual(checked['36']['portfolio_case_count'], 14)
        # Historical transcripts remain usable for recovery, never a new 3D release.
        for old in (reports(), [android15_report(), *reports()]):
            from_ci_reports(old, CANDIDATE)
            with self.assertRaises(InstallationEvidenceError):
                from_ci_reports(old, CANDIDATE, require_runtime_16kb=True)

    def test_new_release_cannot_omit_kernel_upgrade_or_profile_on_either_api(self):
        for index in (0, 1):
            for name in ('kernel_page_size', 'previous_clean_install', 'upgrade_to_candidate',
                         'upgrade_bootstrap_launch', 'candidate_clean_install', 'activity_launch', 'profile_ui'):
                data = runtime_reports()
                data[index]['results'] = [r for r in data[index]['results'] if r['test'] != name]
                with self.subTest(api=index, missing=name), self.assertRaises(InstallationEvidenceError):
                    from_ci_reports(data, CANDIDATE, require_runtime_16kb=True)

    def test_kernel_measurement_is_bound_to_exact_platform_and_candidate(self):
        for field, value in (('android_api', 36), ('android_api', 35.0), ('abi', 'arm64-v8a'),
                             ('system_image', 'system-images;android-35;google_apis;x86_64'),
                             ('page_size_bytes', 4096), ('page_size_bytes', '16384'),
                             ('page_size_bytes', True), ('apk_sha256', PREVIOUS),
                             ('command', 'static-elf-check')):
            data = runtime_reports()
            data[0]['results'][-1][field] = value
            # Even the backwards-compatible parser must not accept false new evidence.
            with self.subTest(field=field, value=value):
                self.reject(data)

    def test_new_release_requires_all_six_routes_and_both_native_font_sizes(self):
        self.assertEqual(len(BUSINESS_CASE_IDS), 52)
        self.assertEqual({f'analysis/{state}@{font}' for state in ('ready', 'partial', 'empty', 'error') for font in (1, 2)},
                         {case for case in BUSINESS_CASE_IDS if case.startswith('analysis/')})
        for field, value in (('ui_suite', 'old-profile-only'), ('business_case_count', 44),
                             ('business_case_count', 52.0), ('business_case_count', True),
                             ('business_cases', sorted(BUSINESS_CASE_IDS)[:-1]), ('business_cases', '52'),
                             ('fixture_apk_sha256', CANDIDATE), ('fixture_apk_sha256', None)):
            data = runtime_reports()
            next(row for row in data[0]['results'] if row['test'] == 'profile_ui')[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InstallationEvidenceError):
                from_ci_reports(data, CANDIDATE, require_runtime_16kb=True)

    def test_duplicate_case_or_missing_receipt_cannot_replace_a_full_run(self):
        for api in (0, 1):
            data = runtime_reports()
            profile = next(row for row in data[api]['results'] if row['test'] == 'profile_ui')
            profile['business_cases'][-1] = profile['business_cases'][0]
            with self.assertRaises(InstallationEvidenceError):
                from_ci_reports(data, CANDIDATE, require_runtime_16kb=True)
            for field in ('ui_suite', 'business_case_count', 'business_cases',
                          'portfolio_case_count', 'portfolio_cases', 'fixture_apk_sha256'):
                data = runtime_reports()
                del next(row for row in data[api]['results'] if row['test'] == 'profile_ui')[field]
                with self.subTest(api=api, missing=field), self.assertRaises(InstallationEvidenceError):
                    from_ci_reports(data, CANDIDATE, require_runtime_16kb=True)

    def test_portfolio_receipt_requires_both_fonts_and_exact_missing_instant_scenario(self):
        self.assertEqual(len(PORTFOLIO_CASE_IDS), 14)
        self.assertEqual({case for case in PORTFOLIO_CASE_IDS if case.startswith('history/')},
                         {'history/ready@1', 'history/ready@2', 'history/partial@1', 'history/partial@2'})
        for field, value in (('portfolio_case_count', 7), ('portfolio_case_count', 14.0),
                             ('portfolio_case_count', True), ('portfolio_cases', sorted(PORTFOLIO_CASE_IDS)[:-1]),
                             ('portfolio_cases', '14'), ('portfolio_cases', sorted(BUSINESS_CASE_IDS)[:14])):
            for index in (0, 1):
                data = runtime_reports()
                next(row for row in data[index]['results'] if row['test'] == 'profile_ui')[field] = value
                with self.subTest(api=index, field=field, value=value), self.assertRaises(InstallationEvidenceError):
                    from_ci_reports(data, CANDIDATE, require_runtime_16kb=True)

    def test_repeated_portfolio_case_or_old_suite_never_substitutes_for_new_production_screens(self):
        for index in (0, 1):
            data = runtime_reports()
            profile = next(row for row in data[index]['results'] if row['test'] == 'profile_ui')
            profile['portfolio_cases'][-1] = profile['portfolio_cases'][0]
            with self.assertRaises(InstallationEvidenceError):
                from_ci_reports(data, CANDIDATE, require_runtime_16kb=True)
            data = runtime_reports()
            next(row for row in data[index]['results'] if row['test'] == 'profile_ui')['ui_suite'] = 'spectrum-3d-100-v1'
            with self.assertRaises(InstallationEvidenceError):
                from_ci_reports(data, CANDIDATE, require_runtime_16kb=True)


if __name__ == '__main__':
    unittest.main()
