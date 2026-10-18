"""Validate the actual Android 15/16 CI transcript; never infer installation from a build.

This is an operator-supplied test record, NOT signed device attestation. These
records prove only the recorded adb/emulator checks, not in-app self-update.
"""
from __future__ import annotations

import re

CURRENT_UI_SUITE = 'spectrum-3d-100-v2'
BUSINESS_CASE_IDS = frozenset(
    f'{route}/{scenario}@{font}'
    for route in ('risk', 'assistant', 'plans', 'strategy', 'notifications', 'analysis')
    for scenario in ('ready', 'empty', 'partial', 'error', 'job')
    if scenario != 'job' or route in ('assistant', 'plans')
    for font in (1, 2)
)
PORTFOLIO_CASE_IDS = frozenset(
    f'{route}/{scenario}@{font}'
    for route, scenario in (
        ('discovery', 'ready'), ('dossier', 'ready'),
        ('history', 'ready'), ('history', 'partial'),
        ('quotes', 'ready'), ('markets', 'ready'), ('appearance', 'ready'),
    )
    for font in (1, 2)
)


class InstallationEvidenceError(ValueError):
    """An incomplete, ambiguous or wrong-artifact transcript cannot publish."""


def _digest(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r'[a-f0-9]{64}', value) is None:
        raise InstallationEvidenceError('invalid_test_artifact_digest')
    return value


def _results(raw: object) -> dict[str, dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 32:
        raise InstallationEvidenceError('invalid_installation_results')
    indexed = {}
    for result in raw:
        if not isinstance(result, dict) or result.get('success') is not True:
            raise InstallationEvidenceError('failed_or_incomplete_installation_test')
        name = result.get('test')
        if not isinstance(name, str) or not name or name in indexed:
            raise InstallationEvidenceError('ambiguous_installation_test')
        indexed[name] = result
    return indexed


def _case_receipt(record: dict, group: str, expected: frozenset[str]) -> int:
    cases = record.get(group + '_cases')
    count = record.get(group + '_case_count')
    if type(count) is not int or count != len(expected) \
            or not isinstance(cases, list) or len(cases) != len(expected) \
            or not all(isinstance(case, str) for case in cases) or set(cases) != expected:
        raise InstallationEvidenceError(group + '_ui_matrix_incomplete')
    return len(cases)


def validate_ui_receipt(record: object, fixture_digest: str) -> dict[str, int]:
    """Require both completed case/font matrices bound to the installed debug APK."""
    if not isinstance(record, dict) or record.get('ui_suite') != CURRENT_UI_SUITE:
        raise InstallationEvidenceError('current_ui_suite_evidence_required')
    counts = {
        'business_case_count': _case_receipt(record, 'business', BUSINESS_CASE_IDS),
        'portfolio_case_count': _case_receipt(record, 'portfolio', PORTFOLIO_CASE_IDS),
    }
    if _digest(record.get('fixture_apk_sha256')) != _digest(fixture_digest):
        raise InstallationEvidenceError('ui_artifact_mismatch')
    return counts


def _one_emulator(run: dict, digest: str) -> dict:
    if run.get('abi') != 'x86_64' or type(run.get('profile_ui_required')) is not bool:
        raise InstallationEvidenceError('unrecognized_emulator_evidence')
    records = _results(run.get('results'))
    api = run['android_api']
    required = {'candidate_clean_install'}
    upgrade = {'previous_clean_install', 'upgrade_to_candidate', 'upgrade_bootstrap_launch'}
    performed_upgrade = api == 36 or bool(records.keys() & upgrade)
    if performed_upgrade:
        required |= upgrade
    # Historical 0.10 evidence used clean-only API35 because 0.9 required API36.
    # New CI requires the complete upgrade group on both supported APIs. Preserve
    # historical recovery while never promoting a partial group to success.
    launches = {'activity_launch', 'bootstrap_activity_launch'} & records.keys()
    if not required <= records.keys() or len(launches) != 1:
        raise InstallationEvidenceError('installation_evidence_incomplete')
    bound = required - {'previous_clean_install'} | launches
    for name in bound:
        if _digest(records[name].get('apk_sha256')) != digest:
            raise InstallationEvidenceError('installation_artifact_mismatch')
    if performed_upgrade and _digest(records['previous_clean_install'].get('apk_sha256')) == digest:
        raise InstallationEvidenceError('upgrade_reinstalled_same_artifact')
    if not run['profile_ui_required'] or not {'debug_ui_fixture_install', 'profile_ui'} <= records.keys():
        raise InstallationEvidenceError('profile_ui_evidence_missing')
    checked = {
        'clean_install': True,
        'upgrade': performed_upgrade,
        'upgrade_launch': performed_upgrade,
        'launch': True,
    }
    profile = records['profile_ui']
    if 'ui_suite' in profile:
        checked.update(validate_ui_receipt(
            profile, records['debug_ui_fixture_install'].get('apk_sha256')))
    if 'kernel_page_size' in records:
        checked.update(_kernel_evidence(records['kernel_page_size'], api, digest))
    return checked


def from_ci_reports(installations: object, apk_sha256: str, *, require_runtime_16kb: bool = False) -> dict:
    """Reduce checked transcripts; preserve old API36 releases for verified recovery."""
    digest = _digest(apk_sha256)
    if not isinstance(installations, list) or len(installations) not in (1, 2):
        raise InstallationEvidenceError('android_16_evidence_required')
    result = {'apk_sha256': digest}
    for run in installations:
        if not isinstance(run, dict):
            raise InstallationEvidenceError('invalid_emulator_report')
        api = run.get('android_api')
        if type(api) is not int or api not in (35, 36) or str(api) in result:
            raise InstallationEvidenceError('ambiguous_android_version')
        result[str(api)] = _one_emulator(run, digest)
    if "36" not in result:
        raise InstallationEvidenceError("android_16_evidence_required")
    if require_runtime_16kb:
        _require_runtime_matrix(result)
    return result


def _kernel_evidence(kernel, api, digest):
    image = f"system-images;android-{api};{'google_apis_ps16k' if api == 35 else 'google_apis'};x86_64"
    expected_bytes = 16_384 if api == 35 else 4_096
    if type(kernel.get('android_api')) is not int or kernel['android_api'] != api \
            or kernel.get('abi') != 'x86_64' or kernel.get('system_image') != image \
            or type(kernel.get('page_size_bytes')) is not int or kernel['page_size_bytes'] != expected_bytes \
            or kernel.get('command') != 'getconf PAGE_SIZE':
        raise InstallationEvidenceError('invalid_kernel_page_size_evidence')
    if _digest(kernel.get('apk_sha256')) != digest:
        raise InstallationEvidenceError('installation_artifact_mismatch')
    return dict(page_size_bytes=expected_bytes, system_image=image,
                runtime_16kb=expected_bytes == 16_384)


def _require_runtime_matrix(result):
    for api, size in (('35', 16_384), ('36', 4_096)):
        checked = result.get(api, {})
        if checked.get('page_size_bytes') != size or checked.get('upgrade') is not True \
                or checked.get('upgrade_launch') is not True \
                or checked.get('business_case_count') != len(BUSINESS_CASE_IDS) \
                or checked.get('portfolio_case_count') != len(PORTFOLIO_CASE_IDS):
            raise InstallationEvidenceError('android_runtime_page_size_evidence_required')
