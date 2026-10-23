"""Adopt the verified NL VM and retire only this task's unused route-failed VM."""
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import access_owner_vm as access
import prepare_owner_vm as prepare
from replace_unreachable_vm import remove_ip

NEW_ID = 9408159
NEW_IP = "201.34.146.244"
NEW_HOST_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDpyNJRmtgaymzM1TT1t1DudEnPQ6eaoYLw7C5kPaJ9H"
OLD_ID = 9407735
OLD_IP = "201.34.156.98"
OLD_HOST_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPsWdiuF70XIWeWMiDBFvJF51PUVKnggvLcKk8JUOHSf"
OLD_IP_ID = "4121856b-33c2-457a-b328-8db251e9dd20"


def select_target(new):
    access.SERVER_ID = NEW_ID if new else OLD_ID
    access.EXPECTED_IP = NEW_IP if new else OLD_IP
    access.HOST_KEY = NEW_HOST_KEY if new else OLD_HOST_KEY
    prepare.NAME = "analyst-ai-owner-route-20261023" if new else "analyst-ai-owner-20261023"
    prepare.MARKER = ("Analyst AI replacement for verified Telegram route failure 2026-10-23" if new
                      else "Analyst AI owner installation 2026-10-23")
    prepare.CONFIGURATION = {"configurator_id": 153 if new else 19, "cpu": 1, "ram": 1024, "disk": 15360}
    prepare.CONFIG_LOCATION = "nl-1" if new else "ru-2"
    prepare.cloud.PRESET_ID = None
    prepare.cloud.OWNER_MARKER = prepare.MARKER


def verified_target(token):
    server = prepare.owned_server(access.request(token, "GET", f"/servers/{access.SERVER_ID}"))
    project = access.request(token, "GET", f"/projects/{prepare.PROJECT}/resources")
    if server["id"] != access.SERVER_ID or prepare.cloud.public_ipv4(server) != access.EXPECTED_IP or not any(row.get("id") == server["id"] for row in project.get("servers", [])):
        raise prepare.ProbeError("adoption_server_identity_changed")
    return server


def move_dns(token):
    domain = prepare.domain_api(token, "GET").get("domain", {})
    if domain.get("is_technical") is not True or domain.get("fqdn") != prepare.HOST or domain.get("linked_ip") is not None:
        raise prepare.ProbeError("adoption_domain_identity_changed")
    path = "/domains/" + prepare.HOST + "/dns-records"
    def exact_record():
        result = access.request(token, "GET", path)
        records = result.get("dns_records", [])
        print("OWNER_ADOPTION_DNS_INVENTORY=" + json.dumps({"meta": result.get("meta"), "count": len(records),
            "types": [row.get("type") for row in records], "address_records": [
                {"id": row.get("id"), "type": row.get("type"), "fqdn": row.get("fqdn"), "value": row.get("data", {}).get("value")}
                for row in records if row.get("type") in {"A", "AAAA", "CNAME"}]}), flush=True)
        if result.get("meta", {}).get("total") != len(records):
            raise prepare.ProbeError("adoption_dns_inventory_changed")
        addresses = [row for row in records if row.get("type") in {"A", "AAAA", "CNAME"} and row.get("fqdn") == prepare.HOST]
        if len(addresses) != 1:
            raise prepare.ProbeError("adoption_domain_address_conflict")
        row = addresses[0]
        if row.get("type") != "A" or row.get("fqdn") != prepare.HOST or type(row.get("id")) is not int:
            raise prepare.ProbeError("adoption_dns_record_changed")
        if row.get("data", {}).get("value") == OLD_IP and row["id"] != 95034169:
            raise prepare.ProbeError("original_dns_record_identity_changed")
        preserved = {item["id"]: json.dumps(item, sort_keys=True) for item in records if item.get("id") != row["id"]}
        return row.get("data", {}).get("value"), preserved
    current, preserved = exact_record()
    if current not in {OLD_IP, NEW_IP}:
        raise prepare.ProbeError("adoption_dns_address_changed")
    if current == OLD_IP:
        # Both documented update versions returned HTTP500 without changing
        # this task's A record. Replace only that verified record; preserve MX/TXT.
        access.request(token, "DELETE", path + "/95034169")
        access.request(token, "POST", path, {"type": "A", "subdomain": prepare.HOST, "value": NEW_IP, "ttl": 300})
    updated, remaining = exact_record()
    if updated != NEW_IP or remaining != preserved:
        raise prepare.ProbeError("adoption_dns_update_not_verified")
    print("OWNER_REPLACEMENT_DNS=" + json.dumps({"host": prepare.HOST, "ip": NEW_IP}), flush=True)


def retire_old(token):
    select_target(False)
    verified_target(token)
    with tempfile.TemporaryDirectory(prefix="owner-retire-", dir=os.environ["RUNNER_TEMP"]) as root:
        folder = Path(root)
        prepare.cloud.generate_key(folder / "client")
        public = (folder / "client.pub").read_text().strip()
        created = access.request(token, "POST", "/ssh-keys", {"name": "analyst-ai-retire-" + os.environ["GITHUB_RUN_ID"], "body": public, "is_default": False})
        key = created.get("ssh_key", created.get("ssh-key", {}))
        if type(key.get("id")) is not int or key.get("body", "").split()[:2] != public.split()[:2]:
            raise prepare.ProbeError("retirement_key_mismatch")
        identifier = key["id"]
        attached = False
        try:
            access.request(token, "POST", f"/servers/{OLD_ID}/ssh-keys", {"ssh_key_ids": [identifier]})
            attached = True
            command = prepare.ssh_command(folder, OLD_IP, OLD_HOST_KEY)
            for attempt in range(12):
                try:
                    prepare.remote(command, "test $(id -u) = 0", timeout=12)
                    break
                except (prepare.ProbeError, subprocess.TimeoutExpired):
                    if attempt == 11:
                        raise prepare.ProbeError("old_vm_retirement_inspection_unreachable") from None
                    time.sleep(5)
            script = '''import json,sys
from pathlib import Path
sys.path.insert(0,"/root/analyst-ai-source/deploy")
import install_owner_backend as installer
installer.check_target()
installer.source_files()
values=installer.load_config(enrollment=True)
assert values["EXPECTED_PUBLIC_IPV4"]=="201.34.156.98"
assert values["BACKEND_PUBLIC_URL"]=="https://analyst-ai-2941515.twc1.net"
assert not installer.INPUT_CONFIG.exists() and not installer.INPUT_CONFIG.is_symlink()
print("unused_fresh_install_target_verified")
'''
            output = prepare.remote(command, "python3 -c " + shlex.quote(script))
            if output.strip() != b"unused_fresh_install_target_verified":
                raise prepare.ProbeError("old_vm_unused_state_not_verified")
            print("OWNER_OLD_VM_UNUSED=verified_no_owner_binding_or_app_data", flush=True)
        finally:
            if attached:
                access.request(token, "DELETE", f"/servers/{OLD_ID}/ssh-keys/{identifier}")
            access.request(token, "DELETE", f"/ssh-keys/{identifier}")
            print("OWNER_RETIREMENT_KEY=removed", flush=True)
    verified_target(token)
    prepare.cloud.request(token, "DELETE", f"/api/v1/servers/{OLD_ID}")
    for _ in range(24):
        inventory = prepare.read_resource(token, "servers")
        if prepare.summarize("servers", inventory)["complete"] and not any(row["id"] == OLD_ID for row in inventory["servers"]):
            break
        time.sleep(5)
    else:
        raise prepare.ProbeError("old_vm_delete_not_verified")
    remove_ip(token, OLD_IP_ID, OLD_ID)
    print("OWNER_OLD_VM_RETIRED=" + json.dumps({"id": OLD_ID, "ip_id": OLD_IP_ID}), flush=True)


def run():
    token = prepare.validated_token(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
    select_target(True)
    verified_target(token)
    move_dns(token)
    access.run("stage")
    for _ in range(60):
        try:
            addresses = {row[4][0] for row in socket.getaddrinfo(prepare.HOST,443,type=socket.SOCK_STREAM)}
        except OSError:
            addresses = set()
        if addresses == {NEW_IP}:
            break
        time.sleep(5)
    else:
        raise prepare.ProbeError("new_dns_propagation_not_verified_old_vm_preserved")
    access.run("verify")
    retire_old(token)
    select_target(True)
    verified_target(token)
    print("OWNER_INSTALLATION_TARGET=" + json.dumps({"id": NEW_ID, "ip": NEW_IP, "host": prepare.HOST, "backend_started": False, "owner_enrollment_required": True}), flush=True)


if __name__ == "__main__":
    try:
        run()
    except (prepare.ProbeError,OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        print("OWNER_ADOPTION_ERROR=" + (str(error) if isinstance(error,prepare.ProbeError) else type(error).__name__), flush=True)
        sys.exit(1)
