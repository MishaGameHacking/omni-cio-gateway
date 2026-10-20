"""Combine exact APK evidence with independent Android 17 runtime reports."""
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
if str(CHECKOUT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT))
from backend.android_platform import RUNTIME_TARGETS, RuntimeTarget
from backend.installation_evidence import from_ci_reports


def checked_installation(target: RuntimeTarget) -> dict:
    directory = output_directory()
    folder = fixed_file(directory, target.report_directory)
    results_path = fixed_file(folder, 'install-results.json')
    results = json.loads(results_path.read_text(encoding='utf-8'))
    profile_required = os.getenv('RUN_PROFILE_UI_TESTS') == '1'
    require(profile_required, 'Complete UI testing cannot be disabled for distribution')
    validate_results(results, upgrade_required=True, profile_required=True,
                     android_api=target.api, page_size_bytes=target.page_size_bytes)
    return {'android_api': target.api, 'runtime_case': target.key, 'page_size_bytes': target.page_size_bytes,
            'abi': 'x86_64', 'profile_ui_required': True, 'results': results}


def save_report(report: dict) -> None:
    directory = CHECKOUT / 'app' / 'build' / 'outputs' / 'apk' / 'preview'
    if directory.is_symlink() or not directory.resolve(strict=True).is_relative_to(CHECKOUT):
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
    report = json.loads(fixed_file(directory, 'apk-verification.json').read_text(encoding='utf-8'))
    apk = fixed_file(directory, 'app-preview.apk')
    require(report['sha256'] == hashlib.sha256(apk.read_bytes()).hexdigest(), 'APK changed after static verification')
    require(report['min_sdk'] == 37 and report['target_sdk'] == 37, 'Android 17 build contract required')
    report['installation_tests'] = [checked_installation(target) for target in RUNTIME_TARGETS]
    report['installation_evidence'] = from_ci_reports(report['installation_tests'], report['sha256'])
    report['installation_method'] = 'adb_emulator_not_in_app_self_update'
    report['device_install_test'] = 'passed_on_emulators_not_a_physical_phone'
    save_report(report)
    print('DISTRIBUTION_VALIDATION=' + json.dumps(report, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
