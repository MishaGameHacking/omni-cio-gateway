"""Authenticated Timeweb transport and whole-file public verification for shell51."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import urllib.request

import owner_plan_transport_20261027 as transport

PUBLIC = "https://analyst-ai-2941515.twc1.net"


def need(value, code):
    if not value:
        raise RuntimeError(code)


def transfer(operation, meta, payload):
    p, access = transport.p, transport.access
    status, data = transport.api("GET", "/servers/" + str(transport.SERVER_ID))
    need(status == 200, "server_identity_unavailable")
    server = data["server"]
    need(server["name"] == "Analyst AI runtime 20261025" and server["project_id"] == 2941515
         and server["availability_zone"] == "ams-1" and p.cloud.public_ipv4(server) == transport.IP,
         "server_identity_mismatch")
    access.SERVER_ID = transport.SERVER_ID
    with tempfile.TemporaryDirectory(prefix="analyst-shell-delivery-", dir=os.environ["RUNNER_TEMP"]) as directory:
        folder = Path(directory)
        p.cloud.generate_key(folder / "client")
        public = (folder / "client.pub").read_text().strip()
        created = access.request(transport.TOKEN, "POST", "/ssh-keys",
            {"name": "analyst-shell-" + os.environ["GITHUB_RUN_ID"], "body": public, "is_default": False})
        key = created.get("ssh_key", created.get("ssh-key", {}))
        key_id = key["id"]
        need(type(key_id) is int and key["body"].split()[:2] == public.split()[:2], "temporary_key_identity_mismatch")
        attached = False
        try:
            access.request(transport.TOKEN, "POST", "/servers/" + str(transport.SERVER_ID) + "/ssh-keys", {"ssh_key_ids": [key_id]})
            attached = True
            command = p.ssh_command(folder, transport.IP, transport.HOST_KEY)
            command[1:1] = ["-o", "ServerAliveInterval=20", "-o", "ServerAliveCountMax=3"]
            for attempt in range(12):
                try:
                    p.remote(command, "test $(id -u) = 0", timeout=12)
                    break
                except (p.ProbeError, subprocess.TimeoutExpired):
                    if attempt == 11:
                        raise
                    time.sleep(5)
            bootstrap = "import json,sys; e=json.loads(sys.stdin.buffer.readline(131073)); exec(compile(e['operation'],'shell-publication','exec'),{'ENVELOPE':e,'__name__':'__main__'})"
            header = json.dumps({"operation": operation, "meta": meta}).encode() + b"\n"
            need(len(header) <= 131072, "operation_header_too_large")
            result = subprocess.run([*command, "/opt/analyst-ai/venv/bin/python -c " + shlex.quote(bootstrap)],
                input=header + payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=360)
            (transport.REPORTS / "shell-remote-receipt.json").write_bytes(result.stdout)
            need(result.returncode == 0, "shell_remote_publication_failed")
            need(len(result.stdout) <= 65536, "unexpected_publication_output")
            return json.loads(result.stdout)
        finally:
            try:
                if attached:
                    access.request(transport.TOKEN, "DELETE", "/servers/" + str(transport.SERVER_ID) + "/ssh-keys/" + str(key_id))
            finally:
                access.request(transport.TOKEN, "DELETE", "/ssh-keys/" + str(key_id))
            print("SHELL_TEMP_KEY_REMOVED=true", flush=True)


def verify_public(receipt):
    opener = urllib.request.build_opener(transport.p.NoRedirect(),
        urllib.request.HTTPSHandler(context=transport.p.verified_ssl_context()))
    def get_json(path, limit):
        with opener.open(urllib.request.Request(PUBLIC + path, headers={"Cache-Control": "no-cache"}), timeout=45) as response:
            need(response.status == 200 and response.headers.get_content_type() == "application/json", "unexpected_public_json")
            raw = response.read(limit + 1)
            need(len(raw) <= limit, "public_json_too_large")
            return json.loads(raw)
    policy_path = "/client/update-policy?package_name=ru.omnicio.app.debug"
    policy = get_json(policy_path, 16384)
    for key in ("version_code", "version_name", "apk_sha256", "apk_bytes", "certificate_sha256", "published_at"):
        need(type(policy[key]) is type(receipt[key]) and policy[key] == receipt[key], "public_policy_mismatch")
    expected_path = "/client/apk/Analyst-AI-51-" + receipt["apk_sha256"] + ".apk"
    need(policy["package_name"] == "ru.omnicio.app.debug" and policy["minimum_version_code"] == 51
         and policy["min_sdk"] == 37 and policy["apk_path"] == expected_path
         and receipt["url"] == PUBLIC + expected_path, "public_channel_mismatch")
    digest, size = hashlib.sha256(), 0
    with opener.open(urllib.request.Request(receipt["url"], headers={"Cache-Control": "no-cache"}), timeout=120) as response:
        need(response.status == 200 and response.headers.get_content_type() == "application/vnd.android.package-archive",
             "unexpected_public_apk")
        for block in iter(lambda: response.read(1024**2), b""):
            size += len(block)
            need(size <= receipt["apk_bytes"], "public_apk_too_large")
            digest.update(block)
    need(size == receipt["apk_bytes"] and digest.hexdigest() == receipt["apk_sha256"], "public_apk_bytes_changed")
    need(get_json(policy_path, 16384) == policy, "public_policy_changed_during_download")
    need(get_json("/health", 1024) == {"status": "ok"}, "runtime_health_failed")
    return {"publication": receipt, "https_policy_verified": True, "https_entire_apk_verified": True,
            "backend_health": 200, "physical_phone_verified": False}


def main():
    root = Path(os.environ["RUNNER_TEMP"])
    meta = json.loads((root / "server-shell-meta.json").read_text())
    payload = (root / "server-shell-payload.zip").read_bytes()
    need(hashlib.sha256(payload).hexdigest() == meta["payload_sha256"], "transfer_payload_changed")
    receipt = transfer(Path("deploy/publish_workspace_shell.py").read_text(), meta, payload)
    need(receipt["status"] == "published" and receipt["source_commit"] == os.environ["EXPECTED_SOURCE_SHA"]
         and receipt["apk_sha256"] == os.environ["EXPECTED_APK_SHA256"], "publication_receipt_mismatch")
    verification = verify_public(receipt)
    (transport.REPORTS / "shell-public-verification.json").write_text(json.dumps(verification, indent=2))
    print("SERVER_SHELL_PUBLIC_VERIFIED=" + json.dumps(verification), flush=True)


if __name__ == "__main__":
    main()
