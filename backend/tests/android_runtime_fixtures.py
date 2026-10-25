"""Synthetic receipts only: never an APK installation or device attestation."""
from copy import deepcopy
from backend.android_runtime_contract import (
    RUNTIME_PROFILES, AUTOMATION_CASE_IDS, UI_STAGE_IDS, LEGACY_UI_SUITE,
)
from backend.installation_evidence import (
    BUSINESS_CASE_IDS, PORTFOLIO_CASE_IDS, CURRENT_UI_SUITE, from_ci_reports,
)
from backend.automation_ui_evidence import screenshot_name

CANDIDATE = 'a' * 64
PREVIOUS = 'b' * 64
UI_FIXTURE = 'c' * 64


def automation_report(fixture_digest: str = UI_FIXTURE) -> dict:
    rows = []
    foreground = ["topResumedActivity=ActivityRecord{abc u0 "
                  "ru.omnicio.app.debug/ru.omnicio.app.ProfileUiProbeActivity t1}"]
    for identity in sorted(AUTOMATION_CASE_IDS):
        case, font = identity.rsplit("@", 1)
        route, scenario = case.split("/", 1)
        enabled = scenario != "paused"
        mutation = route == "settings" and scenario != "error"
        applied = mutation and scenario != "conflict"
        before = dict(requests=1, writes=0, applied=0, rejected=0, version=1,
                      enabled=enabled, page=route, **{"contract-errors": 0})
        after = dict(before, requests=4 if route == "home" and scenario == "ready" else 3 if mutation else 1,
                     writes=int(mutation), applied=int(applied), rejected=int(scenario == "conflict"),
                     version=1 + int(mutation), enabled=not enabled if applied else enabled)
        renderer = {"renderer": "native-2d", "error": "none", "draw-operations": 1,
                    "engines": 0, "windows": 0, "frames": 0, "meshes": 0, "pending": 0, "pool": 0,
                    "font-scale": float(font), "density": 2.75, "orientation": "1"}
        rows.append(dict(case=case, font_scale=float(font), before=before, after=after, renderer=renderer,
                         process_id="1234", process_id_after="1234", width=480, height=800,
                         screenshot=screenshot_name(identity), screenshot_sha256="d" * 64,
                         foreground_before=dict(before=foreground[:], after=foreground[:]),
                         foreground_after=dict(before=foreground[:], after=foreground[:]),
                         native_switch=None if route != "settings" else dict(
                             checkable=True, checked=scenario in ("paused", "conflict"), enabled=scenario != "error")))
    return dict(schema_version=1, fixture="debug-only-synthetic-transport", actual_device_observations=True,
                external_broker_model_calls=False, real_order_execution=False,
                fixture_apk_sha256=fixture_digest, cases=rows)


def ui_receipt(fixture_digest: str = UI_FIXTURE, *, legacy: bool = False) -> dict:
    receipt = dict(fixture_apk_sha256=fixture_digest,
                   ui_suite=LEGACY_UI_SUITE if legacy else CURRENT_UI_SUITE,
                   business_case_count=len(BUSINESS_CASE_IDS), business_cases=sorted(BUSINESS_CASE_IDS),
                   portfolio_case_count=len(PORTFOLIO_CASE_IDS), portfolio_cases=sorted(PORTFOLIO_CASE_IDS))
    if not legacy:
        receipt.update(ui_stages=list(UI_STAGE_IDS), automation_case_count=len(AUTOMATION_CASE_IDS),
                       automation_cases=sorted(AUTOMATION_CASE_IDS), automation_report=automation_report(fixture_digest),
                       automation_artifact_directory="attempt-1/automation-ui")
    return receipt


def runtime_reports(digest: str = CANDIDATE, *, legacy: bool = False) -> list[dict]:
    runs = []
    for profile in RUNTIME_PROFILES:
        results = [dict(test=name, success=True, apk_sha256=digest) for name in (
            'upgrade_to_candidate', 'upgrade_bootstrap_launch',
            'candidate_clean_install', 'bootstrap_activity_launch',
        )]
        results.insert(0, dict(test='previous_clean_install', success=True, apk_sha256=PREVIOUS))
        results.append(dict(test='debug_ui_fixture_install', success=True, apk_sha256=UI_FIXTURE))
        results.append(dict(test='profile_ui', success=True, **ui_receipt(legacy=legacy)))
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
    result['installation_evidence'] = from_ci_reports(
        result['installation_tests'], result['sha256'], version_code=result.get('version_code'))
    return result
