"""Build and check a secret-free console kit in the owner's project WSL."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import prepare_local_report_release as tested


def launcher_module():
    path = ROOT/"deploy/console_research/__main__.py"
    spec = importlib.util.spec_from_file_location("console_research", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive_members(reference):
    verifier = tested.validation
    verifier.require(hashlib.sha256(Path(verifier.__file__).read_bytes()).hexdigest() == tested.VALIDATOR_HASH,
                     "pinned_artifact_verifier_changed")
    verifier.BASE = tested.BASE
    verifier.MODULES = {"local_research.py", "osint_worker.py"}
    payload = verifier.verify_artifact(ROOT/"server-runtime-artifact.zip",
        archive_sha=tested.ARTIFACT, bundle_sha=tested.BUNDLE, source_sha=tested.SOURCE, run_id=tested.RUN)
    members = {"__main__.py": (ROOT/"deploy/console_research/__main__.py").read_bytes(),
               "server-runtime.json": payload}
    for name, blob in reference.GIT_BLOBS.items():
        data = (ROOT/"deploy"/name).read_bytes()
        verifier.require(reference.git_blob(data) == blob, "qualified_operations_changed")
        members[name] = data
    return members


def write_package(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in sorted(members.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 30, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def entrypoint(path, *args):
    return subprocess.run([sys.executable, "-I", str(path), *args], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=25)


def main():
    if os.environ.get("WSL_DISTRO_NAME") != "Ubuntu-24.04" or os.geteuid() == 0:
        raise RuntimeError("owner_unprivileged_wsl_required")
    verifier = launcher_module()
    members = archive_members(verifier)
    target = ROOT/"console-out"
    target.mkdir(exist_ok=False)
    path = target/"analyst-research-853090e.pyz"
    write_package(path, members)
    result = entrypoint(path, "--verify-only")
    if result.returncode or result.stdout.strip() != "CONSOLE_PACKAGE_VERIFIED=" + tested.SOURCE:
        raise RuntimeError("real_package_verify_entrypoint_failed")
    result = entrypoint(path)
    if result.returncode != 1 or result.stderr.strip() != "CONSOLE_RESEARCH_ERROR=root_console_required":
        raise RuntimeError("unprivileged_invocation_was_not_rejected")
    with tempfile.TemporaryDirectory() as temp:
        changed = Path(temp)/"altered.pyz"
        write_package(changed, {**members, "server-runtime.json": members["server-runtime.json"] + bytes([10])})
        result = entrypoint(changed, "--verify-only")
        if result.returncode != 1 or "changed_verified_runtime_bundle" not in result.stderr:
            raise RuntimeError("modified_payload_was_not_rejected")
    receipt = {"source": tested.SOURCE, "backend_test_run": tested.RUN,
               "bundle_sha256": tested.BUNDLE, "package_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "package_bytes": path.stat().st_size, "original_operations": verifier.GIT_BLOBS,
               "verified_entrypoint": True, "unprivileged_execution_rejected": True,
               "modified_payload_rejected": True, "contains_credentials": False,
               "production_invoked": False}
    (target/"verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("CONSOLE_KIT_VERIFIED=" + json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
