"""Validate complete current-Android runtime evidence, not a successful build.

These are operator-supplied records, not signed device attestation. Historical
reports cannot certify a new target by changing a label or dropping a profile.
"""
from __future__ import annotations

import re

try:
    from .android_runtime_contract import RUNTIME_PROFILES, runtime_profile
except ImportError:
    from android_runtime_contract import RUNTIME_PROFILES, runtime_profile

CURRENT_UI_SUITE = 'spectrum-3d-100-v2'
BUSINESS_CASE_IDS = frozenset(
    f'{route}/{scenario}@{font}'
    for route in ('risk', 'assistant', 'plans', 'strategy', 'notifications', 'analysis', 'catalogue')
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
REQUIRED_TESTS = frozenset({
    'kernel_page_size', 'previous_clean_install', 'upgrade_to_candidate',
    'upgrade_bootstrap_launch', 'candidate_clean_install',
    'bootstrap_activity_launch', 'debug_ui_fixture_install', 'profile_ui',
})


class InstallationEvidenceError(ValueError):
    """Incomplete, ambiguous or wrong-artifact evidence cannot authorize release."""


def _digest(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r'[a-f0-9]{64}', value) is None:
        raise InstallationEvidenceError('invalid_test_artifact_digest')
    return value


def _results(raw: object) -> dict[str, dict]:
    if not isinstance(raw, list) or len(raw) != len(REQUIRED_TESTS):
        raise InstallationEvidenceError('invalid_installation_results')
    indexed = {}
    for result in raw:
        if not isinstance(result, dict) or result.get('success') is not True:
            raise InstallationEvidenceError('failed_or_incomplete_installation_test')
        name = result.get('test')
        if not isinstance(name, str) or name not in REQUIRED_TESTS or name in indexed:
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
    if not isinstance(record, dict) or record.get('ui_suite') != CURRENT_UI_SUITE:
        raise InstallationEvidenceError('current_ui_suite_evidence_required')
    counts = {
        'business_case_count': _case_receipt(record, 'business', BUSINESS_CASE_IDS),
        'portfolio_case_count': _case_receipt(record, 'portfolio', PORTFOLIO_CASE_IDS),
    }
    if _digest(record.get('fixture_apk_sha256')) != _digest(fixture_digest):
        raise InstallationEvidenceError('ui_artifact_mismatch')
    return counts


def _runtime(run: dict):
    if run.get('abi') != 'x86_64' or run.get('profile_ui_required') is not True:
        raise InstallationEvidenceError('unrecognized_emulator_evidence')
    try:
        return runtime_profile(run.get('android_api'), run.get('page_size_bytes'))
    except ValueError as error:
        raise InstallationEvidenceError('unrecognized_runtime_profile') from error


def _kernel_evidence(record: dict, profile, digest: str) -> None:
    expected = {'android_api': profile.api, 'abi': 'x86_64',
                'system_image': profile.image, 'page_size_bytes': profile.page_size_bytes,
                'command': 'getconf PAGE_SIZE'}
    if any(type(record.get(key)) is not type(value) or record.get(key) != value
           for key, value in expected.items()):
        raise InstallationEvidenceError('invalid_kernel_page_size_evidence')
    if _digest(record.get('apk_sha256')) != digest:
        raise InstallationEvidenceError('installation_artifact_mismatch')


def _one_emulator(run: dict, digest: str) -> tuple[str, dict]:
    profile = _runtime(run)
    records = _results(run.get('results'))
    bound = REQUIRED_TESTS - {'previous_clean_install', 'debug_ui_fixture_install', 'profile_ui'}
    for name in bound:
        if _digest(records[name].get('apk_sha256')) != digest:
            raise InstallationEvidenceError('installation_artifact_mismatch')
    if _digest(records['previous_clean_install'].get('apk_sha256')) == digest:
        raise InstallationEvidenceError('upgrade_reinstalled_same_artifact')
    fixture = _digest(records['debug_ui_fixture_install'].get('apk_sha256'))
    counts = validate_ui_receipt(records['profile_ui'], fixture)
    _kernel_evidence(records['kernel_page_size'], profile, digest)
    return profile.key, {
        'clean_install': True, 'upgrade': True, 'upgrade_launch': True, 'launch': True,
        'android_api': profile.api, 'abi': 'x86_64', 'system_image': profile.image,
        'page_size_bytes': profile.page_size_bytes, 'fixture_apk_sha256': fixture, **counts,
    }


def from_ci_reports(installations: object, apk_sha256: str, *, require_runtime_16kb: bool = True) -> dict:
    """Both current-OS page-size profiles are mandatory; no reduced publication path."""
    digest = _digest(apk_sha256)
    if require_runtime_16kb is not True:
        raise InstallationEvidenceError('full_runtime_matrix_required')
    if not isinstance(installations, list) or len(installations) != len(RUNTIME_PROFILES):
        raise InstallationEvidenceError('full_runtime_matrix_required')
    runtimes = {}
    for run in installations:
        if not isinstance(run, dict):
            raise InstallationEvidenceError('invalid_emulator_report')
        key, checked = _one_emulator(run, digest)
        if key in runtimes:
            raise InstallationEvidenceError('duplicate_runtime_profile')
        runtimes[key] = checked
    if set(runtimes) != {profile.key for profile in RUNTIME_PROFILES}:
        raise InstallationEvidenceError('full_runtime_matrix_required')
    if len({checked['fixture_apk_sha256'] for checked in runtimes.values()}) != 1:
        raise InstallationEvidenceError('different_ui_fixture_artifacts')
    return {'schema_version': 2, 'apk_sha256': digest, 'runtimes': runtimes}
