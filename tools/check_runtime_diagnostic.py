"""Run Linux filesystem read-only runtime diagnostic checks in the laptop's project WSL under its lease."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / ".github/scripts"))
import emulator_lease

def main():
    if sys.platform != "win32" or os.environ.get("COMPUTERNAME") != "LAPTOP-NPSGA016":
        raise RuntimeError("owner_laptop_required")
    raw = (root / ".github/scripts/emulator_lease.py").read_bytes()
    if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != "c9626f3bf90b612a71b9bbf2954d0c134aa29b22":
        raise RuntimeError("canonical_host_lease_changed")
    claim = json.loads(Path("C:/actions-runner-2/_work/_tool/AnalystLinux/analyst-project-distribution.json").read_text())
    if claim.get("distribution") != "Ubuntu-24.04" or claim.get("host") != "LAPTOP-NPSGA016" or not claim.get("completed_at"):
        raise RuntimeError("project_distribution_identity_changed")
    if root.drive.upper() != "C:":
        raise RuntimeError("unsupported_source_drive")
    path = "/mnt/c/" + "/".join(root.parts[1:]) + "/deploy/test_runtime_diagnostic.py"
    env = {key: value for key, value in os.environ.items() if key.upper() in {
        "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "USERPROFILE", "COMPUTERNAME",
        "LOCALAPPDATA", "APPDATA", "PROGRAMDATA", "COMSPEC"}}
    with emulator_lease.exclusive_emulator():
        # Run40673296285 started this project-only distribution for wslpath and failed
        # before tests. Reuse it under the canonical lease and close it in all outcomes.
        try:
            subprocess.run(["wsl.exe", "--distribution", "Ubuntu-24.04", "--user", "analyst-ci", "--exec",
                "/usr/bin/timeout", "--kill-after=5s", "90s", "/usr/bin/python3", "-I", path, "-v"],
                cwd=root, env=env, stdin=subprocess.DEVNULL, check=True, timeout=120)
        finally:
            subprocess.run(["wsl.exe", "--terminate", "Ubuntu-24.04"], cwd=root, env=env,
                stdin=subprocess.DEVNULL, check=True, timeout=60)

if __name__ == "__main__":
    main()


