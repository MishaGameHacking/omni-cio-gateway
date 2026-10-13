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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--sdk", required=True, type=Path)
    parser.add_argument("--api", default=33, type=int)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()
    apk = args.apk.resolve(strict=True)
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

    def device(*command: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        # The target is explicitly the emulator we started, never an implicit device.
        return run([adb, "-s", serial, *command], timeout=timeout)

    def install(label: str, path: Path, update: bool = False) -> None:
        command = ["install", "--no-streaming"]
        if update:
            command.append("-r")
        output = device(*command, str(path), timeout=240)
        ok = output.returncode == 0 and "Success" in output.stdout
        result = {"test": label, "success": ok, "output": (output.stdout + output.stderr).strip()}
        results.append(result)
        print("INSTALL_RESULT=" + json.dumps(result, ensure_ascii=True), flush=True)
        if not ok:
            raise RuntimeError("APK installation failed: " + label)

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [emulator, "-avd", name, "-port", str(port), "-no-window", "-no-audio",
             "-no-snapshot", "-no-boot-anim", "-gpu", "software", "-memory", "2048",
             "-cores", "2", "-accel", "on" if acceleration.returncode == 0 else "off"],
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
            package = "ru.omnicio.app.debug"
            if previous:
                install("previous_clean_install", previous)
                install("upgrade_to_candidate", apk, update=True)
                removed = device("uninstall", package)
                if removed.returncode or "Success" not in removed.stdout:
                    raise RuntimeError("Could not reset disposable emulator package")
            install("candidate_clean_install", apk)
            launch = device("shell", "am", "start", "-W", "-n", package + "/ru.omnicio.app.MainActivity")
            print("LAUNCH_RESULT=" + launch.stdout + launch.stderr, flush=True)
            if launch.returncode or "Status: ok" not in launch.stdout:
                raise RuntimeError("Activity launch failed")
            time.sleep(8)
            alive = device("shell", "pidof", package)
            if alive.returncode or not alive.stdout.strip():
                raise RuntimeError("App process did not remain running")
            results.append({"test": "activity_launch", "success": True})
            print("ACTIVITY_LAUNCH=success", flush=True)
            if args.api == 33 and os.getenv("RUN_PROFILE_UI_TESTS") == "1":
                from profile_ui_probe import exercise
                debug_apk = Path(__file__).resolve().parents[2] / "app/build/outputs/apk/debug/app-debug.apk"
                install("debug_ui_fixture_install", debug_apk, update=True)
                exercise(device)
                results.append({"test": "profile_ui", "success": True})
        finally:
            log.flush()
            if any(not item["success"] for item in results):
                diagnostic = device("logcat", "-d", "-t", "200", timeout=30)
                print(diagnostic.stdout[-18000:], flush=True)
            try:
                identity = device("emu", "avd", "name", timeout=10)
                if name in identity.stdout:
                    device("emu", "kill", timeout=10)
            except subprocess.TimeoutExpired:
                pass
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            (work / "install-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
            print("EMULATOR_LOG_TAIL=" + log_path.read_text(encoding="utf-8", errors="replace")[-5000:], flush=True)


if __name__ == "__main__":
    main()
