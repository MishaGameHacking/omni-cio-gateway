"""Measure one pinned E4B candidate against the unchanged AF51 selector suite.

Owner WSL only, synthetic documents only. No Timeweb or broker connections.
The reference checkout is pinned by the workflow; this adapter never changes it.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
SOURCE_SHA = "af51ba32a85683419087760cf2b549176d7d58e5"
MODEL_ID = "litert-community/gemma-4-E4B-it-litert-lm"
REVISION = "e6a3892a8c22cf87ff99583996149cf3cb32452b"
MODEL_SHA = "0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0"
MODEL_BYTES = 3659530240
SELECTOR_SHA = "4bcc429dee99740c29cdfe773e6f7b53e5bffe10cc50ced8c6fb899ce2a233db"
RUNTIME_SHA = "b2fe9b9a87afe991a7b0d29615b0bfc3d41c7a0ac28e9c54436676482bca2e5b"
CACHE = Path("/home/analyst-ci/.cache/analyst-local-research")
MODEL = CACHE / (MODEL_SHA + ".litertlm")
MIB = 1024 * 1024


def baseline():
    sys.path.insert(0, str(SOURCE / "tools"))
    spec = importlib.util.spec_from_file_location("e4b_reference", SOURCE / "tools/evaluate_local_research.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.contract.SELECTOR_SHA256 != SELECTOR_SHA or len(module.CASES) != 12:
        raise ValueError("reference_contract_changed")
    module.contract.MODEL_ID = MODEL_ID
    module.contract.MODEL_REVISION = REVISION
    module.contract.MODEL_SHA256 = MODEL_SHA
    # MODEL_QUALIFIED remains False; a measurement cannot enable the application.
    module.MODEL_FILE = MODEL
    module.ENGINE_CACHE = CACHE / ("engine-" + MODEL_SHA[:16])
    return module


def mem_available():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise ValueError("host_memory_unknown")


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(MIB), b""):
            result.update(block)
    return result.hexdigest()


def download():
    if MODEL.is_file() and MODEL.stat().st_size == MODEL_BYTES and sha(MODEL) == MODEL_SHA:
        return
    temporary = MODEL.with_suffix(".partial")
    try:
        url = "https://huggingface.co/" + MODEL_ID + "/resolve/" + REVISION + "/gemma-4-E4B-it.litertlm"
        with urllib.request.urlopen(url, timeout=40) as response, temporary.open("wb") as output:
            size = 0
            while block := response.read(MIB):
                size += len(block)
                if size > MODEL_BYTES:
                    raise ValueError("model_size_exceeded")
                output.write(block)
        if size != MODEL_BYTES or sha(temporary) != MODEL_SHA:
            raise ValueError("model_checksum_mismatch")
        temporary.replace(MODEL)
    finally:
        temporary.unlink(missing_ok=True)


def child():
    # Mapping budget and CPU limit apply before native model initialization.
    resource.setrlimit(resource.RLIMIT_AS, (12 * 1024 * MIB, 12 * 1024 * MIB))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    baseline().evaluate_child()


def supervise(python, folder, report):
    output = folder / "result.jsonl"
    reason = None
    with output.open("wb") as stream:
        process = subprocess.Popen([python, "-I", str(Path(__file__).resolve()), "--evaluate"],
                                   stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.DEVNULL)
        start = time.monotonic()
        try:
            while process.poll() is None:
                try:
                    status = Path(f"/proc/{process.pid}/status").read_text()
                    rss = next((int(line.split()[1]) * 1024 for line in status.splitlines()
                                if line.startswith("VmRSS:")), 0)
                except (FileNotFoundError, ProcessLookupError):
                    continue
                if rss > 6144 * MIB:
                    reason = "evaluation_rss_limit"
                elif mem_available() < 512 * MIB:
                    reason = "host_memory_pressure"
                elif time.monotonic() - start > 240:
                    reason = "evaluation_time_limit"
                elif output.stat().st_size > 128 * 1024:
                    reason = "evaluation_output_limit"
                if reason:
                    process.kill()
                    break
                time.sleep(0.1)
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    if reason:
        report["reason"] = reason
        return
    if output.stat().st_size > 128 * 1024:
        report["reason"] = "evaluation_output_limit"
        return
    lines = output.read_text(errors="replace").splitlines()
    result = json.loads(lines[-1]) if lines else {}
    if process.returncode or not isinstance(result, dict) or "peak_rss_mib" not in result:
        report.update(reason="local_evaluation_failed", exit_code=process.returncode)
        if isinstance(result, dict) and set(result) == {"failure"}:
            report["diagnostic"] = result["failure"]
        return
    report.update(result)
    peak = result["peak_rss_mib"]
    latency = max(row["seconds"] for row in result["cases"])
    report["resource_profiles"] = {
        "current_4GiB": {"model_budget_mib": 1800, "passed": peak <= 1800 and latency <= 12},
        "candidate_8GiB": {"model_budget_mib": 5120, "reserved_for_application_mib": 3072,
                           "passed": peak <= 5120 and latency <= 12}}
    report["resource_gate_passed"] = report["resource_profiles"]["candidate_8GiB"]["passed"]
    report["status"] = "evaluated"


def prepare(report):
    CACHE.mkdir(parents=True, exist_ok=True)
    available = mem_available()
    free = shutil.disk_usage(CACHE).free
    report["preflight"] = {"mem_available_mib": available // MIB, "disk_free_mib": free // MIB}
    if available < 7168 * MIB or free < 10 * 1024 * MIB:
        report["reason"] = "owner_host_capacity_insufficient"
        return
    download()
    with tempfile.TemporaryDirectory(prefix="analyst-e4b-eval-") as directory:
        folder = Path(directory)
        subprocess.run([sys.executable, "-m", "venv", str(folder / "venv")], check=True, timeout=60)
        python = str(folder / "venv/bin/python")
        installation = folder / "installed.json"
        completed = subprocess.run([python, "-m", "pip", "install", "--only-binary=:all:",
            "--disable-pip-version-check", "--report", str(installation), "litert-lm-api==0.18.1"],
            capture_output=True, timeout=180)
        if completed.returncode:
            report["reason"] = "pinned_runtime_dependency_unavailable"
            return
        rows = json.loads(installation.read_text())["install"]
        report["dependencies"] = [{"name": row["metadata"]["name"], "version": row["metadata"]["version"],
            "sha256": row["download_info"]["archive_info"]["hashes"]["sha256"]} for row in rows]
        runtime = [row for row in report["dependencies"] if row["name"].replace("_", "-").lower() == "litert-lm-api"]
        if len(runtime) != 1 or runtime[0]["sha256"] != RUNTIME_SHA:
            report["reason"] = "runtime_wheel_changed"
            return
        if mem_available() < 7168 * MIB:
            report["reason"] = "owner_host_capacity_changed"
            return
        supervise(python, folder, report)


def main():
    if sys.platform != "linux" or os.environ.get("WSL_DISTRO_NAME") != "Ubuntu-24.04":
        raise ValueError("owner_wsl_required")
    if sys.argv[1:] == ["--evaluate"]:
        child()
        return
    if len(sys.argv) != 1:
        raise ValueError("unsupported_arguments")
    report = {"status": "not_completed", "reference_commit": SOURCE_SHA, "production_activated": False,
              "cloud_inference_called": False, "synthetic_fixtures_only": True, "trade_permission": False}
    try:
        prepare(report)
    except (ValueError, OSError, subprocess.SubprocessError):
        report["reason"] = "preparation_or_evaluation_unavailable"
    (ROOT / "local-e4b-evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    print("LOCAL_E4B_EVALUATION=" + json.dumps(report), flush=True)
    if report["status"] != "evaluated":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
