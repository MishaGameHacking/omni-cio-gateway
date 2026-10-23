"""One-time infrastructure preparation, separate from the app repair branch.

Stage the existing installer on one fresh VM. Owner sign-in remains interactive;
this operation never starts the backend or changes the APK update channel.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import timeweb_ci_capacity as cloud
from timeweb_actions_probe import NoRedirect, ProbeError, decode_response, read_catalog, read_resource, summarize, validated_token, verified_ssl_context
from timeweb_ci_catalog import ubuntu_images

PROJECT = 2941515
PRESET = 6771
NAME = "analyst-ai-owner-20261023"
HOST = "analyst-ai-2941515.twc1.net"
MARKER = "Analyst AI owner installation 2026-10-23"
SOURCE = "fd01d2ac090103cf64557c97aeaf36bc290e2cec"


def domain_api(token, method, *, address=None):
    path = "/add-domain/" + HOST if method == "POST" else "/domains/" + HOST
    payload = None if address is None else json.dumps({"linked_ip": address}).encode()
    request = urllib.request.Request("https://api.timeweb.cloud/api/v1" + path,
        method=method, data=payload, headers={"Authorization": "Bearer " + token,
        "Accept": "application/json", "Content-Type": "application/json"})
    try:
        opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=verified_ssl_context()))
        with opener.open(request, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        if method == "GET" and error.code == 404:
            return None
        raise ProbeError("domain_http_" + str(error.code)) from None
    except OSError:
        raise ProbeError("domain_transport_failed_no_mutation_retry") from None
    return decode_response(raw) if raw else {}


def validate(token):
    if PROJECT not in summarize("projects", read_resource(token, "projects"))["ids"]:
        raise ProbeError("expected_project_missing")
    inventory = read_resource(token, "servers")
    if not summarize("servers", inventory)["complete"]:
        raise ProbeError("incomplete_server_inventory")
    if any(s.get("name") == NAME for s in inventory["servers"]):
        raise ProbeError("installation_already_exists_no_duplicate_order")
    rows = read_catalog(token, "presets").get("server_presets", [])
    matches = [p for p in rows if p.get("id") == PRESET]
    if len(matches) != 1:
        raise ProbeError("expected_offer_missing")
    offer = matches[0]
    if tuple(offer.get(k) for k in ("cpu", "ram", "disk", "price", "location")) != (1, 2048, 30720, 550, "ru-4"):
        raise ProbeError("offer_or_price_changed")
    if not any(x["id"] == 99 and x["version"] == "24.04" for x in ubuntu_images(read_catalog(token, "os"))):
        raise ProbeError("expected_os_missing")
    if domain_api(token, "GET") is not None:
        raise ProbeError("hostname_already_exists_no_replacement")
    print("OWNER_VM_OFFER=" + json.dumps({k: offer[k] for k in ("id", "price", "cpu", "ram", "disk", "location")}), flush=True)


def ssh_command(folder, address, host_public):
    known = folder / "known_hosts"
    known.write_text(address + " " + host_public + "\n")
    config = folder / "ssh_config"
    config.write_text("")
    return ["ssh", "-F", str(config), "-i", str(folder / "client"),
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=8",
        "-o", "StrictHostKeyChecking=yes", "-o", "HostKeyAlgorithms=ssh-ed25519",
        "-o", "UserKnownHostsFile=" + str(known), "root@" + address]


def remote(command, script, data=None, *, timeout=45):
    result = subprocess.run(command + [script], input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise ProbeError("remote_command_failed_" + str(result.returncode))
    return result.stdout


def ready(token, server_id, folder, host_public):
    for _ in range(42):
        server = cloud.owned_server(cloud.request(token, "GET", f"/api/v1/servers/{server_id}"), NAME)
        if server["id"] != server_id:
            raise ProbeError("server_id_changed")
        address = cloud.public_ipv4(server)
        if address:
            command = ssh_command(folder, address, host_public)
            try:
                remote(command, "cloud-init status --wait >/dev/null && test -d /root", timeout=20)
                return command, address
            except (ProbeError, subprocess.TimeoutExpired):
                pass
        time.sleep(10)
    raise ProbeError("new_vm_ssh_readiness_timeout")


def stage(command, address, telegram_id, telegram_secret):
    # Archive only the already checked server commit, never the operational patch.
    archive = subprocess.check_output(["git", "archive", "--format=tar.gz", SOURCE, "backend", "deploy"], cwd=ROOT)
    remote(command, "umask 077; test ! -e /root/analyst-ai-source && mkdir /root/analyst-ai-source && tar -xzf - -C /root/analyst-ai-source", archive)
    values = {"TELEGRAM_CLIENT_ID": telegram_id, "TELEGRAM_CLIENT_SECRET": telegram_secret,
        "BACKEND_PUBLIC_URL": "https://" + HOST, "EXPECTED_PUBLIC_IPV4": address,
        "TELEGRAM_ENROLLMENT_REDIRECT_URI": "https://" + HOST + "/auth/telegram/owner-enrollment/callback"}
    remote(command, "umask 077; test ! -e /root/analyst-ai-enrollment.json && cat > /root/analyst-ai-enrollment.json", json.dumps(values).encode())
    output = remote(command, "cd /root/analyst-ai-source && python3 deploy/install_owner_backend.py --enroll-owner")
    if output.strip() != b"OWNER_BACKEND_INSTALL=configuration_and_sources_validated_only":
        raise ProbeError("installer_preparation_not_confirmed")
    report = json.loads(remote(command, "python3 -c 'import json,shutil,pathlib; print(json.dumps({\"free_disk\":shutil.disk_usage(\"/\").free,\"memory\":next(x for x in pathlib.Path(\"/proc/meminfo\").read_text().splitlines() if x.startswith(\"MemTotal:\"))}))'"))
    if report["free_disk"] < 5 * 1024**3:
        raise ProbeError("fresh_vm_insufficient_free_disk")
    return {"source": SOURCE, "archive_sha256": hashlib.sha256(archive).hexdigest(), "hardware": report}


def prepare(token, telegram_id, telegram_secret):
    validate(token)
    cloud.PRESET_ID = PRESET
    cloud.OWNER_MARKER = MARKER
    with tempfile.TemporaryDirectory(prefix="analyst-owner-", dir=os.environ["RUNNER_TEMP"]) as root:
        folder = Path(root)
        cloud.generate_key(folder / "client")
        cloud.generate_key(folder / "host")
        client = (folder / "client.pub").read_text().strip()
        host_public = (folder / "host.pub").read_text().strip()
        config = {"users": [{"name": "root", "lock_passwd": True, "ssh_authorized_keys": [client]}],
            "ssh_pwauth": False, "disable_root": False, "ssh_deletekeys": True,
            "ssh_keys": {"ed25519_private": (folder / "host").read_text(), "ed25519_public": host_public},
            "ssh": {"emit_keys_to_console": False}, "no_ssh_fingerprints": True,
            "runcmd": [["systemctl", "restart", "ssh"]]}
        # No mutation retries: reconcile the stable name after any ambiguous POST.
        server = cloud.owned_server(cloud.request(token, "POST", "/api/v1/servers", {
            "name": NAME, "hostname": NAME, "comment": MARKER,
            "preset_id": PRESET, "os_id": 99, "project_id": PROJECT,
            "cloud_init": "#cloud-config\n" + json.dumps(config) + "\n"}), NAME)
        print("OWNER_VM_CREATED=" + json.dumps({"id": server["id"], "host_key": host_public}), flush=True)
        command, address = ready(token, server["id"], folder, host_public)
        try:
            domain_api(token, "POST")
            domain_api(token, "PATCH", address=address)
            domain = domain_api(token, "GET").get("domain", {})
            if domain.get("linked_ip") != address or domain.get("is_technical") is not True:
                raise ProbeError("technical_domain_binding_unverified")
            report = stage(command, address, telegram_id, telegram_secret)
            print("OWNER_VM_PREPARED=" + json.dumps({"id": server["id"], "ip": address, "hostname": HOST,
                "backend_started": False, "owner_enrollment_required": True, **report}), flush=True)
        finally:
            script = "python3 -c 'import pathlib,sys; p=pathlib.Path(\"/root/.ssh/authorized_keys\"); k=sys.stdin.read().strip(); p.write_text(\"\\n\".join(x for x in p.read_text().splitlines() if k not in x)+\"\\n\")'"
            remote(command, script, client.encode())
            print("OWNER_VM_TEMPORARY_ACCESS=removed", flush=True)


def main():
    token = validated_token(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
    values = [os.environ.get(k, "").strip() for k in ("TELEGRAM_CLIENT_ID", "TELEGRAM_CLIENT_SECRET")]
    if not all(values):
        raise ProbeError("telegram_credentials_missing")
    prepare(token, *values)


if __name__ == "__main__":
    try:
        main()
    except (ProbeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print("OWNER_VM_PREPARATION_ERROR=" + (str(error) if isinstance(error, ProbeError) else type(error).__name__), flush=True)
        sys.exit(1)
