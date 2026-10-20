"""Synthetic records for parser tests. These are NOT emulator test results."""
from backend.android_platform import RUNTIME_TARGETS
from backend.installation_evidence import BUSINESS_CASE_IDS, PORTFOLIO_CASE_IDS, CURRENT_UI_SUITE, from_ci_reports


def reports(candidate='a' * 64, previous='b' * 64, fixture='c' * 64):
    runs = []
    for target in RUNTIME_TARGETS:
        results = [{'test': 'previous_clean_install', 'success': True, 'apk_sha256': previous}]
        results.extend({'test': name, 'success': True, 'apk_sha256': candidate} for name in (
            'upgrade_to_candidate', 'upgrade_bootstrap_launch', 'candidate_clean_install', 'activity_launch'))
        results.extend((
            {'test': 'debug_ui_fixture_install', 'success': True, 'apk_sha256': fixture},
            {'test': 'profile_ui', 'success': True, 'fixture_apk_sha256': fixture,
             'ui_suite': CURRENT_UI_SUITE, 'business_case_count': len(BUSINESS_CASE_IDS),
             'business_cases': sorted(BUSINESS_CASE_IDS), 'portfolio_case_count': len(PORTFOLIO_CASE_IDS),
             'portfolio_cases': sorted(PORTFOLIO_CASE_IDS)},
            {'test': 'kernel_page_size', 'success': True, 'android_api': target.api, 'runtime_case': target.key,
             'abi': 'x86_64', 'system_image': target.system_image, 'page_size_bytes': target.page_size_bytes,
             'command': 'getconf PAGE_SIZE', 'apk_sha256': candidate}))
        runs.append({'android_api': target.api, 'runtime_case': target.key,
                     'page_size_bytes': target.page_size_bytes, 'abi': 'x86_64',
                     'profile_ui_required': True, 'results': results})
    return runs


def publication_evidence(candidate):
    data = reports(candidate)
    return {'installation_tests': data, 'installation_evidence': from_ci_reports(data, candidate)}


def adapt_publication(report):
    """Upgrade only a test's positive base fixture; later negative mutations stay intact."""
    return {**report, 'min_sdk': 37, 'target_sdk': 37,
            **publication_evidence(report['sha256'])}
