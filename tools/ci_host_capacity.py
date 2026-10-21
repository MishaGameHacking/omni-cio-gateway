"""Measure a Linux CI host before committing to a paid Android runner."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


def measure() -> dict:
    import fcntl

    memory = Path("/proc/meminfo").read_text()
    cpu = Path("/proc/cpuinfo").read_text()
    result = {
        "cpu_count": os.cpu_count(),
        "memory_kib": int(next(line.split()[1] for line in memory.splitlines()
                               if line.startswith("MemTotal:"))),
        "free_disk_bytes": shutil.disk_usage(os.getcwd()).free,
        "virtualization_flag": any(flag in cpu.split() for flag in ("vmx", "svm")),
        "kvm_device": Path("/dev/kvm").exists(),
        "kvm_api_version": None,
    }
    if result["kvm_device"]:
        try:
            with open("/dev/kvm", "rb", buffering=0) as device:
                result["kvm_api_version"] = fcntl.ioctl(device, 0xAE00, 0)
        except OSError:
            pass
    return result


def main() -> int:
    report = measure()
    print("CI_HOST_CAPACITY=" + json.dumps(report, sort_keys=True), flush=True)
    return 0 if (report["kvm_api_version"] == 12
                 and report["free_disk_bytes"] >= 6 * 1024**3) else 1


if __name__ == "__main__":
    raise SystemExit(main())
