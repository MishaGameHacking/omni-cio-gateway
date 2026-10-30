"""Render candidate57 production composables on the owner laptop; not native acceptance."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

REQUIRED_PREVIEWS = (
    ('Terminal57', 'terminal57-phone'),
    ('Terminal57', 'terminal57-full'),
    ('Terminal57', 'terminal57-large-text'),
    ('TerminalEmpty57', 'terminal57-empty'),
    ('TerminalPrivacy57', 'terminal57-private'),
    ('LoginAppearance', 'login-dark'),
    ('LoginAppearance', 'login-narrow-large-text'),
    ('LoginErrorAppearance', 'login-error-dark'),
    ('OwnerCooldown56', 'owner56-cooldown'),
    ('OwnerCooldown56', 'owner56-cooldown-large-text'),
    ('OwnerSetup55', 'owner55-setup'),
    ('OwnerSetup55', 'owner55-setup-large-text'),
    ('SettingsAppearance', 'settings-dark'),
    ('SettingsAppearance', 'settings-narrow-large-text'),
    ('SettingsAppearance', 'settings-tall-content-sheet'),
)
REQUIRED_PREVIEW_PREFIXES = tuple(function + "_" + preview for function, preview in REQUIRED_PREVIEWS)

def require_source_previews(source):
    cases = []
    for annotations, function in re.findall(
        r"@PreviewTest\s+((?:(?!@PreviewTest).)*?)@Composable\s+fun\s+(\w+)\s*\(", source, re.DOTALL
    ):
        cases.extend((function, preview) for preview in re.findall(r'@Preview\(\s*name\s*=\s*"([^"]+)"', annotations))
    missing = [function + "_" + preview for function, preview in REQUIRED_PREVIEWS
               if cases.count((function, preview)) != 1]
    if missing:
        raise ValueError("owner57_source_previews_incomplete:" + ",".join(missing))

def require_preview_inventory(paths):
    names = [path.name for path in paths]
    missing = [prefix for prefix in REQUIRED_PREVIEW_PREFIXES
               if sum(name.startswith(prefix + "_") and name.endswith(".png") for name in names) != 1]
    if missing:
        raise ValueError("owner57_preview_inventory_incomplete:" + ",".join(missing))

def snapshot_reference(reference):
    original = {}
    for path in reference.rglob("*.png"):
        if path.is_symlink():
            raise ValueError("render_reference_symlink")
        original[path.relative_to(reference)] = path.read_bytes()
    return original

def clear_reference(reference):
    # Only this run's isolated Git checkout is changed, under the canonical lease.
    # Removing backed-up PNGs prevents stale reference files from masquerading as new renders.
    for path in reference.rglob("*.png"):
        if path.is_symlink():
            raise ValueError("render_reference_symlink")
        path.unlink()

def restore_reference(reference, original):
    clear_reference(reference)
    for relative, raw in original.items():
        target = reference / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)

def finish_report(state, report, job):
    # Preserve a failed receipt even when Windows refuses to close the job handle.
    try:
        job.close()
    except BaseException as error:
        report["status"] = "failed"
        report["cleanup_error_type"] = type(error).__name__
        raise
    finally:
        (state / "result.json").write_text(json.dumps(report), encoding="utf-8")
        print("REDESIGN_RENDER_REPORT=" + json.dumps(report), flush=True)

def worker(root, state, ci):
    ci.need(sys.stdin.buffer.readline(64) == b"RENDER_READY\n", "render_handshake_required")
    env, _ = ci.test_environment(root, state)
    run = ci.Steps(root, state, "visual", env)
    key, key_before = ci.verify_machine(root, state, run)
    try:
        run.run("compose-preview-render", [os.environ["COMSPEC"], "/d", "/c", root / "gradlew.bat",
            ":app:updateDebugScreenshotTest", "--rerun-tasks", "--no-build-cache",
            "--no-daemon", "--max-workers=2", "--stacktrace"], 7200)
    finally:
        ci.need(ci.file_identity(key) == key_before, "render_signing_identity_changed")

def main():
    root = Path.cwd().resolve(strict=True)
    sys.path.insert(0, str(root / ".github/scripts"))
    import windows_android_ci as ci
    import emulator_lease
    ci.need(sys.platform == "win32" and os.environ.get("COMPUTERNAME") == ci.HOST, "owner_laptop_required")
    state = Path(os.environ["RUNNER_TEMP"]) / ("owner57-visual-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"])
    if "--worker" in sys.argv:
        worker(root, state, ci)
        return
    state.mkdir(exist_ok=False)
    source = os.environ["RENDER_SOURCE_SHA"]
    identity = {"tested_merge_sha": source, "event": "push"}
    before = ci.source_identity(root, identity)
    preview_source = root / "app/src/screenshotTest/kotlin/ru/omnicio/app/preview/AutomationAppearanceScreenshotTest.kt"
    require_source_previews(ci.read_bytes(preview_source, ci.MAX_JSON_BYTES).decode("utf-8"))
    ci.need(ci.git_blob(ci.read_bytes(root / ".github/scripts/emulator_lease.py", ci.MAX_JSON_BYTES)) == ci.LEASE_BLOB,
        "canonical_emulator_lease_changed")
    reference = root / "app/src/screenshotTestDebug/reference"
    ci.need(reference.is_dir() and not reference.is_symlink(), "render_reference_missing")
    original = snapshot_reference(reference)
    report = {"source_commit": source, "host": ci.HOST, "status": "failed", "native_acceptance": False,
        "fixture": "synthetic-Layoutlib-no-network", "baseline_updated": False,
        "required_preview_prefixes": list(REQUIRED_PREVIEW_PREFIXES)}
    env, signing_key = ci.test_environment(root, state)
    signing_before = ci.file_identity(signing_key)
    process = None
    with emulator_lease.exclusive_emulator():
        job = ci.OwnedJob()
        try:
            clear_reference(reference)
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
            require_preview_inventory(screenshots)
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
                restore_reference(reference, original)
                # Restore references before a missing signing key can raise. The
                # parent check also covers forced termination of the worker.
                report["signing_identity_unchanged"] = ci.file_identity(signing_key) == signing_before
                ci.need(ci.source_identity(root, identity) == before, "render_sources_changed")
                ci.need(report["signing_identity_unchanged"], "render_signing_identity_changed")
            except BaseException as error:
                report["status"] = "failed"
                report["cleanup_error_type"] = type(error).__name__
                raise
            finally:
                finish_report(state, report, job)
                for path in sorted(state.glob("visual-*.log")):
                    print(path.name + "\n" + path.read_text(encoding="utf-8", errors="replace")[-15000:])

if __name__ == "__main__":
    main()


