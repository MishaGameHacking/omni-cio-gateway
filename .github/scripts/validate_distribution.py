"""Validate the built preview and record actual installation results before release."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--api", type=int, nargs="+", default=[33, 36])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    scripts = root / ".github" / "scripts"
    apk = root / "app" / "build" / "outputs" / "apk" / "preview" / "app-preview.apk"
    report_path = apk.with_name("apk-verification.json")
    gradle = (root / "app" / "build.gradle.kts").read_text(encoding="utf-8")
    match = re.search(r"versionCode\s*=\s*(\d+)", gradle)
    if match is None:
        raise ValueError("Cannot determine expected versionCode")
    subprocess.run(
        [sys.executable, str(scripts / "verify_apk.py"), "--apk", str(apk),
         "--sdk", str(args.sdk), "--version-code", match.group(1),
         "--certificate", str(root / ".github" / "apk-signing-certificate.sha256"),
         "--report", str(report_path), "--non-debuggable"],
        check=True, timeout=180,
    )
    if not args.api or any(api not in {33, 34, 35, 36} for api in args.api):
        raise ValueError("Choose a supported stable Android test API")
    if os.name != "nt":
        raise RuntimeError("This SDK preparation is configured for the Windows CI runner")
    os.environ["ANDROID_HOME"] = str(args.sdk)
    os.environ["ANDROID_SDK_ROOT"] = str(args.sdk)
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUNBUFFERED"] = "1"
    packages = []
    for name, binary in [("emulator", "emulator.exe"), ("platform-tools", "adb.exe")]:
        if not (args.sdk / name / binary).exists():
            packages.append(name)
    for api in args.api:
        if not (args.sdk / "system-images" / f"android-{api}" / "google_apis" / "x86_64" / "package.xml").exists():
            packages.append(f"system-images;android-{api};google_apis;x86_64")
    if packages:
        # Android CLI's emulator command is not supported on Windows yet:
        # https://developer.android.com/tools/agents/android-cli#known-issues
        manager = args.sdk / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat"
        result = subprocess.run(
            [str(manager), "--sdk_root=" + str(args.sdk), "--channel=0", *packages],
            input="y\n" * 200, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600, check=False,
        )
        print(result.stdout[-3000:] + result.stderr[-3000:], flush=True)
        result.check_returncode()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    installation_tests = []
    temp_root = os.environ.get("RUNNER_TEMP")
    for api in args.api:
        # Only this temporary directory and its disposable AVD can be removed.
        with tempfile.TemporaryDirectory(prefix=f"analyst-apk-api{api}-", dir=temp_root,
                                         ignore_cleanup_errors=True) as temporary:
            command = [sys.executable, str(scripts / "test_apk_installation.py"),
                       "--sdk", str(args.sdk), "--apk", str(apk), "--api", str(api),
                       "--work-dir", temporary]
            if args.previous:
                command += ["--previous", str(args.previous)]
            subprocess.run(command, check=True, timeout=1000)
            results = json.loads((Path(temporary) / "install-results.json").read_text(encoding="utf-8"))
            expected_tests = {"candidate_clean_install", "activity_launch"}
            if args.previous:
                expected_tests |= {"previous_clean_install", "upgrade_to_candidate"}
            actual_tests = {item["test"] for item in results if item.get("success") is True}
            if actual_tests != expected_tests:
                raise RuntimeError("Missing or failed Android installation test")
            installation_tests.append({"android_api": api, "abi": "x86_64", "results": results})
    report["device_install_test"] = "passed_on_emulators_not_a_physical_phone"
    report["installation_tests"] = installation_tests
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("DISTRIBUTION_VALIDATION=" + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
