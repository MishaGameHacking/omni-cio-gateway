"""Read the owner's reset root credential; export only RSA-OAEP ciphertext."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def main():
    if (os.environ.get("GITHUB_REPOSITORY") != "MishaGameHacking/omni-cio-gateway"
            or os.environ.get("GITHUB_REF") != "refs/heads/codex/lenovo-transfer-2026-10-31"
            or os.environ.get("GITHUB_EVENT_NAME") != "push"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        raise RuntimeError("wrong_operation_identity")
    token = os.environ.pop("TIMEWEB_CLOUD_TOKEN")
    request = urllib.request.Request(
        "https://api.timeweb.cloud/api/v1/servers/9417611",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError("metadata_not_available")
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise RuntimeError("metadata_too_large")
    server = json.loads(raw)["server"]
    ips = [entry.get("ip") for net in server.get("networks", []) if net.get("type") == "public"
           for entry in net.get("ips", []) if entry.get("type") == "ipv4"]
    if (server.get("id") != 9417611 or server.get("project_id") != 2941515
            or server.get("name") != "Analyst AI runtime 20261025"
            or server.get("availability_zone") != "ams-1" or ips != ["83.217.195.29"]):
        raise RuntimeError("server_identity_mismatch")
    password = server.get("root_pass")
    if not isinstance(password, str) or not 8 <= len(password.encode()) <= 128:
        raise RuntimeError("root_credential_not_available")
    output = Path("encrypted-credential")
    output.mkdir(mode=0o700)
    encrypted = subprocess.run([
        "openssl", "pkeyutl", "-encrypt", "-certin", "-inkey", "tools/lenovo-recipient.pem",
        "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
        "-pkeyopt", "rsa_mgf1_md:sha256"], input=password.encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    if encrypted.returncode or len(encrypted.stdout) != 384:
        raise RuntimeError("credential_encryption_failed")
    (output / "root-credential.rsa").write_bytes(encrypted.stdout)
    receipt = {"server_id": 9417611, "operation": "read_only", "credential_encrypted": True,
               "cipher": "RSA-3072-OAEP-SHA256", "private_key_location": "Lenovo only",
               "status": server.get("status"), "boot_mode": server.get("boot_mode")}
    (output / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never serialize an HTTP response, credential, URL or arbitrary exception message.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1)
