"""Install only on a disposable, uniquely named emulator; never on a user's phone."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
from collections.abc import Callable

UIAUTOMATOR_PROCESS = "com.android.commands.uiautomator"
UIAUTOMATOR_CONNECT_MARKERS = (
    "timeout while connecting uiautomation",
    "error while connecting uiautomation",
    "null root node returned by uitestautomationbridge",
)
ADB_TRANSIENT_MARKERS = (
    "device offline",
    "device not found",
    "device 'emulator-",
    "no devices/emulators found",
    "cannot connect to daemon",
    "daemon not running",
    "closed",
)
UIAUTOMATOR_MIN_INTERVAL_SECONDS = 0.75
UIAUTOMATOR_RECOVERY_SECONDS = 45
EMULATOR_ATTEMPTS = 2


class EmulatorTransportLost(OSError):
    """The disposable emulator or its ADB transport disappeared."""

    emulator_transport_lost = True


def run(args: list[str], *, timeout: int = 120, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def is_uiautomator_dump(command: tuple[str, ...]) -> bool:
    """Match only the disposable emulator's accessibility-tree command."""
    return len(command) >= 3 and command[:3] == ("shell", "uiautomator", "dump")


def is_uiautomator_connect_timeout(
    command: tuple[str, ...],
    response_text: str,
    crash_text: str = "",
) -> bool:
    """Classify only Android's transient UiAutomation failures as recoverable.

    A later successful dump is still required; this helper never converts a failed
    UI assertion into a pass. Crash-buffer evidence additionally requires the
    system uiautomator process identity so an app crash cannot be misclassified.
    """
    if not is_uiautomator_dump(command):
        return False
    response = response_text.lower()
    if any(marker in response for marker in UIAUTOMATOR_CONNECT_MARKERS):
        return True
    crash = crash_text.lower()
    return UIAUTOMATOR_PROCESS in crash and any(
        marker in crash for marker in UIAUTOMATOR_CONNECT_MARKERS
    )


def is_transient_adb_transport_failure(response_text: str) -> bool:
    """Recognize only bounded ADB/emulator transport failures.

    The quoted-serial form matches Android platform-tools output such as
    ``adb.exe: device 'emulator-5560' not found`` without treating an ordinary
    shell-level ``file not found`` message as an emulator loss.
    """
    response = response_text.lower()
    return any(marker in response for marker in ADB_TRANSIENT_MARKERS)


def adb_transport_connected(adb: str, serial: str) -> bool:
    """Independently distinguish a command timeout from an offline emulator."""
    try:
        state = run([adb, "-s", serial, "get-state"], timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return state.returncode == 0 and state.stdout.strip() == "device"


def classify_frame_failure(error: Exception, adb: str, serial: str, process) -> Exception:
    """Retry a broken frame stream only with independent emulator-loss evidence."""
    if not isinstance(error, ConnectionError):
        return error
    exit_code = process.poll()
    connected = exit_code is None and adb_transport_connected(adb, serial)
    print(
        f"FRAME_TRANSPORT_STATE=exit_code:{exit_code};adb_connected:{connected}",
        flush=True,
    )
    if connected:
        return error
    return EmulatorTransportLost(
        f"{serial} lost during frame read; emulator_exit_code={exit_code}"
    )

def free_emulator_port() -> int:
    # Outside the default 5555..5585 discovery range of unrelated ADB servers.
    for port in range(5600, 5680, 2):
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
        receipt = exercise(device)
        if not isinstance(receipt, dict) or set(receipt) != {
            "ui_suite", "business_case_count", "business_cases", "portfolio_case_count", "portfolio_cases",
        }:
            raise ValueError("Profile UI did not return its completed runtime matrix")
        fixtures = [row for row in results if row.get("test") == "debug_ui_fixture_install" and row.get("success") is True]
        if len(fixtures) != 1:
            raise ValueError("The UI receipt has no unique installed debug fixture")
        result.update(receipt)
        result["fixture_apk_sha256"] = fixtures[0].get("apk_sha256")
        from installation_report import validate_current_ui
        validate_current_ui(result, fixtures[0])
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
            print(
                "EMULATOR_DIAGNOSTIC="
                + command[-1]
                + "\n"
                + diagnostic.stdout[-18000:],
                flush=True,
            )
        except (subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
            print(
                "EMULATOR_DIAGNOSTIC_UNAVAILABLE=" + type(exc).__name__,
                flush=True,
            )


def candidate_package_uid(output: str) -> str | None:
    """Resolve only this installed APK's UID, including after its process died."""
    matches = []
    for line in output.splitlines():
        match = re.fullmatch(r"package:ru\.omnicio\.app\.debug uid:([0-9]{1,10})", line.strip())
        if match is not None:
            value = int(match.group(1))
            if 10000 <= value <= 2147483647:
                matches.append(str(value))
    return matches[0] if len(matches) == 1 else None


def collect_graphics_diagnostics(device) -> None:
    """Retain shader errors and app PIDs before unrelated log traffic hides them.

    Read the bounded Android log buffers through tag/UID filters, not a global
    last-N-lines query. The package UID still identifies the failed process after
    SIGABRT; threadtime output retains its exact PID/TID. Each read has a deadline
    and the printed excerpt is bounded. Diagnostics never turn a failure into a
    pass or authorize an emulator retry.
    """
    commands = [(
        "shader-main-system",
        ("logcat", "-d", "-b", "main", "-b", "system", "-v", "threadtime",
         "Filament:V", "filament:V", "Spectrum3D:V", "libc:F", "*:S"),
    )]
    try:
        identity = device("shell", "cmd", "package", "list", "packages", "-U",
                          "ru.omnicio.app.debug", timeout=10)
        uid = candidate_package_uid(identity.stdout) if identity.returncode == 0 else None
        if uid is not None:
            commands.append((
                "candidate-uid-" + uid,
                ("logcat", "-d", "-b", "main", "-b", "system", "-v", "threadtime", "--uid=" + uid),
            ))
        else:
            print("EMULATOR_GRAPHICS_IDENTITY=unavailable", flush=True)
    except (subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
        print("EMULATOR_GRAPHICS_IDENTITY=" + type(exc).__name__, flush=True)
    for label, command in commands:
        try:
            diagnostic = device(*command, timeout=10)
            if diagnostic.returncode:
                print("EMULATOR_GRAPHICS_DIAGNOSTIC_UNAVAILABLE=" + label, flush=True)
                continue
            output = diagnostic.stdout
            if len(output) > 32000:
                output = output[:16000] + "\n[bounded diagnostic: middle omitted]\n" + output[-16000:]
            print("EMULATOR_GRAPHICS_DIAGNOSTIC=" + label + "\n" + output, flush=True)
        except (subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
            print("EMULATOR_GRAPHICS_DIAGNOSTIC_UNAVAILABLE=" + label + ":" + type(exc).__name__, flush=True)


def run_with_transport_retry(
    execute: Callable[[int], list[dict[str, object]]],
    *,
    attempts: int = EMULATOR_ATTEMPTS,
) -> list[dict[str, object]]:
    """Restart the whole disposable-emulator contract once after transport loss.

    UI assertions, palette mismatches and app failures are deliberately not
    retried. A retry starts a new AVD and reruns upgrade, clean install, launch,
    and the complete UI exercise; no partial screenshot or stale tree can pass.
    """
    if type(attempts) is not int or not 1 <= attempts <= 2:
        raise ValueError("Invalid emulator attempt count")
    for attempt in range(1, attempts + 1):
        try:
            return execute(attempt)
        except EmulatorTransportLost as exc:
            print(
                f"EMULATOR_TRANSPORT_RESTART=attempt-{attempt};"
                + str(exc).replace("\n", " ")[-1000:],
                flush=True,
            )
            if attempt == attempts:
                raise
    raise AssertionError("Emulator retry loop did not finish")


def _safe_attempt_directory(root: Path, attempt: int) -> Path:
    directory = root / f"attempt-{attempt}"
    resolved_root = root.resolve()
    if directory.is_symlink() or not directory.resolve().is_relative_to(resolved_root):
        raise ValueError("Emulator attempt directory escapes work directory")
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    return directory


def _write_report(path: Path, results: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")


def run_attempt(
    *,
    apk: Path,
    candidate_digest: str,
    previous: Path | None,
    sdk: Path,
    api: int,
    work: Path,
    attempt: int,
) -> list[dict[str, object]]:
    """Execute the complete publication-grade contract in one fresh AVD."""
    from artifact_test_identity import apk_digest, record_install
    from emulator_lease import collect_runtime_failure, verify_emulator_identity

    avd_home = work / "avd"
    avd_home.mkdir(exist_ok=True)
    os.environ["ANDROID_AVD_HOME"] = str(avd_home)
    os.environ["ANDROID_HOME"] = str(sdk)
    os.environ["ANDROID_SDK_ROOT"] = str(sdk)
    suffix = ".exe" if os.name == "nt" else ""
    batch = ".bat" if os.name == "nt" else ""
    adb = str(sdk / "platform-tools" / ("adb" + suffix))
    emulator = str(sdk / "emulator" / ("emulator" + suffix))
    manager = str(
        sdk / "cmdline-tools" / "latest" / "bin" / ("avdmanager" + batch)
    )
    name = f"analyst-install-{os.getpid()}-{attempt}"
    from kernel_page_size import measured_record, system_image

    image = system_image(api)
    create = run(
        [
            manager,
            "create",
            "avd",
            "--name",
            name,
            "--package",
            image,
            "--path",
            str(avd_home / (name + ".avd")),
        ],
        stdin="no\n",
    )
    if create.returncode:
        raise RuntimeError("AVD creation failed: " + create.stdout + create.stderr)
    acceleration = run([emulator, "-accel-check"])
    print("EMULATOR_ACCELERATION=" + acceleration.stdout.strip(), flush=True)
    port = free_emulator_port()
    serial = f"emulator-{port}"
    log_path = work / "emulator.log"
    results: list[dict[str, object]] = []
    failed = True

    last_uiautomator_dump_finished = 0.0
    process: subprocess.Popen[str] | None = None
    transport_lost = False

    def device(*command: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        """Retry bounded transport races, then report a real transport loss.

        A confirmed transport loss is eligible only for a full fresh-AVD retry.
        Ordinary command errors are returned to the caller and UI assertions
        still fail immediately.
        """
        nonlocal last_uiautomator_dump_finished, transport_lost
        ui_dump = is_uiautomator_dump(command)
        recovery_window = (
            UIAUTOMATOR_RECOVERY_SECONDS
            if ui_dump
            else max(30, min(timeout, 120))
        )
        recovery_deadline = time.monotonic() + recovery_window
        while True:
            if ui_dump:
                remaining = UIAUTOMATOR_MIN_INTERVAL_SECONDS - (
                    time.monotonic() - last_uiautomator_dump_finished
                )
                if remaining > 0:
                    time.sleep(remaining)
            try:
                response = run([adb, "-s", serial, *command], timeout=timeout)
            except subprocess.TimeoutExpired:
                response = None
            finally:
                if ui_dump:
                    last_uiautomator_dump_finished = time.monotonic()

            combined = "" if response is None else response.stdout + "\n" + response.stderr
            # Only THIS command's output is evidence of a recoverable bridge
            # error. A historic crash-buffer entry cannot authorize a retry.
            uiautomator_timeout = is_uiautomator_connect_timeout(command, combined)
            if response is not None and response.returncode == 0 and not uiautomator_timeout:
                return response

            process_exited = process is not None and process.poll() is not None
            if response is None and not process_exited and adb_transport_connected(adb, serial):
                # A timed-out UI command is not a lost device. Do not restart the
                # whole test and accidentally hide an app/UI failure.
                raise subprocess.TimeoutExpired([adb, "-s", serial, *command], timeout)

            transient_transport = response is None or is_transient_adb_transport_failure(combined)
            if not transient_transport and not uiautomator_timeout:
                return response

            expired = time.monotonic() >= recovery_deadline
            if not process_exited and uiautomator_timeout and not transient_transport:
                if expired:
                    raise RuntimeError("UiAutomation bridge did not recover: " + combined[-1000:])
                print("UIAUTOMATOR_TRANSIENT_RECOVERY=" + combined.strip()[-2000:], flush=True)
                time.sleep(2)
                continue

            if expired and not process_exited and adb_transport_connected(adb, serial):
                raise RuntimeError("ADB command failed on a connected emulator: " + combined[-1000:])
            if process_exited or expired:
                detail = combined.strip() or "ADB transport did not answer get-state"
                transport_lost = True
                raise EmulatorTransportLost(
                    f"{serial} unavailable during {' '.join(command)}: " + detail[-1000:]
                )

            print(
                "ADB_TRANSIENT_RECOVERY=" + (combined.strip() or "timeout"),
                flush=True,
            )
            time.sleep(2)
            try:
                wait = run(
                    [adb, "-s", serial, "wait-for-device"],
                    timeout=20,
                )
            except subprocess.TimeoutExpired:
                continue
            if wait.returncode:
                continue
            try:
                boot = run(
                    [
                        adb,
                        "-s",
                        serial,
                        "shell",
                        "getprop",
                        "sys.boot_completed",
                    ],
                    timeout=15,
                )
            except subprocess.TimeoutExpired:
                continue
            if boot.returncode == 0 and boot.stdout.strip() == "1":
                time.sleep(2)

    def install(label: str, path: Path, update: bool = False) -> None:
        record_install(device, results, label, path, update=update)

    def launch_candidate(label: str) -> None:
        """Launch the exact candidate and retain an explicit pass/fail record."""
        result: dict[str, object] = {
            "test": label,
            "success": False,
            "apk_sha256": candidate_digest,
        }
        results.append(result)
        try:
            launch = device(
                "shell",
                "am",
                "start",
                "-W",
                "-n",
                "ru.omnicio.app.debug/ru.omnicio.app.BootstrapActivity",
            )
            print(
                label.upper() + "_RESULT=" + launch.stdout + launch.stderr,
                flush=True,
            )
            if launch.returncode or "Status: ok" not in launch.stdout:
                raise RuntimeError(f"{label} failed")
            time.sleep(8)
            alive = device("shell", "pidof", "ru.omnicio.app.debug")
            if alive.returncode or not alive.stdout.strip():
                raise RuntimeError(f"{label} process did not remain running")
            if apk_digest(apk) != candidate_digest:
                raise RuntimeError("Candidate changed during emulator checks")
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            raise
        else:
            result["success"] = True
            print(label.upper() + "=success", flush=True)

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                emulator,
                "-avd",
                name,
                "-port",
                str(port),
                "-no-window",
                "-no-audio",
                "-no-snapshot",
                "-no-boot-anim",
                # Fix the disposable device's local zone for the actual calendar
                # UTC/Moscow date-boundary checks; never inherit the runner host.
                # developer.android.com/studio/run/emulator-commandline#common
                "-timezone",
                "Etc/UTC",
                "-gpu",
                "swiftshader",
                "-feature",
                "-Vulkan",
                "-memory",
                "2048",
                "-cores",
                "2",
                "-accel",
                "on" if acceleration.returncode == 0 else "off",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    transport_lost = True
                    raise EmulatorTransportLost("Emulator exited before boot")
                try:
                    boot = run(
                        [
                            adb,
                            "-s",
                            serial,
                            "shell",
                            "getprop",
                            "sys.boot_completed",
                        ],
                        timeout=15,
                    )
                except subprocess.TimeoutExpired:
                    boot = None
                if (
                    boot is not None
                    and boot.returncode == 0
                    and boot.stdout.strip() == "1"
                ):
                    break
                time.sleep(5)
            else:
                raise TimeoutError("Emulator boot deadline exceeded")

            print(
                "ANDROID_API="
                + device(
                    "shell",
                    "getprop",
                    "ro.build.version.sdk",
                ).stdout.strip(),
                flush=True,
            )
            verify_emulator_identity(device, name, api)
            page_size = device("shell", "getconf", "PAGE_SIZE")
            try:
                if page_size.returncode:
                    raise RuntimeError("The booted kernel could not report its page size")
                kernel = measured_record(api, page_size.stdout, candidate_digest)
            except (RuntimeError, ValueError):
                results.append({"test": "kernel_page_size", "success": False,
                                "android_api": api, "system_image": image,
                                "observed": page_size.stdout.strip()[:80]})
                raise
            results.append(kernel)
            print("KERNEL_PAGE_SIZE=" + json.dumps(kernel, sort_keys=True), flush=True)
            package = "ru.omnicio.app.debug"
            if previous:
                install("previous_clean_install", previous)
                install("upgrade_to_candidate", apk, update=True)
                launch_candidate("upgrade_bootstrap_launch")
                removed = device("uninstall", package)
                if removed.returncode or "Success" not in removed.stdout:
                    raise RuntimeError(
                        "Could not reset disposable emulator package"
                    )
            install("candidate_clean_install", apk)
            launch_candidate("bootstrap_activity_launch")
            if api in {35, 36} and os.getenv("RUN_PROFILE_UI_TESTS") == "1":
                from profile_ui_probe import exercise

                debug_apk = (
                    Path(__file__).resolve().parents[2]
                    / "app/build/outputs/apk/debug/app-debug.apk"
                )
                install("debug_ui_fixture_install", debug_apk, update=True)
                record_profile_check(device, results, exercise)
            failed = False
            return results
        except Exception as original:
            classified = classify_frame_failure(original, adb, serial, process)
            if classified is not original:
                transport_lost = True
                raise classified from original
            raise
        finally:
            log.flush()
            _write_report(work / "install-results.json", results)
            if failed and not transport_lost:
                collect_graphics_diagnostics(device)
                collect_runtime_failure(device)
                collect_failure_diagnostics(device)
            elif failed:
                print(
                    "EMULATOR_TRANSPORT_DIAGNOSTICS=adb-unavailable;"
                    "full fresh-AVD attempt required",
                    flush=True,
                )
            try:
                identity = run(
                    [adb, "-s", serial, "emu", "avd", "name"],
                    timeout=10,
                )
                if (
                    identity.returncode == 0
                    and name in identity.stdout.splitlines()
                ):
                    run([adb, "-s", serial, "emu", "kill"], timeout=10)
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
            print(
                "EMULATOR_LOG_TAIL="
                + log_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )[-5000:],
                flush=True,
            )


def main() -> None:
    from artifact_test_identity import apk_digest

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
    canonical_report = work / "install-results.json"

    def execute(attempt: int) -> list[dict[str, object]]:
        attempt_work = _safe_attempt_directory(work, attempt)
        try:
            results = run_attempt(
                apk=apk,
                candidate_digest=candidate_digest,
                previous=previous,
                sdk=sdk,
                api=args.api,
                work=attempt_work,
                attempt=attempt,
            )
        except Exception:
            report = attempt_work / "install-results.json"
            if report.is_file():
                shutil.copyfile(report, canonical_report)
            raise
        _write_report(canonical_report, results)
        return results

    from isolated_adb import isolated_adb_server

    adb = sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    with isolated_adb_server(adb, work):
        run_with_transport_retry(execute)


if __name__ == "__main__":
    from emulator_lease import exclusive_emulator

    with exclusive_emulator():
        main()
