"""Synthetic CI records. These tests do NOT perform an Android installation."""
from copy import deepcopy
import unittest
from backend.installation_evidence import InstallationEvidenceError, from_ci_reports

CANDIDATE = 'a' * 64
PREVIOUS = 'b' * 64


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


if __name__ == '__main__':
    unittest.main()
