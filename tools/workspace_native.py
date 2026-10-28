"""Run the unchanged complete native suite on exact laptop-built APKs."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

BASELINE_SHA = "d5216a4604edb611c9e124e1aa9472aa5323dfc65f97631dffe8c73b9b233a95"
BASELINE_BYTES = 29937843
BASELINE_ARTIFACT_SHA = "0303e6d8af4247bf5b33ef41b689e1a83b33bcea963d2b0de35d11485dd730cc"


def need(value, code):
    if not value:
        raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def baseline_from_archive(raw):
    """Use the immutable verified build50 artifact; no live download or TLS fallback."""
    need(0 < len(raw) <= 64 * 1024**2 and digest(raw) == BASELINE_ARTIFACT_SHA,
         "baseline_artifact_changed")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        need(len(names) < 500 and len(names) == len(set(names)), "ambiguous_baseline_artifact")
        matches = [name for name in names
                   if name.endswith("/app/build/outputs/apk/preview/app-preview.apk")]
        need(len(matches) == 1, "missing_unique_baseline")
        info = archive.getinfo(matches[0])
        need(info.file_size == BASELINE_BYTES, "baseline_size_changed")
        content = archive.read(info)
    need(len(content) == BASELINE_BYTES and digest(content) == BASELINE_SHA, "baseline50_changed")
    return content


def prepare(root, state, ci):
    raw = (Path(os.environ["RUNNER_TEMP"]) / "workspace-native-artifact.zip").read_bytes()
    need(len(raw) <= 256 * 1024**2 and digest(raw) == os.environ["EXPECTED_CLIENT_ARTIFACT_SHA256"],
         "native_artifact_changed")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        need(len(names) < 500 and len(names) == len(set(names)), "ambiguous_native_artifact")
        def member(suffix, maximum):
            matches = [name for name in names if name.endswith("/" + suffix)]
            need(len(matches) == 1, "missing_native_member")
            info = archive.getinfo(matches[0])
            need(0 < info.file_size <= maximum, "native_member_size_invalid")
            return archive.read(info)
        report = json.loads(member("result.json", 1024**2))
        need(report["source_commit"] == os.environ["EXPECTED_SOURCE_SHA"]
             and report["status"] == "passed" and report["host"] == ci.HOST
             and report["owned_processes_after"] == 0, "native_build_not_verified")
        expected = report["runtime_inputs"]
        need(set(expected) == set(ci.APK_PATHS), "native_apk_inventory_changed")
        for name in ci.APK_PATHS:
            content = member(name, 100 * 1024**2)
            need({"sha256": digest(content), "bytes": len(content)} == expected[name], "native_apk_changed")
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            ci.put_new(path, content)
    previous = state / "previous50.apk"
    raw = (Path(os.environ["RUNNER_TEMP"]) / "workspace-baseline-artifact.zip").read_bytes()
    ci.put_new(previous, baseline_from_archive(raw))
    return expected


def run_worker(root, state, ci):
    need(sys.stdin.buffer.readline(64) == b"NATIVE_CHECK_READY\n", "native_handshake_required")
    env, _ = ci.test_environment(root, state)
    steps = ci.Steps(root, state, "native", env)
    python = ci.new_venv(root, state, steps)
    for page in (4096, 16384):
        # Canonical test driver acquires the host emulator lease itself.
        steps.run("native-api37-" + str(page), [python, ".github/scripts/test_apk_installation.py",
            "--sdk", str(ci.SDK), "--apk", str(root / ci.APK_PATHS[0]),
            "--previous", str(state / "previous50.apk"), "--api", "37", "--page-bytes", str(page),
            "--work-dir", str(state / ("install-api37-" + str(page)))], 7200)


def main():
    root = Path.cwd().resolve(strict=True)
    sys.path.insert(0, str(root / ".github/scripts"))
    import windows_android_ci as ci
    need(sys.platform == "win32" and os.environ.get("COMPUTERNAME") == ci.HOST, "owner_laptop_required")
    state = Path(os.environ["RUNNER_TEMP"]) / ("workspace-native-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"])
    if "--worker" in sys.argv:
        run_worker(root, state, ci)
        return
    state.mkdir(exist_ok=False)
    head = os.environ["EXPECTED_SOURCE_SHA"]
    identity = {"tested_merge_sha": head, "event": "push"}
    before = ci.source_identity(root, identity)
    need(ci.git_blob(ci.read_bytes(root / ".github/scripts/emulator_lease.py", ci.MAX_JSON_BYTES)) == ci.LEASE_BLOB,
         "canonical_lease_changed")
    apks = prepare(root, state, ci)
    env, _ = ci.test_environment(root, state)
    report = {"source_commit": head, "host": ci.HOST, "status": "failed",
              "baseline_sha256": BASELINE_SHA, "apks": apks, "physical_phone_verified": False}
    process = None
    job = ci.OwnedJob()
    try:
        with (state / "native.log").open("xb") as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker"],
                cwd=root, env=env, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
            try:
                job.attach(process)
            except BaseException:
                process.kill()
                process.wait(timeout=30)
                raise
            process.stdin.write(b"NATIVE_CHECK_READY\n")
            process.stdin.close()
            deadline = time.monotonic() + 16500
            while process.poll() is None:
                need(time.monotonic() < deadline, "native_matrix_timeout")
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    print("WORKSPACE_NATIVE=running", flush=True)
            need(process.returncode == 0, "native_matrix_failed")
            need(ci.source_identity(root, identity) == before, "native_sources_changed")
            need(all(ci.file_identity(root / name) == value for name, value in apks.items()), "native_apks_changed")
            report["status"] = "passed"
    finally:
        try:
            job.stop()
            if process is not None:
                process.wait(timeout=30)
            deadline = time.monotonic() + 30
            while job.active() and time.monotonic() < deadline:
                time.sleep(.2)
            report["owned_processes_after"] = job.active()
            need(report["owned_processes_after"] == 0, "native_cleanup_incomplete")
        finally:
            job.close()
            (state / "result.json").write_text(json.dumps(report), encoding="utf-8")
            print("WORKSPACE_NATIVE_REPORT=" + json.dumps(report), flush=True)
            log_path = state / "native.log"
            if log_path.exists():
                print(log_path.read_text(encoding="utf-8", errors="replace")[-24000:], flush=True)


if __name__ == "__main__":
    main()
