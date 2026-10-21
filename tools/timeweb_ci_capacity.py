"""Bounded, disposable Timeweb VM probe; no application or production deployment."""
from __future__ import annotations

import argparse
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

from timeweb_actions_probe import (
    BASE_URL, MAX_BYTES, NoRedirect, ProbeError, decode_response, read_catalog,
    read_resource, summarize, transport_error_code, validated_token, verified_ssl_context,
)
from timeweb_ci_catalog import candidate_presets, ubuntu_images

PROJECT_ID = 2941515
PRESET_ID = 4245
OS_ID = 99
MAX_MONTHLY_RUB = 6800
OWNER_MARKER = "Analyst AI disposable Android capacity check"
REMOTE_PROBE = r'''import fcntl, json, os, pathlib, shutil
cpu = pathlib.Path('/proc/cpuinfo').read_text()
memory = pathlib.Path('/proc/meminfo').read_text()
result = {
    'cpu_count': os.cpu_count(),
    'free_disk_bytes': shutil.disk_usage('/').free,
    'memory_kib': int(next(line.split()[1] for line in memory.splitlines() if line.startswith('MemTotal:'))),
    'virtualization_flag': any(flag in cpu.split() for flag in ('vmx', 'svm')),
    'kvm_device': pathlib.Path('/dev/kvm').exists(),
    'kvm_api_version': None,
    'drm_device': pathlib.Path('/dev/dri/renderD128').exists(),
}
if result['kvm_device']:
    try:
        with open('/dev/kvm', 'rb', buffering=0) as device:
            result['kvm_api_version'] = fcntl.ioctl(device, 0xAE00, 0)
    except OSError:
        pass
print(json.dumps(result, sort_keys=True))
'''


def identity() -> str:
    run = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if not re.fullmatch(r"\d{1,20}", run, re.ASCII) or not re.fullmatch(r"\d{1,5}", attempt, re.ASCII):
        raise ProbeError("github_run_identity_required")
    return "analyst-ci-" + run + "-" + attempt


def state_path() -> Path:
    root = os.environ.get("RUNNER_TEMP", "")
    if not root or not Path(root).is_dir():
        raise ProbeError("runner_temp_required")
    return Path(root) / (identity() + ".json")


def error_details(raw: bytes) -> dict:
    """Only a bounded symbolic code and known field names; never the error message."""
    try:
        document = decode_response(raw)
    except ProbeError:
        return {}
    result = {}
    code = document.get("error_code")
    if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,64}", code):
        result["error_code"] = code
    message = json.dumps(document.get("message", ""), ensure_ascii=False).lower()
    fields = ("preset_id", "os_id", "project_id", "cloud_init", "hostname", "ssh_keys_ids",
              "availability_zone", "configuration", "is_root_password_required", "network")
    result["mentioned_fields"] = [field for field in fields if field in message]
    result["balance_mentioned"] = any(term in message for term in ("balance", "баланс", "средств"))
    return result


def request(token: str, method: str, path: str, body=None) -> dict:
    allowed = (method == "POST" and path == "/api/v1/servers") or (
        method in {"GET", "DELETE"} and re.fullmatch(r"/api/v1/servers/[1-9]\d{0,15}", path, re.ASCII))
    if not allowed:
        raise ProbeError("unapproved_capacity_request")
    token = validated_token(token)
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Accept": "application/json",
        "Content-Type": "application/json", "Accept-Encoding": "identity",
    })
    try:
        opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=verified_ssl_context()))
        with opener.open(req, timeout=30) as response:
            if response.status not in {200, 201, 204}:
                raise ProbeError("unexpected_capacity_http_status")
            if response.headers.get("Content-Encoding", "identity").lower() not in {"identity", ""}:
                raise ProbeError("encoded_response_refused")
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        code = error.code
        details = error_details(error.read(MAX_BYTES + 1))
        error.close()
        if code != 404:
            print("TIMEWEB_CAPACITY_HTTP=" + json.dumps({"status": code, **details}, sort_keys=True), flush=True)
        raise ProbeError("timeweb_http_" + str(code)) from None
    except OSError as error:
        raise ProbeError(transport_error_code(error)) from None
    return decode_response(raw) if raw else {}


def validate_offer(token: str) -> dict:
    projects = summarize("projects", read_resource(token, "projects"))
    if PROJECT_ID not in projects["ids"]:
        raise ProbeError("expected_project_not_visible")
    offers = candidate_presets(read_catalog(token, "presets"))
    matches = [offer for offer in offers if offer["id"] == PRESET_ID]
    if len(matches) != 1 or matches[0]["price"] > MAX_MONTHLY_RUB:
        raise ProbeError("capacity_offer_changed_or_over_budget")
    images = ubuntu_images(read_catalog(token, "os"))
    if not any(item["id"] == OS_ID and item["version"] == "24.04" for item in images):
        raise ProbeError("capacity_os_changed")
    return matches[0]


def owned_server(document: dict, name: str) -> dict:
    server = document.get("server")
    if (type(server) is not dict or type(server.get("id")) is not int
            or server["id"] <= 0 or server.get("name") != name
            or server.get("comment") != OWNER_MARKER
            or server.get("preset_id") != PRESET_ID):
        raise ProbeError("capacity_server_ownership_mismatch")
    return server


def public_ipv4(server: dict) -> str | None:
    for network in server.get("networks", []):
        if network.get("type") != "public":
            continue
        for entry in network.get("ips", []):
            if entry.get("type") == "ipv4":
                address = IPv4Address(entry["ip"])
                if address.is_global:
                    return str(address)
    return None


def cloud_config(client_public: str, host_private: str, host_public: str) -> str:
    # JSON is a YAML subset. Only a fresh VM receives these single-run keys.
    config = {
        "users": [{"name": "ci-probe", "shell": "/bin/bash", "lock_passwd": True,
                   "sudo": "ALL=(ALL) NOPASSWD:ALL", "ssh_authorized_keys": [client_public]}],
        "ssh_pwauth": False, "disable_root": True, "ssh_deletekeys": True,
        "ssh_keys": {"ed25519_private": host_private, "ed25519_public": host_public},
        "ssh": {"emit_keys_to_console": False}, "no_ssh_fingerprints": True,
        "runcmd": [["systemctl", "restart", "ssh"]],
    }
    return "#cloud-config\n" + json.dumps(config) + "\n"


def generate_key(path: Path) -> None:
    keygen = shutil.which("ssh-keygen")
    if not keygen:
        raise ProbeError("ssh_keygen_missing")
    subprocess.run([keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(path)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)


def wait_probe(token: str, server_id: int, name: str, root: Path, host_public: str) -> dict:
    ssh = shutil.which("ssh")
    if not ssh:
        raise ProbeError("ssh_missing")
    config = root / "ssh_config"
    config.write_text("", encoding="utf-8")
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        server = owned_server(request(token, "GET", f"/api/v1/servers/{server_id}"), name)
        address = public_ipv4(server)
        if address:
            hosts = root / "known_hosts"
            hosts.write_text(address + " " + host_public + "\n", encoding="utf-8")
            command = [ssh, "-F", str(config), "-i", str(root / "client"),
                       "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                       "-o", "StrictHostKeyChecking=yes", "-o", "HostKeyAlgorithms=ssh-ed25519",
                       "-o", "UserKnownHostsFile=" + str(hosts), "-o", "ConnectTimeout=10",
                       "ci-probe@" + address, "sudo -n python3 -"]
            try:
                result = subprocess.run(command, input=REMOTE_PROBE.encode(), capture_output=True, timeout=25)
            except subprocess.TimeoutExpired:
                result = None
            if result is not None and result.returncode == 0:
                return decode_response(result.stdout)
        time.sleep(10)
    raise ProbeError("capacity_ssh_or_cloud_init_timeout")


def probe(token: str) -> None:
    name = identity()
    state = state_path()
    if state.exists():
        raise ProbeError("capacity_state_already_exists")
    offer = validate_offer(token)
    servers = read_resource(token, "servers")
    if not summarize("servers", servers)["complete"]:
        raise ProbeError("capacity_inventory_incomplete")
    if any(item.get("name", "").startswith("analyst-ci-") for item in servers["servers"]):
        raise ProbeError("earlier_capacity_vm_requires_cleanup")
    print("TIMEWEB_CAPACITY_OFFER=" + json.dumps(offer, sort_keys=True), flush=True)
    # Persist identity before POST: cleanup can recover an ambiguous create response.
    state.write_text(json.dumps({"name": name, "server_id": None}), encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix=name + "-", dir=os.environ["RUNNER_TEMP"]) as folder:
        root = Path(folder)
        generate_key(root / "client")
        generate_key(root / "host")
        host_public = (root / "host.pub").read_text().strip()
        body = {
            "name": name, "hostname": name, "comment": OWNER_MARKER,
            "preset_id": PRESET_ID, "os_id": OS_ID, "project_id": PROJECT_ID,
            "cloud_init": cloud_config((root / "client.pub").read_text().strip(),
                                       (root / "host").read_text(), host_public),
        }
        server = owned_server(request(token, "POST", "/api/v1/servers", body), name)
        state.write_text(json.dumps({"name": name, "server_id": server["id"]}), encoding="utf-8")
        print("TIMEWEB_CAPACITY_CREATED=" + str(server["id"]), flush=True)
        report = wait_probe(token, server["id"], name, root, host_public)
        print("TIMEWEB_CAPACITY_HARDWARE=" + json.dumps(report, sort_keys=True), flush=True)
        if report.get("kvm_api_version") != 12:
            raise ProbeError("capacity_nested_kvm_unavailable")


def delete_and_verify(token: str, server_id: int) -> None:
    path = f"/api/v1/servers/{server_id}"
    request(token, "DELETE", path)
    # A deletion acknowledgement can require Telegram confirmation; verify absence.
    for _ in range(6):
        try:
            request(token, "GET", path)
        except ProbeError as error:
            if str(error) == "timeweb_http_404":
                return
            raise
        time.sleep(5)
    raise ProbeError("capacity_deletion_not_confirmed")


def cleanup(token: str) -> None:
    state = state_path()
    if not state.exists():
        print("TIMEWEB_CAPACITY_CLEANUP=no_create_attempt", flush=True)
        return
    record = decode_response(state.read_bytes())
    name = identity()
    if record.get("name") != name:
        raise ProbeError("capacity_cleanup_identity_mismatch")
    collection = read_resource(token, "servers")
    if not summarize("servers", collection)["complete"]:
        raise ProbeError("capacity_cleanup_inventory_incomplete")
    matches = [item for item in collection["servers"] if item.get("name") == name]
    if len(matches) > 1:
        raise ProbeError("capacity_cleanup_ambiguous")
    if matches:
        server = owned_server({"server": matches[0]}, name)
        if record.get("server_id") not in (None, server["id"]):
            raise ProbeError("capacity_cleanup_id_mismatch")
        delete_and_verify(token, server["id"])
    state.unlink()
    print("TIMEWEB_CAPACITY_CLEANUP=verified_absent", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("probe", "cleanup"))
    command = parser.parse_args().command
    try:
        token = validated_token(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        if command == "probe":
            probe(token)
        else:
            cleanup(token)
    except (ProbeError, OSError, subprocess.SubprocessError) as error:
        code = str(error) if isinstance(error, ProbeError) else type(error).__name__
        print("TIMEWEB_CAPACITY_ERROR=" + code, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
