"""Synthetic receipts only: never an APK installation or device attestation."""
from copy import deepcopy
from backend.android_runtime_contract import RUNTIME_PROFILES
from backend.installation_evidence import (
    BUSINESS_CASE_IDS, PORTFOLIO_CASE_IDS, CURRENT_UI_SUITE, from_ci_reports,
)

CANDIDATE = 'a' * 64
PREVIOUS = 'b' * 64
UI_FIXTURE = 'c' * 64


def runtime_reports(digest: str = CANDIDATE) -> list[dict]:
    runs = []
    for profile in RUNTIME_PROFILES:
        results = [dict(test=name, success=True, apk_sha256=digest) for name in (
            'upgrade_to_candidate', 'upgrade_bootstrap_launch',
            'candidate_clean_install', 'bootstrap_activity_launch',
        )]
        results.insert(0, dict(test='previous_clean_install', success=True, apk_sha256=PREVIOUS))
        results.append(dict(test='debug_ui_fixture_install', success=True, apk_sha256=UI_FIXTURE))
        results.append(dict(test='profile_ui', success=True, fixture_apk_sha256=UI_FIXTURE,
                            ui_suite=CURRENT_UI_SUITE, business_case_count=len(BUSINESS_CASE_IDS),
                            business_cases=sorted(BUSINESS_CASE_IDS),
                            portfolio_case_count=len(PORTFOLIO_CASE_IDS),
                            portfolio_cases=sorted(PORTFOLIO_CASE_IDS)))
        results.append(dict(test='kernel_page_size', success=True, android_api=profile.api,
                            abi='x86_64', system_image=profile.image,
                            page_size_bytes=profile.page_size_bytes,
                            command='getconf PAGE_SIZE', apk_sha256=digest))
        runs.append(dict(android_api=profile.api, page_size_bytes=profile.page_size_bytes,
                         abi='x86_64', profile_ui_required=True, results=results))
    return runs


def publication_report(report: dict) -> dict:
    result = deepcopy(report)
    result['min_sdk'] = 37
    result['target_sdk'] = 37
    result['installation_tests'] = runtime_reports(result['sha256'])
    result['installation_evidence'] = from_ci_reports(result['installation_tests'], result['sha256'])
    return result
