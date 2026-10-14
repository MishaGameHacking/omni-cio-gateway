"""Synthetic CI records. These tests do NOT perform an Android installation."""
from copy import deepcopy
import unittest
from backend.installation_evidence import InstallationEvidenceError, from_ci_reports

CANDIDATE = 'a' * 64
PREVIOUS = 'b' * 64


def reports():
    runs = []
    for api in (33, 36):
        results = [{'test': name, 'success': True, 'apk_sha256': CANDIDATE}
                   for name in ('upgrade_to_candidate', 'candidate_clean_install', 'activity_launch')]
        results.insert(0, {'test': 'previous_clean_install', 'success': True, 'apk_sha256': PREVIOUS})
        if api == 33:
            results += [{'test': 'debug_ui_fixture_install', 'success': True}, {'test': 'profile_ui', 'success': True}]
        runs.append({'android_api': api, 'abi': 'x86_64', 'profile_ui_required': api == 33, 'results': results})
    return runs


class EvidenceTests(unittest.TestCase):
    def reject(self, data):
        with self.assertRaises(InstallationEvidenceError):
            from_ci_reports(data, CANDIDATE)

    def test_both_emulators_and_exact_artifact(self):
        result = from_ci_reports(reports(), CANDIDATE)
        self.assertEqual(set(result), {'apk_sha256', '33', '36'})
        self.assertEqual(result['33'], {'clean_install': True, 'upgrade': True, 'launch': True})

    def test_transcript_is_not_mutated(self):
        data = reports()
        original = deepcopy(data)
        from_ci_reports(data, CANDIDATE)
        self.assertEqual(data, original)

    def test_missing_emulator(self):
        self.reject(reports()[:1])

    def test_duplicate_api_does_not_replace_other_api(self):
        data = reports()
        data[1]['android_api'] = 33
        self.reject(data)

    def test_no_coercion_of_android_api(self):
        for value in ('36', 36.0, True):
            data = reports()
            data[1]['android_api'] = value
            self.reject(data)

    def test_missing_result(self):
        for name in ('previous_clean_install', 'upgrade_to_candidate', 'candidate_clean_install', 'activity_launch'):
            data = reports()
            data[1]['results'] = [r for r in data[1]['results'] if r['test'] != name]
            self.reject(data)

    def test_old_failure_followed_by_success_not_hidden(self):
        data = reports()
        data[1]['results'].insert(0, {'test': 'network_check', 'success': False})
        self.reject(data)

    def test_success_requires_true_boolean(self):
        for value in (1, 'true', None):
            data = reports()
            data[1]['results'][0]['success'] = value
            self.reject(data)

    def test_duplicate_result_is_ambiguous(self):
        data = reports()
        data[1]['results'].append(deepcopy(data[1]['results'][0]))
        self.reject(data)

    def test_wrong_or_missing_artifact_digest(self):
        for name in ('upgrade_to_candidate', 'candidate_clean_install', 'activity_launch'):
            data = reports()
            next(r for r in data[1]['results'] if r['test'] == name)['apk_sha256'] = PREVIOUS
            self.reject(data)

    def test_unbound_old_format_is_not_new_test_evidence(self):
        data = reports()
        del data[1]['results'][1]['apk_sha256']
        self.reject(data)

    def test_same_file_reinstalled_is_not_upgrade(self):
        data = reports()
        data[1]['results'][0]['apk_sha256'] = CANDIDATE
        self.reject(data)

    def test_bootstrap_launcher_is_supported(self):
        data = reports()
        for run in data:
            next(r for r in run['results'] if r['test'] == 'activity_launch')['test'] = 'bootstrap_activity_launch'
        self.assertIn('36', from_ci_reports(data, CANDIDATE))

    def test_two_launcher_results_rejected(self):
        data = reports()
        data[1]['results'].append({'test': 'bootstrap_activity_launch', 'success': True, 'apk_sha256': CANDIDATE})
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
        data[1]['abi'] = 'unknown'
        self.reject(data)

    def test_result_container_and_entries_are_checked(self):
        for values in (None, {}, [], [None], [{'success': True, 'test': []}]):
            data = reports()
            data[1]['results'] = values
            self.reject(data)

    def test_wrong_digest_syntax_rejected(self):
        data = reports()
        with self.assertRaises(InstallationEvidenceError):
            from_ci_reports(data, '../not-a-digest')

    def test_missing_profile_flag_is_not_a_boolean(self):
        data = reports()
        del data[1]['profile_ui_required']
        self.reject(data)


if __name__ == '__main__':
    unittest.main()
