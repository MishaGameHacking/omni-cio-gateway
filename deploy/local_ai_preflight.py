"""Observe fixed local AI prerequisites; no DB, credentials, app imports or writes."""
from datetime import datetime, timezone
import ctypes.util
import grp
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

SOURCE = "68e0fb73feddf178c29d990633edae42aa7adda3"
ROOT = Path("/opt/analyst-ai")


def memory(raw):
    result = {}
    for line in raw.splitlines():
        match = re.fullmatch(r"(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+([0-9]{1,12}) kB", line)
        if match:
            result[match[1]] = int(match[2]) // 1024
    return result


def os_release(raw):
    values = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    return {key: value for key in ("ID", "VERSION_ID")
            if re.fullmatch(r"[a-z0-9.-]{1,32}", value := values.get(key, "").strip('"'))}


def services(run=subprocess.run):
    result = {}
    for name in ("analyst-ai-owner.service", "analyst-ai-updates.service"):
        row = run(["systemctl", "show", name, "--property=ActiveState,SubState,MemoryCurrent,User,Group"],
                  capture_output=True, check=True, timeout=10)
        values = dict(line.split("=", 1) for line in row.stdout.decode().splitlines() if "=" in line)
        usage = values.get("MemoryCurrent", "")
        result[name] = {"active": values.get("ActiveState") == "active",
                        "running": values.get("SubState") == "running",
                        "memory_mib": int(usage) // 1024**2 if re.fullmatch(r"[0-9]{1,14}", usage) else None,
                        "uses_expected_user": values.get("User") == "analyst-ai",
                        "uses_expected_group": values.get("Group") in ("", "analyst-ai")}
    return result


def identities():
    result = {}
    for name in ("analyst-ai", "analyst-local-ai"):
        try:
            pwd.getpwnam(name)
            result[name + "_user_exists"] = True
        except KeyError:
            result[name + "_user_exists"] = False
    try:
        grp.getgrnam("analyst-ai")
        result["application_group_exists"] = True
    except KeyError:
        result["application_group_exists"] = False
    return result


def probe(run=subprocess.run):
    response = run(["curl", "--silent", "--output", os.devnull, "--write-out", "%{http_code}",
                    "--max-time", "8", "--connect-timeout", "3", "--max-filesize", "4096",
                    "--max-redirs", "0", "http://127.0.0.1:8080/health"], capture_output=True, timeout=10)
    raw = response.stdout.decode(errors="replace")
    return {"http_status": int(raw) if re.fullmatch(r"[1-5][0-9]{2}", raw) else None,
            "transport_succeeded": response.returncode == 0}


def run(envelope):
    if os.getuid() != 0 or envelope.get("payload") != {"source_commit": SOURCE}:
        raise ValueError("preflight_identity_invalid")
    if ROOT.is_symlink() or ROOT.resolve(strict=True) != ROOT:
        raise ValueError("runtime_directory_invalid")
    usage = shutil.disk_usage(ROOT)
    report = {"status": "observed", "observed_at": datetime.now(timezone.utc).isoformat(),
              "server_id": 9417611, "memory_mib": memory(Path("/proc/meminfo").read_text()),
              "disk_free_mib": usage.free // 1024**2, "disk_total_mib": usage.total // 1024**2,
              "os": os_release(Path("/etc/os-release").read_text()), "python": list(sys.version_info[:3]),
              "identities": identities(), "services": services(), "local_health": probe(),
              "libraries": {name: ctypes.util.find_library(name) is not None for name in ("c++", "c++abi", "atomic", "stdc++")},
              "venv_available": importlib.util.find_spec("venv") is not None,
              "local_model_directory_present": Path("/opt/analyst-local-ai").exists(),
              "source_directory_present": (ROOT / "source").exists(),
              "database_read": False, "configuration_read": False, "application_imported": False,
              "files_written": False, "service_changed": False, "model_called": False, "broker_called": False}
    print("LOCAL_AI_PREFLIGHT=" + json.dumps(report), flush=True)


if __name__ == "__main__":
    try:
        run(ENVELOPE)
    except Exception:
        print(json.dumps({"status": "unavailable", "code": "local_ai_preflight_failed"}), flush=True)
        raise SystemExit(1) from None
