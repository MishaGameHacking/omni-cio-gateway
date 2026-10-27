"""Administrative SSH transport only. Project code executes on Timeweb, never here."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path[:0] = [".transport-admin/deploy", ".transport-admin/tools"]
import prepare_owner_vm as p
import access_owner_vm as access

SERVER_ID = 9417611
IP = "83.217.195.29"
HOST_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILN7hxzg6D6GjaE9OYQ19wH86tSm10pTnv+s81eqOfIU runner@runnervmtai0g"
REPORTS = Path("plan-reports")
REPORTS.mkdir(exist_ok=True)
TOKEN = p.validated_token(os.environ["TIMEWEB_CLOUD_TOKEN"])


def api(method, path, body=None):
    request = urllib.request.Request("https://api.timeweb.cloud/api/v1" + path,
        method=method, data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(p.NoRedirect(), urllib.request.HTTPSHandler(context=p.verified_ssl_context())).open(request, timeout=45) as response:
            raw = response.read(4194305)
            if len(raw) > 4194304:
                raise RuntimeError("cloud_response_too_large")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        return error.code, {}


def main():
    script = Path("deploy/plan-20261027/operation.py").read_bytes()
    if not 1 <= len(script) <= 2 * 1024 * 1024:
        raise RuntimeError("invalid_operation_size")
    payload_path = Path("deploy/plan-20261027/payload.json")
    payload = payload_path.read_bytes() if payload_path.exists() else b"{}"
    if len(payload) > 8 * 1024 * 1024:
        raise RuntimeError("invalid_payload_size")
    # The envelope is passed as stdin, never a command-line argument or log.
    envelope = json.dumps({"operation": script.decode(), "payload": json.loads(payload),
        "github_sha": os.environ["GITHUB_SHA"], "run_id": os.environ["GITHUB_RUN_ID"]}).encode()
    bootstrap = "import json,sys; e=json.load(sys.stdin); exec(compile(e['operation'],'owner-plan-operation','exec'),{'ENVELOPE':e,'__name__':'__main__'})"
    status, data = api("GET", "/servers/" + str(SERVER_ID))
    if status != 200:
        raise RuntimeError("server_identity_unavailable")
    server = data["server"]
    if not (server["name"] == "Analyst AI runtime 20261025" and server["project_id"] == 2941515
            and server["availability_zone"] == "ams-1" and p.cloud.public_ipv4(server) == IP):
        raise RuntimeError("server_identity_mismatch")
    access.SERVER_ID = SERVER_ID
    with tempfile.TemporaryDirectory(prefix="analyst-plan-admin-", dir=os.environ["RUNNER_TEMP"]) as directory:
        folder = Path(directory)
        p.cloud.generate_key(folder / "client")
        public = (folder / "client.pub").read_text().strip()
        created = access.request(TOKEN, "POST", "/ssh-keys", {"name": "analyst-plan-admin-" + os.environ["GITHUB_RUN_ID"], "body": public, "is_default": False})
        key = created.get("ssh_key", created.get("ssh-key", {}))
        key_id = key["id"]
        if type(key_id) is not int or key["body"].split()[:2] != public.split()[:2]:
            raise RuntimeError("temporary_key_identity_mismatch")
        attached = False
        try:
            access.request(TOKEN, "POST", "/servers/" + str(SERVER_ID) + "/ssh-keys", {"ssh_key_ids": [key_id]})
            attached = True
            command = p.ssh_command(folder, IP, HOST_KEY)
            command[1:1] = ["-o", "ServerAliveInterval=20", "-o", "ServerAliveCountMax=3"]
            for attempt in range(12):
                try:
                    p.remote(command, "test $(id -u) = 0", timeout=12)
                    break
                except (p.ProbeError, subprocess.TimeoutExpired):
                    if attempt == 11:
                        raise
                    time.sleep(5)
            result = subprocess.run([*command, "python3 -c " + shlex.quote(bootstrap)], input=envelope,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=720)
            # Operation contract: stdout contains only allowlisted, non-secret receipts.
            (REPORTS / "receipt.txt").write_bytes(result.stdout)
            receipt = {"server_id": SERVER_ID, "github_sha": os.environ["GITHUB_SHA"],
                "operation_sha256": hashlib.sha256(script).hexdigest(), "payload_sha256": hashlib.sha256(payload).hexdigest(),
                "remote_exit_code": result.returncode, "stderr_bytes": len(result.stderr),
                "receipt_sha256": hashlib.sha256(result.stdout).hexdigest()}
            (REPORTS / "transport.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(result.stdout.decode("utf-8", errors="replace"), flush=True)
            print("TRANSPORT=" + json.dumps(receipt), flush=True)
            if result.returncode:
                raise RuntimeError("remote_operation_failed_see_preserved_server_evidence")
        finally:
            try:
                if attached:
                    access.request(TOKEN, "DELETE", "/servers/" + str(SERVER_ID) + "/ssh-keys/" + str(key_id))
            finally:
                access.request(TOKEN, "DELETE", "/ssh-keys/" + str(key_id))
            print("AMS_TEMP_KEY_REMOVED=true", flush=True)


if __name__ == "__main__":
    main()
