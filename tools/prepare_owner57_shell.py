"""Validate the exact laptop artifact and prepare a bounded private APK transfer."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import re
import zipfile

CERT = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
REQUIRED_PREVIEWS = {
    'Terminal57_terminal57-phone',
    'Terminal57_terminal57-full',
    'Terminal57_terminal57-large-text',
    'TerminalEmpty57_terminal57-empty',
    'TerminalPrivacy57_terminal57-private',
    'LoginAppearance_login-dark',
    'LoginAppearance_login-narrow-large-text',
    'LoginErrorAppearance_login-error-dark',
    'OwnerCooldown56_owner56-cooldown',
    'OwnerCooldown56_owner56-cooldown-large-text',
    'OwnerSetup55_owner55-setup',
    'OwnerSetup55_owner55-setup-large-text',
    'SettingsAppearance_settings-dark',
    'SettingsAppearance_settings-narrow-large-text',
    'SettingsAppearance_settings-tall-content-sheet',
}


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_visual(raw, source, expected_sha):
    need(re.fullmatch('[a-f0-9]{64}', expected_sha) is not None
         and digest(raw) == expected_sha and len(raw) <= 256 * 1024**2,
         "visual_artifact_changed")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)) and len(names) < 2000
             and sum(row.file_size for row in archive.infolist()) <= 512 * 1024**2,
             "visual_artifact_invalid")
        candidates = [name for name in names if name.endswith('/result.json')
                      and 'owner57-visual-' in name]
        need(len(candidates) == 1 and archive.getinfo(candidates[0]).file_size <= 2 * 1024**2,
             "visual_receipt_missing")
        receipt_parent = candidates[0].rsplit('/', 1)[0]
        report = json.loads(archive.read(candidates[0]))
        need(report['source_commit'] == source and report['host'] == 'LAPTOP-NPSGA016'
             and report['status'] == 'rendered-awaiting-visual-review'
             and report['fixture'] == 'synthetic-Layoutlib-no-network'
             and report['baseline_updated'] is False and report['owned_processes_after'] == 0
             and report.get('signing_identity_unchanged') is True
             and report.get('native_acceptance') is False
             and set(report['required_preview_prefixes']) == REQUIRED_PREVIEWS,
             "visual_receipt_changed")
        seen = set()
        for screenshot in report['screenshots']:
            path = screenshot['path'].replace('\\', '/')
            need(path not in seen and not path.startswith('/')
                 and '..' not in path.split('/') and ':' not in path,
                 "visual_screenshot_path_invalid")
            seen.add(path)
            matches = [name for name in names if name == receipt_parent + '/screens/' + path]
            need(len(matches) == 1 and 0 < screenshot['bytes'] <= 8 * 1024**2
                 and archive.getinfo(matches[0]).file_size == screenshot['bytes'],
                 "visual_screenshot_missing")
            need(digest(archive.read(matches[0])) == screenshot['sha256'],
                 "visual_screenshot_changed")
        for prefix in REQUIRED_PREVIEWS:
            need(sum(path.split('/')[-1].startswith(prefix + '_') and path.endswith('.png')
                     for path in seen) == 1, "visual_inventory_incomplete")
    return {'visual_artifact_sha256': expected_sha, 'visual_source_commit': source,
            'native_acceptance': False}


def main():
    root = Path(os.environ["RUNNER_TEMP"])
    visual_sha = os.environ['EXPECTED_VISUAL_ARTIFACT_SHA256']
    need(visual_sha == os.environ['REVIEWED_VISUAL_ARTIFACT_SHA256'], 'visual_review_not_bound')
    visual = verify_visual((root / 'owner57-visual-artifact.zip').read_bytes(),
                           os.environ['EXPECTED_SOURCE_SHA'], visual_sha)
    raw = (root / "shell-artifact.zip").read_bytes()
    need(digest(raw) == os.environ["EXPECTED_CLIENT_ARTIFACT_SHA256"], "client_artifact_changed")
    need(len(raw) <= 256 * 1024**2, "artifact_too_large")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)) and len(names) < 500, "ambiguous_artifact")
        def member(suffix, maximum):
            matches = [name for name in names if name.endswith(suffix)]
            need(len(matches) == 1, "missing_unique_artifact_member")
            info = archive.getinfo(matches[0])
            need(0 < info.file_size <= maximum, "artifact_member_size_invalid")
            return archive.read(info)
        apk = member("/app/build/outputs/apk/preview/app-preview.apk", 100 * 1024**2)
        report_raw = member("/app/build/outputs/apk/preview/apk-verification.json", 1024**2)
        result_raw = member("/result.json", 1024**2)
        steps = json.loads(member("/shell-build-steps.json", 1024**2))["steps"]
    report, result = json.loads(report_raw), json.loads(result_raw)
    need(result["source_commit"] == os.environ["EXPECTED_SOURCE_SHA"]
         and result["host"] == "LAPTOP-NPSGA016" and result["status"] == "passed"
         and result["owned_processes_after"] == 0 and result["apk_published"] is False
         and result["apk"] == report, "laptop_build_identity_changed")
    required = {"source-audit", "workspace-guards", "host-tests", "tools-tests", "node-tests",
                "native-alignment-tests", "mesh-tests", "gradle", "apk-verification"}
    need(required <= {step["label"] for step in steps}
         and all(step["exit_code"] == 0 for step in steps), "laptop_checks_not_passed")
    need(report["version_code"] == 57 and report["version_name"] == "0.21.0-preview"
         and report["package"] == "ru.omnicio.app.debug" and report['min_sdk'] == 37
         and report['target_sdk'] == 37 and report['certificate_sha256'] == CERT
         and report['signature_v2'] is True and report['zipalign_16kb'] is True,
         "unexpected_apk_identity")
    need(digest(apk) == report["sha256"] == os.environ["EXPECTED_APK_SHA256"]
         and len(apk) == report["bytes"], "apk_bytes_changed")
    members = {"app-preview.apk": apk, "apk-verification.json": report_raw, "build-result.json": result_raw}
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100600 << 16
            archive.writestr(info, content)
    payload = package.getvalue()
    (root / "server-shell-payload.zip").write_bytes(payload)
    meta = {"source_commit": os.environ["EXPECTED_SOURCE_SHA"], "test_run_id": os.environ["EXPECTED_TEST_RUN"],
            **visual, 'visual_run_id': os.environ['EXPECTED_VISUAL_RUN'],
            "runtime_source_commit": os.environ["EXPECTED_RUNTIME_SOURCE_SHA"],
            "runtime_test_run_id": os.environ["EXPECTED_RUNTIME_TEST_RUN"],
            "runtime_deploy_run_id": os.environ["EXPECTED_RUNTIME_DEPLOY_RUN"],
            "delivery_run_id": os.environ["GITHUB_RUN_ID"], "payload_sha256": digest(payload),
            "payload_bytes": len(payload), "apk_sha256": report["sha256"], "apk_bytes": report["bytes"],
            "client_artifact_sha256": os.environ["EXPECTED_CLIENT_ARTIFACT_SHA256"],
            "members": {name: {"sha256": digest(content), "bytes": len(content)} for name, content in members.items()}}
    (root / "server-shell-meta.json").write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
    print("SHELL_TRANSFER_PREPARED=" + json.dumps({key: value for key, value in meta.items() if key != "members"}))


if __name__ == "__main__":
    main()



