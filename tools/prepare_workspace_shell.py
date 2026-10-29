"""Validate the exact laptop artifact and prepare a bounded private APK transfer."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    root = Path(os.environ["RUNNER_TEMP"])
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
    need(report["version_code"] == 54 and report["version_name"] == "0.18.0-preview"
         and report["package"] == "ru.omnicio.app.debug", "unexpected_apk_identity")
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

