"""Check and build the one-time server-aware shell on the owner laptop."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import emulator_lease
import windows_android_ci as ci


def run_worker(root, state):
    ci.need(sys.stdin.buffer.readline(64) == b"VERSION_CHECK_READY\n", "worker_handshake_required")
    env, _ = ci.test_environment(root, state)
    run = ci.Steps(root, state, "shell-build", env)
    ci.build_worker(root, state, run)


def main():
    ci.need(sys.platform == "win32" and os.environ.get("COMPUTERNAME") == ci.HOST,
            "owner_laptop_required")
    root = Path(__file__).resolve().parents[2]
    state = Path(os.environ["RUNNER_TEMP"]) / (
        "server-version-client-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"])
    if "--worker" in sys.argv:
        run_worker(root, state)
        return
    state.mkdir(exist_ok=False)
    identity = {"tested_merge_sha": os.environ["GITHUB_SHA"], "event": "push"}
    before = ci.source_identity(root, identity)
    ci.need(ci.git_blob(ci.read_bytes(root / ".github/scripts/emulator_lease.py", ci.MAX_JSON_BYTES))
            == ci.LEASE_BLOB, "canonical_emulator_lease_changed")
    env, _ = ci.test_environment(root, state)
    report = {"source_commit": os.environ["GITHUB_SHA"], "host": ci.HOST,
              "status": "failed", "apk_published": False, "physical_phone_verified": False}
    process = None
    with emulator_lease.exclusive_emulator():
        job = ci.OwnedJob()
        try:
            with (state / "gradle.log").open("xb") as log:
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker"],
                    cwd=root, env=env, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
                try:
                    job.attach(process)
                except BaseException:
                    process.kill()
                    process.wait(timeout=30)
                    raise
                process.stdin.write(b"VERSION_CHECK_READY\n")
                process.stdin.close()
                deadline = time.monotonic() + 10800
                while process.poll() is None:
                    ci.need(time.monotonic() < deadline, "version_check_timeout")
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        print("VERSION_CLIENT_CHECK=running", flush=True)
                ci.need(process.returncode == 0, "version_client_checks_failed")
                ci.need(ci.source_identity(root, identity) == before, "verified_sources_changed")
                report["apk"] = ci.read_json(root / "app/build/outputs/apk/preview/apk-verification.json")
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
                ci.need(report["owned_processes_after"] == 0, "owned_cleanup_incomplete")
            finally:
                job.close()
                (state / "result.json").write_text(json.dumps(report), encoding="utf-8")
                print("VERSION_CLIENT_REPORT=" + json.dumps(report), flush=True)
                log_path = state / "gradle.log"
                if log_path.exists():
                    print(log_path.read_text(encoding="utf-8", errors="replace")[-24000:], flush=True)


if __name__ == "__main__":
    main()
