"""Validate the actual Android 15/16 CI transcript; never infer installation from a build.

This is an operator-supplied test record, NOT signed device attestation. These
records prove only the recorded adb/emulator checks, not in-app self-update.
"""
from __future__ import annotations

import re


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


def _one_emulator(run: dict, digest: str) -> dict:
    if run.get('abi') != 'x86_64' or type(run.get('profile_ui_required')) is not bool:
        raise InstallationEvidenceError('unrecognized_emulator_evidence')
    records = _results(run.get('results'))
    api = run['android_api']
    required = {'candidate_clean_install'}
    upgrade = {'previous_clean_install', 'upgrade_to_candidate', 'upgrade_bootstrap_launch'}
    if api == 36:
        required |= upgrade
    elif records.keys() & upgrade:
        # The 0.9 baseline requires API36; API35 starts with a clean install.
        raise InstallationEvidenceError('unexpected_android_15_upgrade_evidence')
    launches = {'activity_launch', 'bootstrap_activity_launch'} & records.keys()
    if not required <= records.keys() or len(launches) != 1:
        raise InstallationEvidenceError('installation_evidence_incomplete')
    bound = required - {'previous_clean_install'} | launches
    for name in bound:
        if _digest(records[name].get('apk_sha256')) != digest:
            raise InstallationEvidenceError('installation_artifact_mismatch')
    if api == 36 and _digest(records['previous_clean_install'].get('apk_sha256')) == digest:
        raise InstallationEvidenceError('upgrade_reinstalled_same_artifact')
    if not run['profile_ui_required'] or not {'debug_ui_fixture_install', 'profile_ui'} <= records.keys():
        raise InstallationEvidenceError('profile_ui_evidence_missing')
    return {
        'clean_install': True,
        'upgrade': api == 36,
        'upgrade_launch': api == 36,
        'launch': True,
    }


def from_ci_reports(installations: object, apk_sha256: str) -> dict:
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
    return result