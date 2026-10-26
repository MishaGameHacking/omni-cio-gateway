"""Ordinary Android CI on the existing laptop; private evidence is exported last.

Candidate prepared by static review only. The source build and runtime entry
points must be exercised on Windows before this helper becomes an active gate.
No patch application, SDK installation, global process cleanup or publication.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import ctypes
from ctypes import wintypes
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import runpy
import shutil
import stat
import subprocess
import sys
import time
import traceback
import zipfile

REPOSITORY = "MishaGameHacking/omni-cio-gateway"
HOST = "LAPTOP-NPSGA016"
RUNNER_NAMES = ("actions-runner", "actions-runner-2", "actions-runner-3", "actions-runner-4")
CACHE = Path(r"C:\actions-runner-2\_work\_tool")
SDK = CACHE / "AndroidSdk/sdk"
JAVA = CACHE / "Java_Temurin-Hotspot_jdk/17.0.20-101/x64"
LEASE_BLOB = "c9626f3bf90b612a71b9bbf2954d0c134aa29b22"
WRAPPER_SHA256 = "238e777fcddd7e34f9708186085def2abd6e08e658505b38718d79d74c21abd5"
CERTIFICATE_SHA256 = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
BASELINE_SHA256 = "4e9bf0a2fd54d8ab4b9d49ef9ddf96bc14a274ac4c145585fcfdb88d6ae774b6"
BASELINE_BYTES = 29771254
MAX_ARCHIVE_BYTES = 512 * 1024**2
MAX_JSON_BYTES = 4 * 1024**2
SOURCE_FIELDS = ("repository", "event", "tested_merge_sha", "pr_head_sha", "pr_base_sha", "pr_number", "run_id")
PHASE_SECONDS = {"build": 10800, "runtime-prepare": 2400, "profile-16384": 7200, "profile-4096": 7200, "validate": 600}
APK_PATHS = (
    "app/build/outputs/apk/preview/app-preview.apk",
    "app/build/outputs/apk/debug/app-debug.apk",
    "ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk",
)
GRADLE_TASKS = (
    ":app:testDebugUnitTest", ":app:lintDebug", ":app:lintPreview",
    ":app:assembleDebug", ":app:assembleRelease", ":app:assemblePreview",
    ":ci-ui-driver:lintDebug", ":ci-ui-driver:assembleDebug",
)


def need(value, message):
    if not value:
        raise RuntimeError(message)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def git_blob(value):
    return hashlib.sha1(b"blob " + str(len(value)).encode() + b"\0" + value).hexdigest()


def checked(path, *, directory=False):
    """Check every ancestor: Windows junctions must not bypass a lexical allowlist."""
    path = Path(path)
    need(path.is_absolute(), "absolute_path_required")
    for current in (*reversed(path.parents), path):
        info = current.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "linked_or_reparse_path")
        final_file = current == path and not directory
        need((stat.S_ISREG if final_file else stat.S_ISDIR)(info.st_mode), "unexpected_path_type")
        if final_file:
            need(info.st_nlink == 1, "hardlinked_file")
    need(path.resolve(strict=True) == path, "noncanonical_path")
    return path.lstat()


def read_bytes(path, limit):
    before = checked(path)
    need(0 <= before.st_size <= limit, "input_size_invalid")
    with Path(path).open("rb") as source:
        opened = os.fstat(source.fileno())
        need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), "input_replaced_before_read")
        data = source.read(limit + 1)
        after = os.fstat(source.fileno())
    final = checked(path)
    identity = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns)
    need(len(data) == before.st_size and identity(before) == identity(after) == identity(final),
         "input_changed_during_read")
    return data


def file_identity(path, limit=MAX_ARCHIVE_BYTES):
    data = read_bytes(path, limit)
    return {"bytes": len(data), "sha256": sha_bytes(data)}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def read_json(path):
    def reject(value):
        raise ValueError("nonfinite_json_number")
    raw = read_bytes(path, MAX_JSON_BYTES)
    need(raw, "json_bytes_required")
    value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject)
    need(isinstance(value, dict), "json_object_required")
    return value


def save(path, value):
    checked(path.parent, directory=True)
    if path.exists() or path.is_symlink():
        checked(path)
    temporary = path.with_name(path.name + ".next")
    with temporary.open("xb") as output:
        output.write((json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8"))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def put_new(path, data):
    checked(path.parent, directory=True)
    with path.open("xb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    need(read_bytes(path, max(1, len(data))) == data, "saved_bytes_changed")


def output_values(values):
    target = os.environ.get("GITHUB_OUTPUT")
    need(target, "github_output_required")
    with open(target, "a", encoding="utf-8", newline="\n") as output:
        for key, value in values.items():
            text = str(value)
            need(re.fullmatch(r"[a-z_]+", key) and "\n" not in text and "\r" not in text,
                 "invalid_workflow_output")
            output.write(key + "=" + text + "\n")


def scalar_identity(env):
    run, attempt = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_RUN_ATTEMPT", "")
    need(re.fullmatch(r"[1-9]\d{0,19}", run) and re.fullmatch(r"[1-9]\d{0,4}", attempt), "invalid_run_identity")
    tested = env.get("GITHUB_SHA", "")
    head, base = env.get("CI_PR_HEAD_SHA", ""), env.get("CI_PR_BASE_SHA", "")
    need(all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (tested, head, base)), "invalid_source_identity")
    need(env.get("GITHUB_REPOSITORY") == REPOSITORY, "wrong_repository")
    event = env.get("GITHUB_EVENT_NAME")
    number = env.get("CI_PR_NUMBER", "")
    if event == "pull_request":
        need(env.get("CI_HEAD_REPOSITORY") == REPOSITORY and re.fullmatch(r"[1-9]\d{0,19}", number),
             "same_repository_pr_required")
    else:
        need(event in ("push", "workflow_dispatch") and env.get("GITHUB_REF") == "refs/heads/main",
             "unsupported_ci_event")
        need(head == base == tested and number == "", "non_pr_identity_mismatch")
    return {"repository": REPOSITORY, "event": event, "tested_merge_sha": tested,
            "pr_head_sha": head, "pr_base_sha": base, "pr_number": number,
            "run_id": run, "run_attempt": attempt}


def paths(role):
    need(__debug__ and sys.platform == "win32" and os.environ.get("COMPUTERNAME") == HOST,
         "wrong_execution_host")
    need(os.environ.get("RUNNER_OS") == "Windows" and os.environ.get("RUNNER_ARCH") == "X64",
         "wrong_runner_platform")
    need(sys.version_info[:3] == (3, 14, 6) and sys.maxsize > 2**32, "unexpected_python_runtime")
    need(role in ("build", "runtime", "publication"), "invalid_job_role")
    identity = scalar_identity(os.environ)
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    allowed = [Path("C:/") / runner / "_work/omni-cio-gateway/omni-cio-gateway" for runner in RUNNER_NAMES]
    need(workspace in allowed, "unexpected_runner_workspace")
    checked(workspace, directory=True)
    owned = workspace / f"android-ci-{role}-{identity['run_id']}-{identity['run_attempt']}"
    root = owned / "source"
    need(Path(os.environ["SOURCE_ROOT"]) == root and Path(__file__).resolve() == root / ".github/scripts/windows_android_ci.py",
         "wrong_owned_checkout")
    checked(root, directory=True)
    return root, owned / "state", owned / "handoff", identity


def source_identity(root, identity):
    def git(*arguments):
        value = subprocess.run(["git", *arguments], cwd=root, stdin=subprocess.DEVNULL,
                               capture_output=True, check=True, timeout=45).stdout
        need(len(value) <= MAX_JSON_BYTES, "git_result_too_large")
        return value
    need(git("rev-parse", "HEAD").decode().strip() == identity["tested_merge_sha"], "wrong_tested_merge_checkout")
    raw = git("cat-file", "-p", identity["tested_merge_sha"])
    parents = [line[7:].decode("ascii") for line in raw.split(b"\n\n", 1)[0].splitlines() if line.startswith(b"parent ")]
    if identity["event"] == "pull_request":
        need(parents == [identity["pr_base_sha"], identity["pr_head_sha"]], "tested_merge_parents_differ")
    # Check raw committed tree objects, not Git's stat cache. assume-unchanged
    # and skip-worktree must not hide modified test/application source bytes.
    need(not git("ls-files", "--others", "--exclude-standard", "-z"), "untracked_source_file")
    tree = {}
    for record in git("ls-tree", "-r", "-z", "--full-tree", identity["tested_merge_sha"]).split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        mode, kind, blob = header.split(b" ")
        need(mode in (b"100644", b"100755") and kind == b"blob" and re.fullmatch(rb"[a-f0-9]{40}", blob),
             "unsupported_committed_source_entry")
        need(name not in tree, "duplicate_committed_source_path")
        tree[name] = (mode, blob)
    index = {}
    for record in git("ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        mode, blob, stage = header.split(b" ")
        need(stage == b"0" and name not in index, "conflicted_or_duplicate_index")
        index[name] = (mode, blob)
    need(index == tree, "index_differs_from_tested_commit")
    files, digest = {}, hashlib.sha256()
    for name, (_, blob) in sorted(tree.items()):
        relative = name.decode("utf-8")
        pure = PurePosixPath(relative)
        need(not pure.is_absolute() and ".." not in pure.parts and "\\" not in relative and ":" not in relative,
             "unsafe_source_path")
        path = root / relative
        need(path.is_file(), "source_file_missing")
        data = read_bytes(path, MAX_ARCHIVE_BYTES)
        need(git_blob(data).encode("ascii") == blob, "source_bytes_differ_from_tested_commit")
        value = {"bytes": len(data), "sha256": sha_bytes(data), "git_blob": blob.decode("ascii")}
        files[relative] = value
        digest.update(name + b"\0" + value["sha256"].encode("ascii") + b"\0")
    need(files, "empty_source_inventory")
    return {"sha256": digest.hexdigest(), "files": files, "merge_parents": parents}


def test_environment(root, state):
    # Explicit Windows/test allowlist: no job/API tokens or production secrets.
    allowed = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP",
               "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES",
               "PROGRAMFILES(X86)", "COMMONPROGRAMFILES", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
               "COMPUTERNAME", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME", "RUNNER_TEMP",
               "GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA",
               "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKSPACE",
               "CI_PR_HEAD_SHA", "CI_PR_BASE_SHA", "CI_PR_NUMBER", "CI_HEAD_REPOSITORY", "SOURCE_ROOT",
               "CI_INPUT_ARCHIVE", "CI_INPUT_SHA256", "CI_INPUT_RECEIPT_SHA256", "CI_INPUT_ATTEMPT"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    home = Path(env["USERPROFILE"])
    checked(home, directory=True)
    need(home.name.lower() == "networkservice", "unexpected_service_profile")
    for target in (home / ".gradle", home / ".android"):
        checked(target, directory=True)
    for name, expected in (("GRADLE_USER_HOME", home / ".gradle"), ("ANDROID_USER_HOME", home / ".android"),
                           ("ANDROID_SDK_HOME", home)):
        if os.environ.get(name):
            need(Path(os.environ[name]).resolve(strict=True) == expected, "profile_override_changed")
    env.update(JAVA_HOME=str(JAVA), JAVA_HOME_17_X64=str(JAVA), ANDROID_SDK_ROOT=str(SDK), ANDROID_HOME=str(SDK),
               ANDROID_USER_HOME=str(home / ".android"), GRADLE_USER_HOME=str(home / ".gradle"),
               PATH=str(JAVA / "bin") + os.pathsep + env["PATH"], RUN_PROFILE_UI_TESTS="1",
               PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1", CI="true",
               PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK="1",
               TELEGRAM_CLIENT_ID="123456", TELEGRAM_CLIENT_SECRET="test-only", BACKEND_PUBLIC_URL="https://example.invalid",
               TELEGRAM_REDIRECT_URI="https://example.invalid/auth/telegram/callback",
               FERNET_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", DATABASE_PATH=str(state / "tests.sqlite3"),
               ANALYSIS_SCHEDULER_ENABLED="false", AI_EXTERNAL_PROCESSING_APPROVED="false",
               GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="core.autocrlf", GIT_CONFIG_VALUE_0="false",
               GIT_CONFIG_KEY_1="core.longpaths", GIT_CONFIG_VALUE_1="true")
    return env, home / ".android/debug.keystore"


class Steps:
    def __init__(self, root, state, phase, env):
        self.root, self.state, self.env = root, state, dict(env)
        self.env["GITHUB_WORKSPACE"] = str(root)
        self.path = state / (phase + "-steps.json")
        self.rows = []

    def run(self, label, args, timeout=1800, output=None):
        target = output or self.state / (f"{self.path.stem}-{len(self.rows) + 1:02d}-{label}.log")
        checked(target.parent, directory=True)
        row = {"label": label, "started_at": now(), "timeout_seconds": timeout, "log": str(target), "exit_code": None}
        self.rows.append(row)
        save(self.path, {"steps": self.rows})
        print("WINDOWS_ANDROID_STEP=" + json.dumps({"label": label, "status": "running"}), flush=True)
        try:
            with target.open("xb") as output_stream:
                process = subprocess.run([str(value) for value in args], cwd=self.root, env=self.env,
                                         stdin=subprocess.DEVNULL, stdout=output_stream, stderr=subprocess.STDOUT,
                                         timeout=timeout)
            row["exit_code"] = process.returncode
            need(process.returncode == 0, "step_failed:" + label)
        except BaseException as error:
            row["error_type"] = type(error).__name__
            raise
        finally:
            row["finished_at"] = now()
            if target.exists() and target.stat().st_size:
                row["log_identity"] = file_identity(target, 128 * 1024**2)
            save(self.path, {"steps": self.rows})
            print("WINDOWS_ANDROID_STEP=" + json.dumps({"label": label, "exit_code": row["exit_code"]}), flush=True)


def verify_machine(root, state, run):
    sys.path[:0] = [str(root / ".github/scripts"), str(root)]
    import verify_cached_jdk as jdk
    import prepare_android_sdk as sdk
    from backend.android_runtime_contract import required_sdk_packages
    need(jdk.discover(str(CACHE)) == JAVA, "unexpected_java_cache")
    jdk.verify(JAVA, run.env)
    checked(SDK, directory=True)
    for package in required_sdk_packages():
        sdk._verify_package(SDK, package)
    need(file_identity(root / "gradle/wrapper/gradle-wrapper.jar")["sha256"] == WRAPPER_SHA256,
         "gradle_wrapper_changed")
    key = Path(run.env["USERPROFILE"]) / ".android/debug.keystore"
    key_before = file_identity(key)
    certificate = state / (run.path.stem + "-certificate.der")
    run.run("signing-certificate", [JAVA / "bin/keytool.exe", "-exportcert", "-alias", "androiddebugkey",
                                   "-keystore", key, "-storepass", "android"], 30, output=certificate)
    need(file_identity(certificate)["sha256"] == CERTIFICATE_SHA256, "signing_certificate_changed")
    profile = state / (run.path.stem + "-java-profile.log")
    run.run("java-default-profile", [JAVA / "bin/java.exe", "-XshowSettings:properties", "-version"], 30, output=profile)
    homes = re.findall(r"^\s*user\.home\s*=\s*(.+?)\s*$", read_bytes(profile, MAX_JSON_BYTES).decode("utf-8", errors="replace"), re.MULTILINE)
    need(len(homes) == 1 and Path(homes[0]).resolve(strict=True) == key.parent.parent, "java_service_home_changed")
    class Memory(ctypes.Structure):
        _fields_ = [("Length", wintypes.DWORD), ("Load", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in ("TotalPhys", "AvailPhys", "TotalPageFile", "AvailPageFile",
                                                   "TotalVirtual", "AvailVirtual", "AvailExtendedVirtual")]
    memory = Memory()
    memory.Length = ctypes.sizeof(memory)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(Memory)]
    kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError(ctypes.get_last_error())
    need(memory.TotalPhys >= 3500 * 1024**2, "insufficient_physical_memory")
    need(shutil.disk_usage(root).free >= 7 * 1024**3, "insufficient_free_disk")
    return key, key_before


def new_venv(root, state, run):
    venv = state / "venv"
    need(not venv.exists(), "venv_already_exists")
    run.run("venv", [sys.executable, "-m", "venv", venv], 300)
    python = venv / "Scripts/python.exe"
    checked(python)
    run.run("test-requirements", [python, "-m", "pip", "--require-virtualenv", "install", "--no-input", "--no-cache-dir",
                                 "--index-url", "https://pypi.org/simple", "-r", root / "backend/requirements-dev.txt"], 900)
    run.run("native-tls", [python, "-m", "pip", "--require-virtualenv", "install", "--no-input", "--no-cache-dir",
                          "--index-url", "https://pypi.org/simple", "--require-hashes", "--only-binary=:all:",
                          "-r", root / "tools/timeweb-actions-requirements.txt"], 900)
    run.run("dependency-check", [python, "-m", "pip", "check"], 90)
    run.run("resolved-dependencies", [python, "-m", "pip", "freeze", "--all"], 60)
    return python


def static_apk(root, python, run):
    out = root / "app/build/outputs/apk/preview"
    apk = out / "app-preview.apk"
    bt = SDK / "build-tools/37.0.0"
    for name, command in (
        ("signature.txt", [JAVA / "bin/java.exe", "-jar", bt / "lib/apksigner.jar", "verify", "--verbose", "--print-certs", apk]),
        ("alignment.txt", [bt / "zipalign.exe", "-c", "-P", "16", "-v", "4", apk]),
        ("badging.txt", [bt / "aapt.exe", "dump", "badging", apk]),
        ("manifest.txt", [bt / "aapt.exe", "dump", "xmltree", apk, "AndroidManifest.xml"]),
    ):
        run.run("apk-" + name, command, 90, output=out / name)
    run.run("apk-verification", [python, ".github/scripts/verify_apk.py"], 120)


def build_worker(root, state, run):
    key, key_before = verify_machine(root, state, run)
    python = new_venv(root, state, run)
    try:
        for label, command in (
            ("diff-check", ["git", "diff", "--check"]),
            ("source-audit", [python, ".github/scripts/audit_python_sources.py"]),
            ("workspace-guards", [python, "-m", "unittest", "discover", "-s", "deploy/tests", "-p", "test_timeweb_workspace.py", "-v"]),
            ("host-tests", [python, "-m", "unittest", "discover", "-s", ".github/scripts/tests", "-p", "test_*.py", "-v"]),
            ("tools-tests", [python, "-m", "unittest", "discover", "-s", "tools/tests", "-p", "test_*.py", "-v"]),
        ):
            run.run(label, command)
        nodes = sorted(str(path.relative_to(root)) for path in (root / ".github/scripts").glob("*.test.cjs"))
        need(nodes, "node_tests_missing")
        run.run("node-tests", ["node", "--test", *nodes])
        run.run("gradle-version", [os.environ["COMSPEC"], "/d", "/c", root / "gradlew.bat", "--version"], 120)
        run.run("native-alignment-tests", [python, "tools/test_native_alignment.py"], 180)
        run.run("mesh-tests", [python, "tools/test_spectrum_meshes.py"], 180)
        run.run("gradle", [os.environ["COMSPEC"], "/d", "/c", root / "gradlew.bat", *GRADLE_TASKS,
                           "--no-daemon", "--parallel", "--max-workers=2", "--stacktrace"], 7200)
        run.run("mesh-apk-check", [python, "tools/generate_spectrum_meshes.py", "--check", "--check-apk"], 180)
        static_apk(root, python, run)
    finally:
        need(file_identity(key) == key_before, "signing_key_changed")
        run.run("release-owned-intermediates", [python, ".github/scripts/release_build_intermediates.py", "--allow-incomplete-build"], 300)


def baseline_identity(path):
    need(file_identity(path) == {"bytes": BASELINE_BYTES, "sha256": BASELINE_SHA256}, "published_baseline43_changed")


def archive_reference(value, run_id, build_attempt, current_attempt):
    need(re.fullmatch(r"[1-9]\d{0,4}", build_attempt) and int(build_attempt) <= int(current_attempt), "invalid_build_attempt")
    pure = PureWindowsPath(value)
    need(pure.is_absolute() and pure.drive.upper() == "C:" and len(pure.parts) == 8, "invalid_build_archive_path")
    need(pure.parts[1] in RUNNER_NAMES and pure.parts[2:5] == ("_work", "omni-cio-gateway", "omni-cio-gateway"),
         "build_archive_outside_allowed_runner")
    need(pure.parts[5:] == (f"android-ci-build-{run_id}-{build_attempt}", "handoff", "ci-apk-inputs.zip"),
         "build_archive_not_owned_by_this_run")
    need(str(pure) == value, "noncanonical_build_archive_text")
    return pure


def pack_inputs(root, state, handoff, identity):
    need(read_json(state / "build-controller.json").get("status") == "passed", "build_controller_not_successful")
    source = read_json(state / "source.json")
    need(source_identity(root, identity) == source, "source_changed_after_build")
    previous = Path(os.environ["PREVIOUS_APK"])
    baseline_identity(previous)
    for relative in APK_PATHS:
        checked(root / relative)
    sys.path.insert(0, str(root / "tools"))
    import ci_apk_archive
    data = ci_apk_archive.pack(root, previous)
    handoff.mkdir(exist_ok=False)
    archive = handoff / "ci-apk-inputs.zip"
    put_new(archive, data)
    receipt = {"schema": 1, "kind": "windows_android_ci_inputs", **identity,
               "host": HOST, "build_root": str(root), "source": source,
               "archive": file_identity(archive), "baseline": {"bytes": BASELINE_BYTES, "sha256": BASELINE_SHA256},
               "apks": {name: file_identity(root / name) for name in APK_PATHS},
               "build_controller": read_json(state / "build-controller.json"),
               "certificate_sha256": CERTIFICATE_SHA256, "created_at": now()}
    target = handoff / "build-handoff.json"
    save(target, receipt)
    output_values({"input_archive": str(archive), "input_sha256": receipt["archive"]["sha256"],
                   "input_receipt_sha256": file_identity(target)["sha256"], "input_attempt": identity["run_attempt"]})


def receive_inputs(root, state, identity):
    reference = archive_reference(os.environ.get("CI_INPUT_ARCHIVE", ""), identity["run_id"],
                                  os.environ.get("CI_INPUT_ATTEMPT", ""), identity["run_attempt"])
    archive = Path(str(reference))
    expected_archive, expected_receipt = os.environ.get("CI_INPUT_SHA256", ""), os.environ.get("CI_INPUT_RECEIPT_SHA256", "")
    need(all(re.fullmatch(r"[a-f0-9]{64}", value) for value in (expected_archive, expected_receipt)), "invalid_input_hash")
    receipt_path = archive.with_name("build-handoff.json")
    need(file_identity(receipt_path, MAX_JSON_BYTES)["sha256"] == expected_receipt, "build_receipt_changed")
    receipt = read_json(receipt_path)
    need(receipt.get("schema") == 1 and receipt.get("kind") == "windows_android_ci_inputs", "wrong_build_receipt")
    need(receipt.get("host") == HOST and receipt.get("run_attempt") == os.environ["CI_INPUT_ATTEMPT"], "wrong_build_host_or_attempt")
    need(all(receipt.get(key) == identity[key] for key in SOURCE_FIELDS), "build_source_or_run_mismatch")
    need(receipt.get("build_root") == str(archive.parent.parent / "source"), "build_root_receipt_mismatch")
    need(receipt.get("certificate_sha256") == CERTIFICATE_SHA256, "build_certificate_mismatch")
    controller = receipt.get("build_controller", {})
    need(controller.get("status") == "passed" and controller.get("owned_processes_after") == 0,
         "build_cleanup_not_verified")
    need(source_identity(root, identity) == receipt.get("source"), "runtime_source_differs_from_build")
    data = read_bytes(archive, MAX_ARCHIVE_BYTES)
    need(0 < len(data) <= MAX_ARCHIVE_BYTES and {"bytes": len(data), "sha256": sha_bytes(data)} == receipt.get("archive") and sha_bytes(data) == expected_archive,
         "build_archive_changed")
    destination = state / "ci-apk-inputs.zip"
    put_new(destination, data)
    save(state / "build-handoff.json", receipt)
    # Recheck the original receipt after reading the archive; its expected SHA is
    # a build-job output, not an assertion copied from the untrusted JSON itself.
    need(file_identity(receipt_path, MAX_JSON_BYTES)["sha256"] == expected_receipt, "build_receipt_changed_during_copy")
    return receipt


def runtime_prepare_worker(root, state, run, identity):
    receipt = receive_inputs(root, state, identity)
    key, key_before = verify_machine(root, state, run)
    python = new_venv(root, state, run)
    sys.path.insert(0, str(root / "tools"))
    import ci_apk_archive
    data = read_bytes(state / "ci-apk-inputs.zip", MAX_ARCHIVE_BYTES)
    need({"bytes": len(data), "sha256": sha_bytes(data)} == receipt["archive"], "local_input_archive_changed")
    for relative in ci_apk_archive.FILES:
        target = root / relative
        need(not target.exists() and not target.is_symlink(), "input_destination_already_exists")
        for parent in target.parents:
            if parent.exists():
                checked(parent, directory=True)
    ci_apk_archive.unpack(data, root)
    previous = root / ci_apk_archive.PREVIOUS_FILE
    baseline_identity(previous)
    os.replace(previous, state / "previous43.apk")
    require_runtime_inputs(root, state, identity)
    run.run("native-alignment-tests", [python, "tools/test_native_alignment.py"], 180)
    run.run("mesh-tests", [python, "tools/test_spectrum_meshes.py"], 180)
    run.run("mesh-apk-check", [python, "tools/generate_spectrum_meshes.py", "--check", "--check-apk"], 180)
    static_apk(root, python, run)
    need(file_identity(key) == key_before, "signing_key_changed_during_runtime_prepare")


def require_runtime_inputs(root, state, identity):
    receipt = read_json(state / "build-handoff.json")
    need(source_identity(root, identity) == receipt["source"], "runtime_source_changed")
    for relative in APK_PATHS:
        need(file_identity(root / relative) == receipt["apks"][relative], "runtime_apk_changed")
    baseline_identity(state / "previous43.apk")


def profile_worker(root, state, page, identity):
    require_runtime_inputs(root, state, identity)
    need(os.environ.get("RUN_PROFILE_UI_TESTS") == "1", "full_ui_required")
    work = root / "app/build/outputs/apk/preview" / f"install-api37-{page}"
    need(not work.exists(), "profile_directory_already_exists")
    sys.path[:0] = [str(root / ".github/scripts"), str(root)]
    sys.argv = [str(root / ".github/scripts/test_apk_installation.py"), "--sdk", str(SDK),
                "--apk", str(root / APK_PATHS[0]), "--previous", str(state / "previous43.apk"),
                "--api", "37", "--page-bytes", str(page), "--work-dir", str(work)]
    # __main__ acquires the unchanged canonical host lease itself. No focused
    # hook or monkeypatch is installed before executing the full native suite.
    runpy.run_path(sys.argv[0], run_name="__main__")
    require_runtime_inputs(root, state, identity)


def snapshot_ui(source, destination):
    """Retain the first profile without following a capture-tree junction."""
    checked(source, directory=True)
    for directory, dirs, names in os.walk(source, followlinks=False):
        current = Path(directory)
        checked(current, directory=True)
        for name in dirs:
            checked(current / name, directory=True)
        for name in names:
            checked(current / name)

    def copy_file(src, dst):
        put_new(Path(dst), read_bytes(Path(src), 128 * 1024**2))
        return str(dst)

    shutil.copytree(source, destination, copy_function=copy_file)


# Windows Job Object implementation copied byte-for-byte from the verified build bootstrap.
class OwnedJob:
    """Only the handshake-blocked worker and its descendants enter this OS job."""
    def __init__(self):
        class Limits(ctypes.Structure):
            _fields_=[("ProcessTime",ctypes.c_longlong),("JobTime",ctypes.c_longlong),("Flags",wintypes.DWORD),("MinWorking",ctypes.c_size_t),("MaxWorking",ctypes.c_size_t),("ActiveLimit",wintypes.DWORD),("Affinity",ctypes.c_size_t),("Priority",wintypes.DWORD),("Scheduling",wintypes.DWORD)]
        class IO(ctypes.Structure): _fields_=[(name,ctypes.c_ulonglong) for name in ("ReadOps","WriteOps","OtherOps","ReadBytes","WriteBytes","OtherBytes")]
        class Extended(ctypes.Structure): _fields_=[("Basic",Limits),("IO",IO),("ProcessMemory",ctypes.c_size_t),("JobMemory",ctypes.c_size_t),("PeakProcess",ctypes.c_size_t),("PeakJob",ctypes.c_size_t)]
        self.api=ctypes.WinDLL("kernel32",use_last_error=True)
        signatures={"CreateJobObjectW":([ctypes.c_void_p,wintypes.LPCWSTR],wintypes.HANDLE),"SetInformationJobObject":([wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD],wintypes.BOOL),"AssignProcessToJobObject":([wintypes.HANDLE,wintypes.HANDLE],wintypes.BOOL),"OpenProcess":([wintypes.DWORD,wintypes.BOOL,wintypes.DWORD],wintypes.HANDLE),"QueryInformationJobObject":([wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p],wintypes.BOOL),"TerminateJobObject":([wintypes.HANDLE,wintypes.UINT],wintypes.BOOL),"CloseHandle":([wintypes.HANDLE],wintypes.BOOL)}
        for name,(args,result) in signatures.items(): function=getattr(self.api,name); function.argtypes=args; function.restype=result
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        info=Extended(); info.Basic.Flags=0x2000
        if not self.api.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            error=ctypes.WinError(ctypes.get_last_error()); self.close(); raise error
    def attach(self,process):
        need(process.poll() is None,"worker_exited_before_job_assignment")
        handle=self.api.OpenProcess(0x0100|0x0001,False,process.pid)
        if not handle: raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle,handle): raise ctypes.WinError(ctypes.get_last_error())
        finally: self.api.CloseHandle(handle)
    def active(self):
        class Accounting(ctypes.Structure): _fields_=[("User",ctypes.c_longlong),("Kernel",ctypes.c_longlong),("PeriodUser",ctypes.c_longlong),("PeriodKernel",ctypes.c_longlong),("Faults",wintypes.DWORD),("Total",wintypes.DWORD),("Active",wintypes.DWORD),("Terminated",wintypes.DWORD)]
        info=Accounting()
        if not self.api.QueryInformationJobObject(self.handle,1,ctypes.byref(info),ctypes.sizeof(info),None): raise ctypes.WinError(ctypes.get_last_error())
        return info.Active
    def stop(self):
        if not self.api.TerminateJobObject(self.handle,1): raise ctypes.WinError(ctypes.get_last_error())
    def close(self):
        if self.handle:
            handle,self.handle=self.handle,None
            if not self.api.CloseHandle(handle): raise ctypes.WinError(ctypes.get_last_error())



def worker(root, state, phase, identity):
    env, _ = test_environment(root, state)
    run = Steps(root, state, phase, env)
    if phase == "build":
        build_worker(root, state, run)
    elif phase == "runtime-prepare":
        runtime_prepare_worker(root, state, run, identity)
    elif phase.startswith("profile-"):
        profile_worker(root, state, int(phase.split("-")[1]), identity)
    elif phase == "validate":
        require_runtime_inputs(root, state, identity)
        for page in (16384, 4096):
            need(read_json(state / f"profile-{page}-controller.json").get("status") == "passed", "runtime_profile_not_passed")
        run.run("distribution-validation", [state / "venv/Scripts/python.exe", ".github/scripts/validate_distribution.py"], 300)
        require_runtime_inputs(root, state, identity)
    else:
        raise RuntimeError("unexpected_worker_phase")


def control(root, state, phase, identity):
    first = phase in ("build", "runtime-prepare")
    if first:
        state.mkdir(exist_ok=False)
        env, _ = test_environment(root, state)
        # The fresh checkout has core.autocrlf=false. Attest every committed
        # source byte first; do not silently repair source in ordinary CI.
        source = source_identity(root, identity)
        save(state / "source.json", source)
        save(state / "identity.json", identity)
    else:
        checked(state, directory=True)
        need(read_json(state / "identity.json") == identity, "runtime_context_changed")
        need(source_identity(root, identity) == read_json(state / "source.json"), "source_changed_between_phases")
        env, _ = test_environment(root, state)
    lease_bytes = read_bytes(root / ".github/scripts/emulator_lease.py", MAX_JSON_BYTES)
    need(git_blob(lease_bytes) == LEASE_BLOB, "canonical_emulator_lease_changed")
    sys.path.insert(0, str(root / ".github/scripts"))
    import emulator_lease
    # The profile's __main__ owns the lease. Other heavy workers need the same
    # lease in this controller, released only after their process tree is empty.
    lease_context = nullcontext() if phase.startswith("profile-") else emulator_lease.exclusive_emulator()
    record = {"phase": phase, **identity, "host": HOST, "started_at": now(), "status": "running",
              "worker_started": False, "owned_processes_after": None, "publication_authorized": False}
    destination = state / (phase + "-controller.json")
    need(not destination.exists(), "controller_phase_already_recorded")
    save(destination, record)
    job = process = None
    error = None
    try:
        with lease_context:
            job = OwnedJob()
            try:
                python = state / "venv/Scripts/python.exe" if phase.startswith("profile-") else Path(sys.executable)
                args = [str(python), str(Path(__file__).resolve()), "worker", "--phase", phase]
                with (state / (phase + "-worker.log")).open("xb") as log:
                    process = subprocess.Popen(args, cwd=root, env=env, stdin=subprocess.PIPE, stdout=log,
                                               stderr=subprocess.STDOUT, close_fds=True)
                    job.attach(process)
                    record.update(worker_started=True, worker_pid=process.pid)
                    process.stdin.write(b"WINDOWS_OWNED_JOB_READY\n")
                    process.stdin.close()
                    deadline = time.monotonic() + PHASE_SECONDS[phase]
                    while process.poll() is None:
                        remaining = deadline - time.monotonic()
                        need(remaining > 0, "owned_worker_deadline_exceeded")
                        try:
                            process.wait(timeout=min(30, remaining))
                        except subprocess.TimeoutExpired:
                            print("WINDOWS_ANDROID_PROGRESS=" + json.dumps({"phase": phase, "running": True}), flush=True)
                    record["worker_exit_code"] = process.returncode
                    need(process.returncode == 0, "owned_worker_failed")
            finally:
                try:
                    if job is not None:
                        try:
                            if job.active():
                                job.stop()
                            end = time.monotonic() + 30
                            while job.active() and time.monotonic() < end:
                                time.sleep(0.2)
                            record["owned_processes_after"] = job.active()
                            need(record["owned_processes_after"] == 0, "owned_processes_remain")
                        finally:
                            job.close()
                finally:
                    if process is not None and process.poll() is None:
                        process.kill()
                        process.wait(timeout=15)
    except BaseException as failure:
        error = failure
        record.update(status="failed", error_type=type(failure).__name__, error=str(failure)[:500])
    finally:
        try:
            if phase == "profile-16384":
                base = root / "app/build/outputs/apk/preview"
                if (base / "ui-screens").exists():
                    snapshot_ui(base / "ui-screens", base / "ui-screens-api37-16384")
            need(source_identity(root, identity) == read_json(state / "source.json"), "sources_changed_during_worker")
            if not first:
                require_runtime_inputs(root, state, identity)
            if error is None:
                record["status"] = "passed"
        except BaseException as failure:
            if error is None:
                error = failure
            record.update(status="failed", final_integrity_error=type(failure).__name__)
        record["finished_at"] = now()
        save(destination, record)
        print("WINDOWS_ANDROID_CONTROLLER=" + json.dumps(record, sort_keys=True), flush=True)
    if error is not None:
        raise error


def export_evidence(root, state, handoff, identity):
    checked(state, directory=True)
    need(read_json(state / "identity.json") == identity, "export_context_mismatch")
    need(source_identity(root, identity) == read_json(state / "source.json"), "source_changed_before_export")
    for path in state.glob("*-controller.json"):
        controller = read_json(path)
        need(controller.get("owned_processes_after") == 0 or controller.get("worker_started") is False,
             "worker_cleanup_missing_before_export")
    entries = {}
    def add(relative, file):
        need(relative not in entries, "duplicate_evidence_path")
        entries[relative] = (file, file_identity(file, 128 * 1024**2))
    def tree(prefix, folder, suffixes):
        if not folder.exists():
            return
        checked(folder, directory=True)
        for directory, dirs, names in os.walk(folder, followlinks=False):
            current = Path(directory)
            checked(current, directory=True)
            dirs[:] = [name for name in dirs if name not in {"venv", "avd", ".android", "android-home", "android-user-home"}]
            for name in names:
                path = current / name
                if path.suffix.lower() in suffixes and path.stat().st_size:
                    add(prefix + "/" + path.relative_to(folder).as_posix(), path)
    formats = {".json", ".log", ".txt", ".xml", ".png"}
    tree("runtime/controller", state, formats)
    tree("runtime/preview", root / "app/build/outputs/apk/preview", formats)
    receipt = read_json(state / "build-handoff.json") if (state / "build-handoff.json").exists() else None
    if receipt is not None:
        build_root = Path(receipt["build_root"])
        # This path was already bound to the exact allowed source run by receive_inputs.
        archive_reference(str(build_root.parent / "handoff/ci-apk-inputs.zip"), identity["run_id"],
                          receipt["run_attempt"], identity["run_attempt"])
        need(all(receipt[key] == identity[key] for key in SOURCE_FIELDS), "export_build_identity_changed")
        tree("build/controller", build_root.parent / "state", formats)
        for relative in ("app/build/reports", "app/build/test-results", "ci-ui-driver/build/reports", "ci-ui-driver/build/test-results"):
            tree("build/" + relative, build_root / relative, formats | {".html", ".css", ".js", ".sarif"})
        add("inputs/ci-apk-inputs.zip", state / "ci-apk-inputs.zip")
    source = read_json(state / "source.json")
    for relative, expected in source["files"].items():
        path = root / relative
        actual = file_identity(path)
        need(actual == {key: expected[key] for key in ("bytes", "sha256")}, "source_changed_during_export")
        add("source/" + relative, path)
    need(sum(value[1]["bytes"] for value in entries.values()) < 490 * 1024**2, "evidence_total_size_limit")
    validation = state / "validate-controller.json"
    accepted = validation.exists() and read_json(validation).get("status") == "passed"
    envelope = {"schema": 1, "kind": "windows_android_ci_evidence", **identity, "host": HOST,
                "source_sha256": source["sha256"], "runtime_full_matrix_passed": accepted,
                "publication_authorized": False, "phone_verified": False, "created_at": now(),
                "files": {name: value[1] for name, value in entries.items()}}
    handoff.mkdir(exist_ok=False)
    archive = handoff / "android-evidence.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as target:
        for name, (path, expected) in sorted(entries.items()):
            data = read_bytes(path, 128 * 1024**2)
            need({"bytes": len(data), "sha256": sha_bytes(data)} == expected, "evidence_changed_during_export")
            target.writestr(name, data)
        target.writestr("android-ci-envelope.json", json.dumps(envelope, sort_keys=True))
    data = read_bytes(archive, MAX_ARCHIVE_BYTES)
    temporary = Path(os.environ["RUNNER_TEMP"]) / "ci-handoff.zip"
    put_new(temporary, data)
    receipt = {"schema": 1, "kind": "windows_android_ci_export", **identity, "runtime_root": str(root),
               "bytes": len(data), "sha256": sha_bytes(data), "files": len(entries), "full_matrix_passed": accepted,
               "source_sha256": source["sha256"]}
    save(handoff / "export-receipt.json", receipt)
    output_values({"runtime_root": str(root), "runtime_attempt": identity["run_attempt"],
                   "runtime_receipt_sha256": file_identity(handoff / "export-receipt.json")["sha256"]})
    print("WINDOWS_ANDROID_EVIDENCE=" + json.dumps(receipt), flush=True)


def runtime_reference(value, run_id, runtime_attempt, current_attempt):
    need(re.fullmatch(r"[1-9]\d{0,4}", runtime_attempt) and int(runtime_attempt) <= int(current_attempt),
         "invalid_runtime_attempt")
    pure = PureWindowsPath(value)
    need(pure.is_absolute() and pure.drive.upper() == "C:" and len(pure.parts) == 7, "invalid_runtime_root")
    need(pure.parts[1] in RUNNER_NAMES and pure.parts[2:5] == ("_work", "omni-cio-gateway", "omni-cio-gateway"),
         "runtime_outside_allowed_runner")
    need(pure.parts[5:] == (f"android-ci-runtime-{run_id}-{runtime_attempt}", "source") and str(pure) == value,
         "runtime_root_not_owned_by_run")
    return pure


def inspect_retained(root, identity):
    """Re-attest retained bytes before API-only release/private-retention steps."""
    expected_attempt = os.environ.get("CI_RUNTIME_ATTEMPT", "")
    pure = runtime_reference(os.environ.get("CI_RUNTIME_ROOT", ""), identity["run_id"], expected_attempt,
                             identity["run_attempt"])
    retained = Path(str(pure))
    checked(retained, directory=True)
    handoff, state = retained.parent / "handoff", retained.parent / "state"
    expected_receipt = os.environ.get("CI_RUNTIME_RECEIPT_SHA256", "")
    expected_archive = os.environ.get("CI_EVIDENCE_SHA256", "")
    need(all(re.fullmatch(r"[a-f0-9]{64}", value) for value in (expected_receipt, expected_archive)),
         "retained_evidence_hash_required")
    receipt_path = handoff / "export-receipt.json"
    need(file_identity(receipt_path, MAX_JSON_BYTES)["sha256"] == expected_receipt, "retained_export_receipt_changed")
    receipt = read_json(receipt_path)
    need(receipt.get("schema") == 1 and receipt.get("kind") == "windows_android_ci_export" and
         receipt.get("full_matrix_passed") is True and receipt.get("runtime_root") == str(retained) and
         receipt.get("run_attempt") == expected_attempt, "retained_export_not_accepted")
    need(all(receipt.get(key) == identity[key] for key in SOURCE_FIELDS), "retained_source_or_run_mismatch")
    archive = handoff / "android-evidence.zip"
    need(file_identity(archive) == {"bytes": receipt["bytes"], "sha256": expected_archive} and
         receipt["sha256"] == expected_archive, "retained_evidence_archive_changed")
    with zipfile.ZipFile(archive) as source:
        entry = source.getinfo("android-ci-envelope.json")
        need(0 < entry.file_size <= MAX_JSON_BYTES and
             sum(item.filename == entry.filename for item in source.infolist()) == 1, "invalid_retained_envelope")
        envelope = json.loads(source.read(entry), object_pairs_hook=unique_object)
    need(envelope.get("runtime_full_matrix_passed") is True and envelope.get("run_attempt") == expected_attempt and
         all(envelope.get(key) == identity[key] for key in SOURCE_FIELDS), "retained_envelope_identity_mismatch")
    # Verify every runtime controller/report/capture against the uploaded archive
    # manifest before trusting its earlier validation result. A substituted local
    # success flag cannot recreate this expected archive SHA.
    for name, expected in envelope["files"].items():
        if name.startswith("runtime/controller/"):
            relative, parent = name[len("runtime/controller/"):], state
        elif name.startswith("runtime/preview/"):
            relative, parent = name[len("runtime/preview/"):], retained / "app/build/outputs/apk/preview"
        else:
            continue
        pure_name = PurePosixPath(relative)
        need(relative and not pure_name.is_absolute() and ".." not in pure_name.parts and "\\" not in relative and ":" not in relative,
             "unsafe_retained_evidence_path")
        need(file_identity(parent / relative, 128 * 1024**2) == expected, "retained_runtime_evidence_changed")
    retained_identity = read_json(state / "identity.json")
    need(retained_identity["run_attempt"] == expected_attempt and
         all(retained_identity[key] == identity[key] for key in SOURCE_FIELDS), "retained_identity_changed")
    expected_source = source_identity(root, identity)
    need(source_identity(retained, retained_identity) == expected_source and receipt["source_sha256"] == expected_source["sha256"],
         "retained_source_differs_from_current_merge")
    require_runtime_inputs(retained, state, retained_identity)
    for phase in ("runtime-prepare", "profile-16384", "profile-4096", "validate"):
        controller = read_json(state / (phase + "-controller.json"))
        need(controller.get("status") == "passed" and controller.get("owned_processes_after") == 0,
             "retained_runtime_phase_not_accepted")
    report = read_json(retained / "app/build/outputs/apk/preview/apk-verification.json")
    need(report.get("certificate_sha256") == CERTIFICATE_SHA256 and
         report.get("device_install_test") == "passed_on_emulators_not_a_physical_phone" and
         report.get("sha256") == file_identity(retained / APK_PATHS[0])["sha256"], "retained_apk_report_mismatch")
    need(file_identity(receipt_path, MAX_JSON_BYTES)["sha256"] == expected_receipt, "retained_receipt_changed_during_check")
    output_values({"retained_root": str(retained)})
    print("WINDOWS_ANDROID_RETAINED_INPUTS=" + json.dumps({"runtime_root": str(retained),
          "tested_merge_sha": identity["tested_merge_sha"], "pr_head_sha": identity["pr_head_sha"],
          "archive_sha256": expected_archive, "source_sha256": expected_source["sha256"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "pack", "runtime-prepare", "profile-16384", "profile-4096", "validate", "export", "inspect-retained", "worker"))
    parser.add_argument("--phase", choices=tuple(PHASE_SECONDS))
    args = parser.parse_args()
    phase = args.phase if args.command == "worker" else args.command
    need(phase is not None, "worker_phase_required")
    role = "publication" if phase == "inspect-retained" else "build" if phase in ("build", "pack") else "runtime"
    root, state, handoff, identity = paths(role)
    if args.command == "worker":
        need(sys.stdin.buffer.readline(64) == b"WINDOWS_OWNED_JOB_READY\n", "worker_job_handshake_missing")
        try:
            worker(root, state, phase, identity)
        except BaseException:
            with (state / (phase + "-failure.log")).open("w", encoding="utf-8") as output:
                traceback.print_exc(file=output)
            raise
    elif args.command == "pack":
        need(git_blob(read_bytes(root / ".github/scripts/emulator_lease.py", MAX_JSON_BYTES)) == LEASE_BLOB,
             "canonical_emulator_lease_changed")
        sys.path.insert(0, str(root / ".github/scripts"))
        import emulator_lease
        with emulator_lease.exclusive_emulator():
            pack_inputs(root, state, handoff, identity)
    elif args.command == "export":
        export_evidence(root, state, handoff, identity)
    elif args.command == "inspect-retained":
        inspect_retained(root, identity)
    else:
        control(root, state, phase, identity)


if __name__ == "__main__":
    main()
