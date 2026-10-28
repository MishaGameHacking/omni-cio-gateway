"""Render production Compose previews only on the owner laptop; not native acceptance."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

def worker(root, state, ci):
    ci.need(sys.stdin.buffer.readline(64) == b"RENDER_READY\n", "render_handshake_required")
    env, _ = ci.test_environment(root, state)
    run = ci.Steps(root, state, "visual", env)
    key, key_before = ci.verify_machine(root, state, run)
    try:
        run.run("compose-preview-render", [os.environ["COMSPEC"], "/d", "/c", root / "gradlew.bat",
            ":app:updateDebugScreenshotTest", "--no-daemon", "--max-workers=2", "--stacktrace"], 7200)
    finally:
        ci.need(ci.file_identity(key) == key_before, "render_signing_identity_changed")

def main():
    root = Path.cwd().resolve(strict=True)
    sys.path.insert(0, str(root / ".github/scripts"))
    import windows_android_ci as ci
    import emulator_lease
    ci.need(sys.platform == "win32" and os.environ.get("COMPUTERNAME") == ci.HOST, "owner_laptop_required")
    state = Path(os.environ["RUNNER_TEMP"]) / ("redesign-visual-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"])
    if "--worker" in sys.argv:
        worker(root, state, ci)
        return
    state.mkdir(exist_ok=False)
    source = os.environ["RENDER_SOURCE_SHA"]
    identity = {"tested_merge_sha": source, "event": "push"}
    before = ci.source_identity(root, identity)
    ci.need(ci.git_blob(ci.read_bytes(root / ".github/scripts/emulator_lease.py", ci.MAX_JSON_BYTES)) == ci.LEASE_BLOB,
        "canonical_emulator_lease_changed")
    reference = root / "app/src/screenshotTestDebug/reference"
    ci.need(reference.is_dir() and not reference.is_symlink(), "render_reference_missing")
    original = {path.relative_to(reference): path.read_bytes() for path in reference.rglob("*.png")}
    report = {"source_commit": source, "host": ci.HOST, "status": "failed", "native_acceptance": False,
        "fixture": "synthetic-Layoutlib-no-network", "baseline_updated": False}
    env, _ = ci.test_environment(root, state)
    process = None
    with emulator_lease.exclusive_emulator():
        job = ci.OwnedJob()
        try:
            with (state / "render.log").open("xb") as log:
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker"],
                    cwd=root, env=env, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
                try:
                    job.attach(process)
                except BaseException:
                    process.kill()
                    process.wait(timeout=30)
                    raise
                process.stdin.write(b"RENDER_READY\n")
                process.stdin.close()
                deadline = time.monotonic() + 8400
                while process.poll() is None:
                    ci.need(time.monotonic() < deadline, "render_timeout")
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        print("REDESIGN_RENDER=running", flush=True)
                ci.need(process.returncode == 0, "compose_render_failed")
            screenshots = sorted(reference.rglob("*.png"))
            ci.need(len(screenshots) >= 20, "render_inventory_incomplete")
            report["screenshots"] = []
            for path in screenshots:
                target = state / "screens" / path.relative_to(reference)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                report["screenshots"].append({"path": str(path.relative_to(reference)), **ci.file_identity(target)})
            report["status"] = "rendered-awaiting-visual-review"
        finally:
            try:
                job.stop()
                if process is not None: process.wait(timeout=30)
                deadline = time.monotonic() + 30
                while job.active() and time.monotonic() < deadline: time.sleep(.2)
                report["owned_processes_after"] = job.active()
                ci.need(report["owned_processes_after"] == 0, "render_cleanup_incomplete")
                # Only generated reference PNGs in this owned checkout are restored.
                # They were copied to the evidence directory, never silently accepted.
                for path in reference.rglob("*.png"):
                    relative = path.relative_to(reference)
                    if relative not in original: path.unlink()
                for relative, raw in original.items(): (reference / relative).write_bytes(raw)
                ci.need(ci.source_identity(root, identity) == before, "render_sources_changed")
            finally:
                job.close()
                (state / "result.json").write_text(json.dumps(report), encoding="utf-8")
                print("REDESIGN_RENDER_REPORT=" + json.dumps(report), flush=True)
                for path in sorted(state.glob("visual-*.log")):
                    print(path.name + "\n" + path.read_text(encoding="utf-8", errors="replace")[-15000:])

if __name__ == "__main__":
    main()
