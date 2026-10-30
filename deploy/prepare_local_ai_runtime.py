"""Stage pinned public source and local weights without starting a model or app.

No broker/API model credentials, database access, service restart or OS reinstall.
The Timeweb host stays unchanged in size; activation is a separate gated step.
"""
from datetime import datetime, timezone
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

SOURCE = "853090e11dcefef693366159c97316e55045c4c9"
REPOSITORY = "https://github.com/MishaGameHacking/omni-cio-gateway.git"
MODEL_ID = "litert-community/gemma-4-E4B-it-litert-lm"
REVISION = "e6a3892a8c22cf87ff99583996149cf3cb32452b"
MODEL_SHA = "0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0"
MODEL_BYTES = 3659530240
WHEEL_SHA = "b2fe9b9a87afe991a7b0d29615b0bfc3d41c7a0ac28e9c54436676482bca2e5b"
LOCAL = Path("/opt/analyst-local-ai")
SOURCES = Path("/opt/analyst-source")
FILES = {
    "backend/local_research.py": "13560fbce8557673d892cacc1a5f447c7f4255e4abbbc131b0259be33e7c284c",
    "deploy/local_research_worker.py": "73b0b2d488b2306ef9e4631bca019f8a966077b6674b08ef0734f2409f94f972",
    "deploy/analyst-local-research.service": "9161820a769464b667edd39d1bfd358f24dc34bef1cea56f7e92f2ab7a112f97",
}
PHASE = "validate"


def need(value, code):
    if not value:
        raise ValueError(code)


def directory(path):
    need(path.is_dir() and not path.is_symlink() and path.resolve(strict=True) == path,
         "unsafe_directory")
    info = path.stat()
    need(info.st_uid == os.getuid() and info.st_mode & 0o022 == 0, "unsafe_directory_owner")


def regular(path, limit):
    need(path.is_file() and not path.is_symlink() and path.resolve(strict=True) == path,
         "unsafe_file")
    info = path.stat()
    need(info.st_uid == os.getuid() and info.st_nlink == 1 and info.st_mode & 0o022 == 0
         and 0 <= info.st_size <= limit, "unsafe_file_metadata")
    return path.read_bytes()


def mkdir(path):
    directory(path.parent)
    if not path.exists() and not path.is_symlink():
        path.mkdir(mode=0o755)
    directory(path)


def digest_file(path):
    result = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024**2), b""):
            result.update(chunk)
    return result.hexdigest()


def command(arguments, *, cwd=None, timeout=90, run=subprocess.run):
    # Do not pass SSH/session or application environment to package managers.
    environment = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8",
        "DEBIAN_FRONTEND": "noninteractive", "NEEDRESTART_MODE": "l",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0", "PYTHONNOUSERSITE": "1"}
    result = run(arguments, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                 capture_output=True, timeout=timeout)
    need(result.returncode == 0, "preparation_command_failed")
    need(len(result.stdout) <= 2 * 1024**2, "preparation_output_limit")
    return result.stdout.decode("utf-8", errors="replace").strip()


def prerequisites():
    packages = []
    for library, package in (("c++", "libc++1"), ("c++abi", "libc++abi1"), ("atomic", "libatomic1")):
        if ctypes.util.find_library(library) is None:
            packages.append(package)
    if shutil.which("git") is None:
        packages.append("git")
    if packages:
        command(["/usr/bin/apt-get", "update", "-qq"], timeout=90)
        command(["/usr/bin/apt-get", "install", "--no-install-recommends", "-y", *packages], timeout=150)
    need(all(ctypes.util.find_library(name) is not None for name in ("c++", "c++abi", "atomic")),
         "native_libraries_missing")
    return packages


def checkout_source():
    mkdir(SOURCES)
    target = SOURCES / SOURCE
    mkdir(target)
    git = ["/usr/bin/git", "-c", "credential.helper=", "-c", "http.extraHeader=",
           "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never"]
    if not (target / ".git").exists():
        command([*git, "init", "--quiet"], cwd=target)
        command([*git, "remote", "add", "origin", REPOSITORY], cwd=target)
    directory(target / ".git")
    need(command([*git, "remote", "get-url", "origin"], cwd=target) == REPOSITORY,
         "source_remote_changed")
    command([*git, "fetch", "--no-tags", "--depth=1", "origin", SOURCE], cwd=target, timeout=120)
    entries = command([*git, "ls-tree", "-r", "--format=%(objectmode)", SOURCE], cwd=target)
    need(entries and len(entries.splitlines()) <= 20000
         and set(entries.splitlines()) <= {"100644", "100755"}, "source_tree_types_invalid")
    command([*git, "checkout", "--detach", "--quiet", SOURCE], cwd=target)
    need(command([*git, "rev-parse", "HEAD"], cwd=target) == SOURCE, "source_revision_mismatch")
    need(command([*git, "status", "--porcelain", "--untracked-files=all"], cwd=target) == "",
         "source_tree_dirty")
    for name, checksum in FILES.items():
        need(hashlib.sha256(regular(target / name, 512 * 1024)).hexdigest() == checksum,
             "source_file_checksum_mismatch")
    return target


def download_model(open_url=urllib.request.urlopen):
    model = LOCAL / "model.litertlm"
    if model.exists() or model.is_symlink():
        need(model.is_file() and not model.is_symlink() and model.stat().st_uid == os.getuid()
             and model.stat().st_nlink == 1 and model.stat().st_mode & 0o022 == 0
             and model.stat().st_size == MODEL_BYTES,
             "model_existing_file_invalid")
        need(digest_file(model) == MODEL_SHA, "model_checksum_mismatch")
        return
    partial = LOCAL / "model.partial"
    need(not partial.exists() and not partial.is_symlink(), "model_partial_already_present")
    url = "https://huggingface.co/" + MODEL_ID + "/resolve/" + REVISION + "/gemma-4-E4B-it.litertlm"
    deadline = time.monotonic() + 240
    try:
        with open_url(urllib.request.Request(url, headers={"Accept-Encoding": "identity"}), timeout=30) as response:
            need(urllib.parse.urlsplit(response.geturl()).scheme == "https", "insecure_model_redirect")
            with partial.open("xb") as output:
                size = 0
                while chunk := response.read(1024**2):
                    size += len(chunk)
                    need(size <= MODEL_BYTES and time.monotonic() <= deadline, "model_download_bound")
                    output.write(chunk)
        need(size == MODEL_BYTES and digest_file(partial) == MODEL_SHA, "model_checksum_mismatch")
        partial.chmod(0o644)
        partial.replace(model)
    finally:
        partial.unlink(missing_ok=True)


def install_runtime():
    venv = LOCAL / "venv"
    if not venv.exists() and not venv.is_symlink():
        command(["/usr/bin/python3", "-m", "venv", str(venv)], timeout=60)
    directory(venv)
    requirements = LOCAL / "requirements-pinned.txt"
    content = "litert-lm-api==0.18.1 --hash=sha256:" + WHEEL_SHA + "\n"
    if requirements.exists() or requirements.is_symlink():
        need(regular(requirements, 1024).decode() == content, "runtime_requirements_changed")
    else:
        with requirements.open("x") as output:
            output.write(content)
    python = str(venv / "bin/python")
    command([python, "-m", "pip", "install", "--require-hashes", "--only-binary=:all:",
             "--disable-pip-version-check", "-r", str(requirements)], timeout=120)
    version = command([python, "-I", "-c", "from importlib.metadata import version; print(version('litert-lm-api'))"])
    need(version == "0.18.1", "runtime_version_mismatch")


def stage_files(source):
    for relative, checksum in FILES.items():
        destination = LOCAL / relative
        mkdir(destination.parent)
        raw = regular(source / relative, 512 * 1024)
        need(hashlib.sha256(raw).hexdigest() == checksum, "stage_source_changed")
        if destination.exists() or destination.is_symlink():
            need(regular(destination, 512 * 1024) == raw, "stage_file_changed")
        else:
            with destination.open("xb") as output:
                output.write(raw)
            destination.chmod(0o644)


def run(envelope):
    global PHASE
    need(os.getuid() == 0 and envelope.get("payload") == {"source_commit": SOURCE},
         "preparation_scope_invalid")
    need(len(FILES) == 3, "source_manifest_unset")
    directory(Path("/opt"))
    need(shutil.disk_usage("/opt").free >= 12 * 1024**3, "preparation_disk_headroom_insufficient")
    need(not Path("/etc/systemd/system/analyst-local-research.service").exists(), "service_already_installed")
    mkdir(LOCAL)
    PHASE = "dependencies"
    packages = prerequisites()
    PHASE = "sources"
    source = checkout_source()
    PHASE = "files"
    stage_files(source)
    PHASE = "weights"
    download_model()
    PHASE = "runtime"
    install_runtime()
    PHASE = "receipt"
    receipt = {"status": "prepared", "observed_at": datetime.now(timezone.utc).isoformat(),
        "server_id": 9417611, "source_commit": SOURCE, "source_directory": str(source),
        "model_sha256": MODEL_SHA, "model_bytes": MODEL_BYTES, "runtime_version": "0.18.1",
        "runtime_wheel_sha256": WHEEL_SHA, "installed_system_packages": packages,
        "model_started": False, "service_enabled": False, "application_changed": False,
        "configuration_read": False, "database_read": False, "broker_called": False,
        "paid_inference_called": False, "resources_resized": False}
    target = LOCAL / "preparation-receipt.json"
    if target.exists() or target.is_symlink():
        regular(target, 65536)
    target.write_text(json.dumps(receipt, indent=2) + "\n")
    print("LOCAL_AI_PREPARED=" + json.dumps(receipt), flush=True)


if __name__ == "__main__":
    try:
        run(ENVELOPE)
    except Exception as error:
        allowed = {"preparation_scope_invalid", "source_manifest_unset", "preparation_disk_headroom_insufficient",
                   "native_libraries_missing", "source_revision_mismatch", "source_tree_types_invalid",
                   "model_checksum_mismatch", "model_download_bound", "runtime_version_mismatch"}
        code = str(error) if type(error) is ValueError and str(error) in allowed else "local_ai_preparation_failed"
        print(json.dumps({"status": "failed", "code": code, "model_started": False,
                          "phase": PHASE, "service_enabled": False, "broker_called": False}), flush=True)
        raise SystemExit(1) from None
