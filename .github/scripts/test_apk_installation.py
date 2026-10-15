"""Install only on a disposable, uniquely named emulator; never on a user's phone."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time


def run(args: list[str], *, timeout: int = 120, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, check=False)


def free_emulator_port() -> int:
    for port in range(5560, 5680, 2):
        with socket.socket() as console, socket.socket() as adb:
            try:
                console.bind(("127.0.0.1", port))
                adb.bind(("127.0.0.1", port + 1))
            except OSError:
                continue
            return port
    raise RuntimeError("No unused emulator port")


def record_profile_check(device, results, exercise) -> None:
    """A timeout/exception must leave an explicit failed result, not disappear."""
    result = {"test": "profile_ui", "success": False}
    results.append(result)
    try:
        exercise(device)
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        raise
    else:
        result["success"] = True


def collect_failure_diagnostics(device) -> None:
    """Bounded, best-effort reads of this disposable emulator only."""
    commands = (
        ("logcat", "-d", "-t", "200"),
        ("shell", "dumpsys", "SurfaceFlinger"),
    )
    for command in commands:
        try:
            diagnostic = device(*command, timeout=10)
            print("EMULATOR_DIAGNOSTIC=" + command[-1] + "\n" + diagnostic.stdout[-18000:], flush=True)
        except (subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
            print("EMULATOR_DIAGNOSTIC_UNAVAILABLE=" + type(exc).__name__, flush=True)


def main() -> None:
    from artifact_test_identity import apk_digest, record_install
    from emulator_lease import collect_runtime_failure, verify_emulator_identity

    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--sdk", required=True, type=Path)
    parser.add_argument("--api", default=36, type=int)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()
    apk = args.apk.resolve(strict=True)
    candidate_digest = apk_digest(apk)
    previous = args.previous.resolve(strict=True) if args.previous else None
    sdk = args.sdk.resolve(strict=True)
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    avd_home = work / "avd"
    avd_home.mkdir(exist_ok=True)
    os.environ["ANDROID_AVD_HOME"] = str(avd_home)
    os.environ["ANDROID_HOME"] = str(sdk)
    os.environ["ANDROID_SDK_ROOT"] = str(sdk)
    suffix = ".exe" if os.name == "nt" else ""
    batch = ".bat" if os.name == "nt" else ""
    adb = str(sdk / "platform-tools" / ("adb" + suffix))
    emulator = str(sdk / "emulator" / ("emulator" + suffix))
    manager = str(sdk / "cmdline-tools" / "latest" / "bin" / ("avdmanager" + batch))
    name = "analyst-install-" + str(os.getpid())
    image = f"system-images;android-{args.api};google_apis;x86_64"
    create = run([manager, "create", "avd", "--name", name, "--package", image,
                  "--path", str(avd_home / (name + ".avd"))], stdin="no\n")
    if create.returncode:
        raise RuntimeError("AVD creation failed: " + create.stdout + create.stderr)
    acceleration = run([emulator, "-accel-check"])
    print("EMULATOR_ACCELERATION=" + acceleration.stdout.strip(), flush=True)
    port = free_emulator_port()
    serial = f"emulator-{port}"
    log_path = work / "emulator.log"
    results: list[dict[str, object]] = []
    failed = True

    transient_adb_errors = (
        "device offline",
        "device not found",
        "no devices/emulators found",
        "cannot connect to daemon",
        "daemon not running",
        "closed",
    )

    def device(*command: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        """Retry only transport loss while the disposable emulator restarts.

        Android may briefly restart the emulator transport while applying system UI mode.
        ADB returning `device offline` is not an application failure, but all other command
        failures remain visible and fail closed.
        """
        recovery_deadline = time.monotonic() + max(timeout, 120)
        while True:
            try:
                response = run([adb, "-s", serial, *command], timeout=timeout)
            except subprocess.TimeoutExpired:
                if time.monotonic() >= recovery_deadline:
                    raise
                response = None
            if response is not None and response.returncode == 0:
                return response
            combined = "" if response is None else (response.stdout + "\n" + response.stderr).lower()
            transient = response is None or any(marker in combined for marker in transient_adb_errors)
            if not transient or time.monotonic() >= recovery_deadline:
                assert response is not None
                return response
            print("ADB_TRANSIENT_RECOVERY=" + (combined.strip() or "timeout"), flush=True)
            time.sleep(2)
            try:
                wait = run([adb, "-s", serial, "wait-for-device"], timeout=20)
            except subprocess.TimeoutExpired:
                continue
            if wait.returncode:
                continue
            try:
                boot = run(
                    [adb, "-s", serial, "shell", "getprop", "sys.boot_completed"],
                    timeout=15,
                )
            except subprocess.TimeoutExpired:
                continue
            if boot.returncode == 0 and boot.stdout.strip() == "1":
                time.sleep(2)

    def install(label: str, path: Path, update: bool = False) -> None:
        record_install(device, results, label, path, update=update)

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [emulator, "-avd", name, "-port", str(port), "-no-window", "-no-audio",
             "-no-snapshot", "-no-boot-anim", "-gpu", "swiftshader", "-feature", "-Vulkan",
             "-memory", "2048", "-cores", "2", "-accel", "on" if acceleration.returncode == 0 else "off"],
            stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Emulator exited before boot")
                try:
                    boot = device("shell", "getprop", "sys.boot_completed", timeout=15)
                except subprocess.TimeoutExpired:
                    continue
                if boot.returncode == 0 and boot.stdout.strip() == "1":
                    break
                time.sleep(5)
            else:
                raise TimeoutError("Emulator boot deadline exceeded")
            print("ANDROID_API=" + device("shell", "getprop", "ro.build.version.sdk").stdout.strip(), flush=True)
            verify_emulator_identity(device, name, args.api)
            package = "ru.omnicio.app.debug"
            if previous:
                install("previous_clean_install", previous)
                install("upgrade_to_candidate", apk, update=True)
                removed = device("uninstall", package)
                if removed.returncode or "Success" not in removed.stdout:
                    raise RuntimeError("Could not reset disposable emulator package")
            install("candidate_clean_install", apk)
            launch = device("shell", "am", "start", "-W", "-n", package + "/ru.omnicio.app.BootstrapActivity")
            print("LAUNCH_RESULT=" + launch.stdout + launch.stderr, flush=True)
            if launch.returncode or "Status: ok" not in launch.stdout:
                raise RuntimeError("Bootstrap launch failed")
            time.sleep(8)
            alive = device("shell", "pidof", package)
            if alive.returncode or not alive.stdout.strip():
                raise RuntimeError("App process did not remain running")
            if apk_digest(apk) != candidate_digest:
                raise RuntimeError("Candidate changed during emulator checks")
            results.append({"test": "bootstrap_activity_launch", "success": True, "apk_sha256": candidate_digest})
            print("BOOTSTRAP_ACTIVITY_LAUNCH=success", flush=True)
            if args.api == 36 and os.getenv("RUN_PROFILE_UI_TESTS") == "1":
                from profile_ui_probe import exercise
                debug_apk = Path(__file__).resolve().parents[2] / "app/build/outputs/apk/debug/app-debug.apk"
                install("debug_ui_fixture_install", debug_apk, update=True)
                record_profile_check(device, results, exercise)
            failed = False
        finally:
            log.flush()
            (work / "install-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
            if failed:
                collect_runtime_failure(device)
                collect_failure_diagnostics(device)
            try:
                identity = device("emu", "avd", "name", timeout=10)
                if name in identity.stdout.splitlines():
                    device("emu", "kill", timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                pass
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            print("EMULATOR_LOG_TAIL=" + log_path.read_text(encoding="utf-8", errors="replace")[-5000:], flush=True)


if __name__ == "__main__":
    from emulator_lease import exclusive_emulator
    with exclusive_emulator():
        main()
