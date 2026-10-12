"""Combine fixed-path APK and emulator reports. This parser never executes commands."""
from __future__ import annotations

import hashlib
import json

from verify_apk import fixed_file, output_directory, require


def checked_installation(api: int) -> dict:
    directory = output_directory()
    folder = fixed_file(directory, f"install-api-{api}")
    results_path = fixed_file(folder, "install-results.json")
    results = json.loads(results_path.read_text(encoding="utf-8"))
    require(isinstance(results, list), "Invalid installation report")
    require(all(isinstance(item, dict) and item.get("success") is True for item in results),
            "Failed installation test in report")
    actual = {item.get("test") for item in results}
    required = {"candidate_clean_install", "activity_launch"}
    upgrade = {"previous_clean_install", "upgrade_to_candidate"}
    require(actual in [required, required | upgrade], "Missing or unknown installation tests")
    require(len(results) == len(actual), "Duplicate installation tests")
    return {"android_api": api, "abi": "x86_64", "results": results}


def main() -> None:
    directory = output_directory()
    report_path = fixed_file(directory, "apk-verification.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    apk = fixed_file(directory, "app-preview.apk")
    require(report["sha256"] == hashlib.sha256(apk.read_bytes()).hexdigest(),
            "APK changed after static verification")
    report["installation_tests"] = [checked_installation(33), checked_installation(36)]
    report["device_install_test"] = "passed_on_emulators_not_a_physical_phone"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("DISTRIBUTION_VALIDATION=" + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
