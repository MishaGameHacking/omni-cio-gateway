"""Combine fixed-path APK and measured current-runtime reports; never execute devices."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from installation_report import validate_results
from verify_apk import fixed_file, output_directory, require

CHECKOUT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CHECKOUT))
from backend.android_runtime_contract import RUNTIME_PROFILES, runtime_profile, CURRENT_UI_SUITE
from backend.installation_evidence import from_ci_reports
from automation_artifacts import verify_automation_artifacts


def checked_installation(api: int, page_size_bytes: int = 4096, *, version_code: int | None = None) -> dict:
    profile = runtime_profile(api, page_size_bytes)
    directory = output_directory()
    folder = fixed_file(directory, profile.directory)
    results_path = fixed_file(folder, 'install-results.json')
    results = json.loads(results_path.read_text(encoding='utf-8'))
    require(os.getenv('RUN_PROFILE_UI_TESTS') == '1', 'Full UI verification is mandatory')
    validate_results(results, upgrade_required=True, profile_required=True,
                     android_api=profile.api, page_size_bytes=profile.page_size_bytes,
                     candidate_version_code=version_code)
    ui = next(row for row in results if row['test'] == 'profile_ui')
    if ui['ui_suite'] == CURRENT_UI_SUITE:
        relative = ui['automation_artifact_directory']
        archive = folder / relative
        if archive.is_symlink() or not archive.resolve(strict=True).is_relative_to(folder.resolve(strict=True)):
            raise ValueError('Automation artifact archive escapes the runtime directory')
        verify_automation_artifacts(ui['automation_report'], archive)
    return {'android_api': profile.api, 'page_size_bytes': profile.page_size_bytes,
            'abi': 'x86_64', 'profile_ui_required': True, 'results': results}


def save_report(report: dict) -> None:
    root = CHECKOUT
    directory = root / 'app' / 'build' / 'outputs' / 'apk' / 'preview'
    if directory.is_symlink() or not directory.resolve(strict=True).is_relative_to(root):
        raise ValueError('Report directory escapes the checkout')
    destination = directory / 'apk-verification.json'
    if destination.is_symlink():
        raise ValueError('Report destination must not be a symlink')
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                     prefix='validated-', suffix='.json', delete=False) as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
        temporary = handle.name
    try:
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    directory = output_directory()
    report_path = fixed_file(directory, 'apk-verification.json')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    apk = fixed_file(directory, 'app-preview.apk')
    require(report['sha256'] == hashlib.sha256(apk.read_bytes()).hexdigest(),
            'APK changed after static verification')
    require(type(report.get('min_sdk')) is int and report['min_sdk'] == 37,
            'Only the current Android minimum can be certified')
    require(type(report.get('target_sdk')) is int and report['target_sdk'] == 37,
            'The current Android target is required')
    version = report.get('version_code')
    require(type(version) is int and 1 <= version <= 2_100_000_000, 'Candidate version is not verified')
    report['installation_tests'] = [checked_installation(p.api, p.page_size_bytes, version_code=version)
                                    for p in RUNTIME_PROFILES]
    report['installation_evidence'] = from_ci_reports(report['installation_tests'], report['sha256'], version_code=version)
    report['installation_method'] = 'adb_emulator_not_in_app_self_update'
    report['device_install_test'] = 'passed_on_emulators_not_a_physical_phone'
    save_report(report)
    print('DISTRIBUTION_VALIDATION=' + json.dumps(report, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
