"""Synthetic current-platform records, never claims of a successful device run."""
from copy import deepcopy
import unittest
from backend.android_runtime_contract import RUNTIME_PROFILES, runtime_profile
from backend.installation_evidence import (
    BUSINESS_CASE_IDS, PORTFOLIO_CASE_IDS, AUTOMATION_CASE_IDS, InstallationEvidenceError, from_ci_reports,
)
from backend.tests.android_runtime_fixtures import CANDIDATE, PREVIOUS, runtime_reports


def reports():
    return runtime_reports()


def record(run, name):
    return next(row for row in run['results'] if row['test'] == name)


class EvidenceTests(unittest.TestCase):
    def reject(self, data):
        with self.assertRaises(InstallationEvidenceError):
            from_ci_reports(data, CANDIDATE)

    def test_current_os_requires_both_distinct_page_size_profiles(self):
        result = from_ci_reports(reports(), CANDIDATE)
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual(result['apk_sha256'], CANDIDATE)
        self.assertEqual(set(result['runtimes']), {'api37-4096', 'api37-16384'})
        for profile in RUNTIME_PROFILES:
            checked = result['runtimes'][profile.key]
            self.assertEqual(checked['android_api'], 37)
            self.assertEqual(checked['page_size_bytes'], profile.page_size_bytes)
            self.assertEqual(checked['system_image'], profile.image)
            for field in ('clean_install', 'upgrade', 'upgrade_launch', 'launch'):
                self.assertIs(checked[field], True)

    def test_case_sets_and_both_font_sizes_are_not_reduced(self):
        self.assertEqual(len(BUSINESS_CASE_IDS), 60)
        self.assertEqual(len(PORTFOLIO_CASE_IDS), 14)
        self.assertEqual(len(AUTOMATION_CASE_IDS), 26)
        for values in (BUSINESS_CASE_IDS, PORTFOLIO_CASE_IDS, AUTOMATION_CASE_IDS):
            self.assertEqual({case.rsplit('@', 1)[1] for case in values}, {'1', '2'})
        checked = from_ci_reports(reports(), CANDIDATE)
        for profile in checked['runtimes'].values():
            self.assertEqual(profile['business_case_count'], 60)
            self.assertEqual(profile['portfolio_case_count'], 14)
            self.assertEqual(profile['automation_case_count'], 26)
            self.assertEqual(profile['ui_stage_count'], 15)

    def test_unsupported_os_is_rejected_even_with_complete_receipts(self):
        for api in (35, 36, 38, '37', 37.0, True, None):
            data = reports()
            data[0]['android_api'] = api
            with self.subTest(api=api):
                self.reject(data)

    def test_page_size_types_are_not_coerced(self):
        for value in (4096.0, '4096', True, None, 0, 8192):
            data = reports()
            data[0]['page_size_bytes'] = value
            with self.subTest(value=value):
                self.reject(data)

    def test_duplicate_profile_never_replaces_missing_runtime(self):
        data = reports()
        self.reject([data[0], deepcopy(data[0])])
        self.reject([data[1], deepcopy(data[1])])

    def test_missing_extra_and_invalid_run_containers(self):
        for data in (None, {}, [], [None, None], reports()[:1], reports() + reports()[:1]):
            self.reject(data)

    def test_full_matrix_cannot_be_opted_out(self):
        data = reports()
        for value in (False, 0, 1, 'true', None):
            with self.subTest(value=value), self.assertRaises(InstallationEvidenceError):
                from_ci_reports(data, CANDIDATE, require_runtime_16kb=value)

    def test_input_is_not_mutated(self):
        data = reports()
        original = deepcopy(data)
        from_ci_reports(data, CANDIDATE)
        self.assertEqual(data, original)

    def test_profile_order_does_not_change_interpretation(self):
        self.assertEqual(from_ci_reports(reports(), CANDIDATE),
                         from_ci_reports(list(reversed(reports())), CANDIDATE))

    def test_missing_any_record_on_either_profile_is_failure(self):
        for index in (0, 1):
            for original in reports()[index]['results']:
                data = reports()
                data[index]['results'] = [r for r in data[index]['results'] if r['test'] != original['test']]
                with self.subTest(index=index, name=original['test']):
                    self.reject(data)

    def test_duplicate_result_and_trailing_failure_are_not_ignored(self):
        for extra in (reports()[0]['results'][0], dict(test='late_failure', success=False)):
            data = reports()
            data[0]['results'].append(deepcopy(extra))
            self.reject(data)

    def test_wrong_result_container_and_invalid_result_name(self):
        for values in (None, {}, [], [None] * 8):
            data = reports()
            data[0]['results'] = values
            self.reject(data)
        for value in (None, [], '', 'unexpected'):
            data = reports()
            data[0]['results'][0]['test'] = value
            self.reject(data)

    def test_each_success_requires_true_boolean(self):
        for index in range(8):
            for value in (False, 1, 'true', None):
                data = reports()
                data[0]['results'][index]['success'] = value
                with self.subTest(index=index, value=value):
                    self.reject(data)

    def test_candidate_artifact_is_bound_in_every_install_launch_and_kernel(self):
        names = ('upgrade_to_candidate', 'upgrade_bootstrap_launch', 'candidate_clean_install',
                 'bootstrap_activity_launch', 'kernel_page_size')
        for index in (0, 1):
            for name in names:
                data = reports()
                record(data[index], name)['apk_sha256'] = PREVIOUS
                with self.subTest(index=index, name=name):
                    self.reject(data)

    def test_previous_artifact_cannot_be_same_or_missing(self):
        for value in (CANDIDATE, None, '', 'not-a-digest'):
            data = reports()
            record(data[0], 'previous_clean_install')['apk_sha256'] = value
            self.reject(data)

    def test_no_legacy_unbound_profile_receipt(self):
        data = reports()
        data[0]['results'] = [dict(test=r['test'], success=True) for r in data[0]['results']]
        self.reject(data)

    def test_actual_page_size_cannot_be_replaced_by_static_alignment(self):
        for field, value in (('page_size_bytes', 16384), ('page_size_bytes', '4096'),
                             ('page_size_bytes', True), ('command', 'ELF alignment'),
                             ('android_api', 36), ('android_api', 37.0), ('abi', 'arm64-v8a'),
                             ('system_image', RUNTIME_PROFILES[1].image)):
            data = reports()
            record(data[0], 'kernel_page_size')[field] = value
            with self.subTest(field=field, value=value):
                self.reject(data)

    def test_all_kernel_fields_are_required(self):
        for field in record(reports()[0], 'kernel_page_size'):
            data = reports()
            del record(data[0], 'kernel_page_size')[field]
            self.reject(data)

    def test_profile_ui_and_platform_identity_are_required(self):
        for field, value in (('abi', 'unknown'), ('profile_ui_required', False),
                             ('profile_ui_required', 1), ('profile_ui_required', None)):
            data = reports()
            data[0][field] = value
            self.reject(data)

    def test_profile_receipt_is_bound_to_installed_debug_fixture(self):
        for value in (None, CANDIDATE, 'd' * 64):
            data = reports()
            record(data[0], 'profile_ui')['fixture_apk_sha256'] = value
            self.reject(data)

    def test_profiles_cannot_test_different_debug_fixtures(self):
        data = reports()
        record(data[1], 'debug_ui_fixture_install')['apk_sha256'] = 'd' * 64
        record(data[1], 'profile_ui')['fixture_apk_sha256'] = 'd' * 64
        self.reject(data)

    def test_current_suite_is_required(self):
        for value in (None, 'spectrum-3d-100-v1', 'analyst-2d-live-v3', '', True):
            data = reports()
            record(data[0], 'profile_ui')['ui_suite'] = value
            self.reject(data)

    def test_each_case_count_is_exact_integer(self):
        for group, count in (('business', 60), ('portfolio', 14), ('automation', 26)):
            for value in (count - 1, float(count), True, str(count), None):
                data = reports()
                record(data[0], 'profile_ui')[group + '_case_count'] = value
                self.reject(data)

    def test_case_arrays_cannot_drop_duplicate_or_substitute(self):
        for group in ('business', 'portfolio', 'automation'):
            for mode in ('missing', 'duplicate', 'unhashable', 'substitute', 'wrong_type'):
                data = reports()
                target = record(data[0], 'profile_ui')
                cases = target[group + '_cases']
                if mode == 'missing':
                    cases.pop()
                elif mode == 'duplicate':
                    cases[-1] = cases[0]
                elif mode == 'unhashable':
                    cases[-1] = []
                elif mode == 'substitute':
                    cases[-1] = 'invented/ready@1'
                else:
                    target[group + '_cases'] = 'not-a-list'
                self.reject(data)

    def test_missing_any_ui_receipt_field_is_failure(self):
        for field in ('ui_suite', 'business_case_count', 'business_cases',
                      'portfolio_case_count', 'portfolio_cases', 'fixture_apk_sha256', 'ui_stages',
                      'automation_case_count', 'automation_cases', 'automation_report', 'automation_artifact_directory'):
            data = reports()
            del record(data[0], 'profile_ui')[field]
            self.reject(data)

    def test_two_launcher_results_are_ambiguous(self):
        data = reports()
        data[0]['results'].append(dict(test='activity_launch', success=True, apk_sha256=CANDIDATE))
        self.reject(data)

    def test_digest_syntax_is_validated_before_reports(self):
        data = reports()
        for digest in (None, '', '../not-a-digest', 'A' * 64):
            with self.subTest(digest=digest), self.assertRaises(InstallationEvidenceError):
                from_ci_reports(data, digest)

    def test_profile_selector_does_not_accept_boolean_or_future_api(self):
        for api, page in ((True, 4096), (37.0, 4096), (37, True), (38, 4096), (36, 16384)):
            with self.subTest(api=api, page=page), self.assertRaises(ValueError):
                runtime_profile(api, page)

    def test_v3_is_only_valid_for_an_explicit_historical_version(self):
        legacy = runtime_reports(legacy=True)
        checked = from_ci_reports(legacy, CANDIDATE, version_code=37)
        self.assertNotIn("automation_case_count", checked["runtimes"]["api37-4096"])
        for version in (None, 38, 39, True, "37", 37.0, 0, -1, 2_100_000_001):
            with self.subTest(version=version), self.assertRaises(InstallationEvidenceError):
                from_ci_reports(legacy, CANDIDATE, version_code=version)

    def test_v4_can_certify_a_historical_artifact_without_inventing_legacy_proof(self):
        self.assertEqual(from_ci_reports(reports(), CANDIDATE, version_code=37),
                         from_ci_reports(reports(), CANDIDATE, version_code=38))

    def test_stage_matrix_and_attempt_archive_are_required(self):
        for field, value in (("ui_stages", []), ("ui_stages", ["settings-group-scroll"] * 15),
                             ("automation_artifact_directory", "../automation-ui"),
                             ("automation_artifact_directory", "attempt-3/automation-ui"),
                             ("automation_artifact_directory", None)):
            data = reports()
            record(data[0], "profile_ui")[field] = value
            self.reject(data)

    def test_complete_counts_do_not_replace_native_automation_observations(self):
        for field in ("automation_report",):
            for value in (None, {}, {"cases": []}):
                data = reports()
                record(data[0], "profile_ui")[field] = value
                self.reject(data)

    def test_automation_fixture_identity_and_image_digest_are_bound(self):
        changes = (("fixture_apk_sha256", "f" * 64), ("schema_version", True),
                   ("actual_device_observations", False), ("external_broker_model_calls", True),
                   ("real_order_execution", True))
        for field, value in changes:
            data = reports()
            record(data[0], "profile_ui")["automation_report"][field] = value
            self.reject(data)
        for value in (None, "invalid", "A" * 64):
            data = reports()
            record(data[0], "profile_ui")["automation_report"]["cases"][0]["screenshot_sha256"] = value
            self.reject(data)

    def test_automation_rows_cannot_drop_duplicate_or_relabel_cases(self):
        for mode in ("missing", "duplicate", "unhashable", "font", "name"):
            data = reports()
            rows = record(data[0], "profile_ui")["automation_report"]["cases"]
            if mode == "missing":
                rows.pop()
            elif mode == "duplicate":
                rows[-1] = deepcopy(rows[0])
            elif mode == "unhashable":
                rows[0] = []
            elif mode == "font":
                rows[0]["font_scale"] = True
            else:
                rows[0]["case"] = "home/conflict"
            self.reject(data)

    def test_automation_observation_failures_are_not_valid_receipts(self):
        mutations = [
            lambda row: row["after"].update(writes=2),
            lambda row: row["after"].update(**{"contract-errors": 1}),
            lambda row: row["renderer"].update(**{"draw-operations": 0}),
            lambda row: row["renderer"].update(**{"font-scale": 3.0}),
            lambda row: row["renderer"].update(orientation="2"),
            lambda row: row["renderer"].update(engines=1),
            lambda row: row.update(process_id_after="9999"),
            lambda row: row.update(width=800, height=480),
            lambda row: row.update(screenshot="../capture.png"),
            lambda row: row["foreground_after"].update(after=[]),
            lambda row: row["foreground_after"].update(after=["topResumedActivity=ActivityRecord{a u0 another.app/.Main t1}"]),
        ]
        for mutate in mutations:
            data = reports()
            mutate(record(data[0], "profile_ui")["automation_report"]["cases"][0])
            self.reject(data)

    def test_rejected_and_applied_settings_require_actual_switch_and_trace(self):
        for scenario in ("conflict", "ready", "paused", "not_connected", "error"):
            for field in ("checked", "enabled", "checkable"):
                data = reports()
                rows = record(data[0], "profile_ui")["automation_report"]["cases"]
                row = next(item for item in rows if item["case"] == "settings/" + scenario)
                row["native_switch"][field] = not row["native_switch"][field]
                self.reject(data)


if __name__ == '__main__':
    unittest.main()
