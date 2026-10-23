"""Independent stock-image control, never an APK or publication receipt.

Only the ephemeral GitHub-hosted Linux VM may execute this diagnostic. The
Windows release gate and its complete Android 15/16 matrix remain unchanged.
"""
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
import time

from emulator_boot_readiness import prepared_emulator_session

API = 35
CONTROL_SECONDS = 90
FATAL = re.compile(r"FATAL EXCEPTION|Fatal signal |WATCHDOG KILLING SYSTEM PROCESS")


def require_ephemeral_linux(environment, platform):
    if (platform != "posix" or environment.get("RUNNER_OS") != "Linux"
            or environment.get("GITHUB_ACTIONS") != "true"
            or environment.get("RUNNER_ENVIRONMENT") != "github-hosted"):
        raise RuntimeError("Runtime control requires an ephemeral GitHub-hosted Linux VM")


def require_healthy_control(page_size, crash_log):
    if page_size.strip() != "16384":
        raise RuntimeError("The control must actually run with 16 KB pages")
    if FATAL.search(crash_log):
        raise RuntimeError("The stock Android image recorded a fatal crash without the candidate")


def run_command(args, *, timeout=15, stdin=None):
    return subprocess.run(args, input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, check=False)


def require_command(args, *, timeout=15, stdin=None):
    result = run_command(args, timeout=timeout, stdin=stdin)
    if result.returncode != 0:
        raise RuntimeError("Control command failed: " + " ".join(map(str, args))
                           + "\n" + (result.stdout + result.stderr)[-4096:])
    return result.stdout


def wait_for_boot(device, process):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Stock-image emulator exited before boot")
        try:
            result = device("shell", "getprop", "sys.boot_completed", timeout=10)
            if result.returncode == 0 and result.stdout.strip() == "1":
                return
        except subprocess.TimeoutExpired:
            pass
        time.sleep(3)
    raise TimeoutError("Stock-image emulator did not boot within five minutes")


def diagnose(device):
    for command in (("logcat", "-d", "-b", "crash", "-v", "threadtime"),
                    ("logcat", "-d", "-b", "events", "-t", "100"),
                    ("shell", "dumpsys", "meminfo")):
        try:
            response = device(*command, timeout=15)
            print("CONTROL_DIAGNOSTIC=" + " ".join(command) + "\n"
                  + (response.stdout + response.stderr)[:20000], flush=True)
        except (OSError, subprocess.TimeoutExpired) as error:
            print("CONTROL_DIAGNOSTIC_UNAVAILABLE=" + type(error).__name__, flush=True)


def observe_stock_android(device, process, name, sdk):
    from emulator_runtime import snapshot_runtime_environment

    wait_for_boot(device, process)
    print("CONTROL_RUNTIME=" + json.dumps(snapshot_runtime_environment(device, sdk, API),
                                         sort_keys=True), flush=True)
    with prepared_emulator_session(device, name, API):
        pages = device("shell", "getconf", "PAGE_SIZE", timeout=15)
        if pages.returncode != 0:
            raise RuntimeError("Cannot read control kernel page size")
        require_healthy_control(pages.stdout, "")
        packages = device("shell", "cmd", "package", "list", "packages", timeout=15)
        if packages.returncode != 0 or not packages.stdout.startswith("package:"):
            raise RuntimeError("Stock PackageManager did not return installed packages")
        if re.search(r"(?m)^package:ru\.omnicio\.app(?:\.[\w.]+)?$", packages.stdout):
            raise RuntimeError("The control is not independent: candidate package already present")
        time.sleep(CONTROL_SECONDS)
        crash = device("logcat", "-d", "-b", "crash", "-v", "threadtime", timeout=15)
        if crash.returncode != 0:
            raise RuntimeError("Cannot read the stock-image crash buffer")
        require_healthy_control(pages.stdout, crash.stdout)


def control(sdk, work):
    from emulator_storage import configure_userdata
    from isolated_adb import isolated_adb_server, stop_owned_server
    from kernel_page_size import system_image

    avd_home = work / "avd"
    avd_home.mkdir()
    os.environ["ANDROID_AVD_HOME"] = str(avd_home)
    (work / "emulator-home").mkdir()
    os.environ["ANDROID_EMULATOR_HOME"] = str(work / "emulator-home")
    os.environ["ANDROID_HOME"] = str(sdk)
    os.environ["ANDROID_SDK_ROOT"] = str(sdk)
    name = f"analyst-install-{os.getpid()}-1"
    adb = sdk / "platform-tools/adb"
    emulator = sdk / "emulator/emulator"
    image = system_image(API)
    require_command([sdk / "cmdline-tools/latest/bin/avdmanager", "create", "avd", "--name", name,
                     "--package", image, "--path", avd_home / (name + ".avd")],
                    timeout=120, stdin="no\n")
    configure_userdata(avd_home / (name + ".avd"), sdk, image)
    print("CONTROL_ACCELERATION=" + require_command([emulator, "-accel-check"]), flush=True)
    with isolated_adb_server(adb, work):
        def device(*args, timeout=15):
            return run_command([adb, "-s", "emulator-5554", *args], timeout=timeout)

        log_path = work / "emulator.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen([
                str(emulator), "-avd", name, "-port", "5554", "-no-window", "-no-audio",
                "-no-snapshot", "-no-boot-anim", "-timezone", "Etc/UTC", "-gpu", "swiftshader",
                "-feature", "Vulkan,GuestAngle", "-memory", "4096", "-cores", "2", "-accel", "on",
            ], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            failure = None
            try:
                observe_stock_android(device, process, name, sdk)
            except BaseException as error:
                failure = error
                raise
            finally:
                diagnose(device)
                try:
                    stop_owned_server(process)
                except (OSError, subprocess.TimeoutExpired) as error:
                    if failure is None:
                        raise
                    failure.add_note("Control process cleanup failed: " + type(error).__name__)
                log.flush()
                print("CONTROL_EMULATOR_LOG=" + log_path.read_text(encoding="utf-8", errors="replace")[-8000:],
                      flush=True)
    print("STOCK_RUNTIME_CONTROL=" + json.dumps({
        "stock_image_healthy": True, "android_api": API, "page_size_bytes": 16384,
        "observation_seconds": CONTROL_SECONDS, "gpu_mode": "swiftshader", "host": "Linux/KVM",
        "apk_test_performed": False, "publication_authorized": False,
    }, sort_keys=True), flush=True)


def main():
    require_ephemeral_linux(os.environ, os.name)
    sdk = Path(os.environ["ANDROID_SDK_ROOT"]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="analyst-runtime-control-", dir=os.environ["RUNNER_TEMP"]) as work:
        control(sdk, Path(work))


if __name__ == "__main__":
    main()
