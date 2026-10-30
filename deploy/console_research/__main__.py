"""Run the same qualified research worker and rollback-capable backend release from an owner console."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import zipfile


SOURCE = "853090e11dcefef693366159c97316e55045c4c9"
BUNDLE_SHA = "4c45834b29bdedd6ccc3c7d120f133423e11b2d6c611b6c9e9d0d09b3debcc3c"
GIT_BLOBS = {
    "activate_local_research.py": "eb8c62e13e90253544e6e59bcb78548c8d5b736d",
    "gpt6_protocol_release.py": "613656222335b82f59bce27b224852323d92d06e",
    "local_report_route_release.py": "f4c0b1a2a2dfa18fef22415ee7f7a5f0d2321ef4",
}
BACKEND = Path("/opt/analyst-ai/backend")
HOSTNAME = "analyst-ai-runtime-20261025"


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def git_blob(data):
    prefix = b"blob " + str(len(data)).encode() + bytes([0])
    return hashlib.sha1(prefix + data).hexdigest()


def verified_payload(package):
    require(package.is_file() and not package.is_symlink() and package.stat().st_size <= 2 * 1024**2,
            "unexpected_console_package")
    with zipfile.ZipFile(package) as archive:
        entries = archive.infolist()
        expected = {"__main__.py", "server-runtime.json", *GIT_BLOBS}
        require(len(entries) == len(expected) and {e.filename for e in entries} == expected
                and sum(e.file_size for e in entries) <= 2 * 1024**2, "unexpected_package_members")
        for name, identity in GIT_BLOBS.items():
            require(git_blob(archive.read(name)) == identity, "changed_reviewed_module")
        data = archive.read("server-runtime.json")
    require(hashlib.sha256(data).hexdigest() == BUNDLE_SHA, "changed_verified_runtime_bundle")
    payload = json.loads(data)
    require(payload.get("source_commit") == SOURCE and payload.get("run_id") == "41088491538"
            and payload.get("apk_changed") is False
            and set(payload.get("files", {})) == {"local_research.py", "osint_worker.py"},
            "unexpected_runtime_bundle")
    return payload


@contextlib.contextmanager
def owner_lock():
    fd = os.open("/var/lock/analyst-console-research.lock",
                 os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, "rb") as lock:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and info.st_mode & 0o077 == 0, "unsafe_console_lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("another_console_install_is_active") from None
        yield


def verify_enabled(core, route, activation, payload):
    require(activation.regular(route.DROPIN) == route.SETTING, "different_existing_route")
    route.check_worker(json.loads(activation.regular(route.WORKER_RECEIPT, 65536)))
    require(core.systemctl("is-active", activation.SERVICE) == "active", "qualified_worker_inactive")
    for name, change in payload["files"].items():
        require(hashlib.sha256(core.read_regular(BACKEND/name)).hexdigest() == change["after"],
                "installed_source_differs")
    pid = core.systemctl("show", "analyst-ai-owner.service", "--property=MainPID", "--value")
    require(re.fullmatch("[1-9][0-9]*", pid), "owner_service_not_running")
    with Path("/proc", pid, "environ").open("rb") as stream:
        env = stream.read(1024**2 + 1)
    require(len(env) <= 1024**2 and [pair for pair in env.split(bytes([0]))
            if pair.startswith(b"LOCAL_RESEARCH_ENABLED=")] == [b"LOCAL_RESEARCH_ENABLED=true"],
            "research_route_not_effective")
    core.healthy()


def model_state(activation):
    result = subprocess.run(["/usr/bin/systemctl", "show", activation.SERVICE,
                             "--property=LoadState,ActiveState,FragmentPath"],
                            capture_output=True, text=True, timeout=15)
    require(result.returncode in {0, 4}, "local_service_state_unknown")
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if values.get("LoadState") == "not-found" and values.get("ActiveState") == "inactive":
        return "inactive"
    require(result.returncode == 0 and values.get("LoadState") == "loaded"
            and values.get("FragmentPath") == str(activation.UNIT), "different_existing_model_unit")
    return values.get("ActiveState")


def apply_to_guest(payload, core, activation, route):
    prepared = json.loads(activation.regular(activation.LOCAL/"preparation-receipt.json", 65536))
    require(prepared.get("server_id") == 9417611 and prepared.get("source_commit") == SOURCE
            and prepared.get("status") == "prepared", "wrong_prepared_guest")
    if route.DROPIN.exists() or route.DROPIN.is_symlink():
        verify_enabled(core, route, activation, payload)
        return "already_active"
    state = model_state(activation)
    if state == "active":
        # Never replace an already-running unproven process.
        route.check_worker(json.loads(activation.regular(route.WORKER_RECEIPT, 65536)))
    else:
        require(state in {"inactive", "failed"}, "model_service_is_transitioning")
        activation.activate({"payload": {"source_commit": SOURCE}})
    # The original release rechecks the model receipt, makes a private backup,
    # verifies the previous backend, and rolls both source and feature flag back.
    route.run({"run_id": str(time.time_ns()), "payload": payload})
    verify_enabled(core, route, activation, payload)
    return "active"


def main():
    require(sys.flags.isolated, "use_python3_isolated_mode")
    args = sys.argv[1:]
    require(args in ([], ["--verify-only"]), "unsupported_arguments")
    package = Path(sys.argv[0]).absolute()
    payload = verified_payload(package)
    if args == ["--verify-only"]:
        print("CONSOLE_PACKAGE_VERIFIED=" + SOURCE)
        return
    require(os.geteuid() == 0, "root_console_required")
    require(os.uname().nodename == HOSTNAME, "not_the_existing_timeweb_vm")
    info = package.stat()
    require(info.st_uid == 0 and info.st_mode & 0o022 == 0 and info.st_nlink == 1
            and package.resolve(strict=True) == package, "unsafe_console_package_owner")
    import activate_local_research as activation
    import gpt6_protocol_release as core
    import local_report_route_release as route
    with owner_lock():
        status = apply_to_guest(payload, core, activation, route)
    print("CONSOLE_RESEARCH_RESULT=" + json.dumps({"status": status, "source": SOURCE,
          "scope": "public_report_ingestion", "trade_permission": False}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        reason = str(error) if type(error) is RuntimeError and re.fullmatch("[a-z0-9_]{1,96}", str(error)) else type(error).__name__
        print("CONSOLE_RESEARCH_ERROR=" + reason, file=sys.stderr, flush=True)
        raise SystemExit(1) from None
