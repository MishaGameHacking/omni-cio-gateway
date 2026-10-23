"""Temporary administrative access to the one verified new VM; no VM creation."""
import json
import ipaddress
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

import prepare_owner_vm as prepare

SERVER_ID = 9407735
KEY_NAME = "analyst-ai-install-20261023"
PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM7lcv6ujGptd74KPdQGz3jCsZoV51WLNePFGRyrfit7 analyst-ai-install-20261023"


def request(token, method, path, data=None):
    allowed = method == "GET" and path in {"/ssh-keys", "/floating-ips", f"/servers/{SERVER_ID}", f"/projects/{prepare.PROJECT}/resources"}
    allowed |= method == "POST" and path in {"/ssh-keys", "/floating-ips", f"/servers/{SERVER_ID}/ssh-keys"}
    allowed |= method == "POST" and re.fullmatch(r"/floating-ips/[a-f0-9-]{36}/bind", path) is not None
    allowed |= method == "DELETE" and re.fullmatch(r"/(?:servers/9407735/)?ssh-keys/[1-9]\d*", path) is not None
    if not allowed:
        raise prepare.ProbeError("unapproved_access_endpoint")
    req = urllib.request.Request("https://api.timeweb.cloud/api/v1" + path, method=method,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Authorization": "Bearer " + token, "Accept": "application/json", "Content-Type": "application/json"})
    try:
        opener = urllib.request.build_opener(prepare.NoRedirect(), urllib.request.HTTPSHandler(context=prepare.verified_ssl_context()))
        with opener.open(req, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        raise prepare.ProbeError("access_http_" + str(error.code)) from None
    except OSError:
        raise prepare.ProbeError("access_transport_failed_reconcile_before_retry") from None
    return prepare.decode_response(raw) if raw else {}


def connect_ipv4(token, server):
    if prepare.cloud.public_ipv4(server):
        return
    inventory = request(token, "GET", "/floating-ips")
    if inventory.get("ips") != [] or inventory.get("meta", {}).get("total") != 0:
        raise prepare.ProbeError("reconcile_existing_addresses_before_allocation")
    if server.get("availability_zone") != "nsk-1":
        raise prepare.ProbeError("unexpected_server_zone")
    address = request(token, "POST", "/floating-ips", {"is_ddos_guard": False, "availability_zone": "nsk-1"})["ip"]
    identifier = str(uuid.UUID(address["id"]))
    ip = str(ipaddress.IPv4Address(address["ip"]))
    print("OWNER_VM_IP_CREATED=" + json.dumps({"id": identifier, "ip": ip}), flush=True)
    if not ipaddress.IPv4Address(ip).is_global or address.get("availability_zone") != "nsk-1" or address.get("is_ddos_guard") is not False:
        raise prepare.ProbeError("allocated_ip_mismatch_reconcile_inventory")
    request(token, "POST", f"/floating-ips/{identifier}/bind", {"resource_type": "server", "resource_id": SERVER_ID})
    for _ in range(12):
        current = prepare.owned_server(request(token, "GET", f"/servers/{SERVER_ID}"))
        if prepare.cloud.public_ipv4(current) == ip:
            print("OWNER_VM_IP_BOUND=" + ip, flush=True)
            return
        time.sleep(5)
    raise prepare.ProbeError("ip_binding_not_yet_verified_no_second_allocation")


def run(mode):
    if mode not in {"inspect", "connect", "attach", "cleanup"}:
        raise prepare.ProbeError("invalid_access_mode")
    token = prepare.validated_token(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
    prepare.cloud.PRESET_ID = prepare.PRESET
    prepare.cloud.OWNER_MARKER = prepare.MARKER
    server = prepare.owned_server(request(token, "GET", f"/servers/{SERVER_ID}"))
    project = request(token, "GET", f"/projects/{prepare.PROJECT}/resources")
    if server["id"] != SERVER_ID or not any(x.get("id") == SERVER_ID for x in project.get("servers", [])):
        raise prepare.ProbeError("server_project_mismatch")
    print("OWNER_VM_OBSERVED=" + json.dumps({"id": SERVER_ID, "status": server.get("status"),
        "ip": prepare.cloud.public_ipv4(server), "location": server.get("location"),
        "cpu": server.get("cpu"), "ram": server.get("ram"), "availability_zone": server.get("availability_zone"),
        "network_types": [n.get("type") for n in server.get("networks", [])]}), flush=True)
    if mode == "connect":
        connect_ipv4(token, server)
    document = request(token, "GET", "/ssh-keys")
    if mode == "inspect":
        print("OWNER_KEY_RESPONSE_SHAPE=" + json.dumps({"keys": list(document), "meta": document.get("meta"),
            "list_lengths": {k: len(v) for k, v in document.items() if isinstance(v, list)}}), flush=True)
        addresses = request(token, "GET", "/floating-ips")
        print("OWNER_IP_INVENTORY=" + json.dumps({"meta": addresses.get("meta"),
            "ips": [{k: v.get(k) for k in ("id", "resource_id", "resource_type", "availability_zone")} for v in addresses.get("ips", [])]}), flush=True)
        return
    keys = document.get("ssh_keys")
    if not isinstance(keys, list) or document.get("meta", {}).get("total") != len(keys):
        raise prepare.ProbeError("incomplete_key_inventory")
    matching = [k for k in keys if k.get("name") == KEY_NAME]
    if len(matching) > 1:
        raise prepare.ProbeError("ambiguous_temporary_key")
    if not matching:
        if mode == "cleanup":
            print("OWNER_VM_TEMPORARY_KEY=already_absent", flush=True)
            return
        created = request(token, "POST", "/ssh-keys", {"name": KEY_NAME, "body": PUBLIC_KEY, "is_default": False})
        key = created.get("ssh_key", created.get("ssh-key", {}))
    else:
        key = matching[0]
    if key.get("body", "").split()[:2] != PUBLIC_KEY.split()[:2] or key.get("is_default") is not False:
        raise prepare.ProbeError("temporary_key_identity_mismatch")
    identifier = key.get("id")
    if type(identifier) is not int or identifier <= 0:
        raise prepare.ProbeError("invalid_temporary_key_id")
    print("OWNER_VM_TEMPORARY_KEY_ID=" + str(identifier), flush=True)
    if mode in {"attach", "connect"}:
        request(token, "POST", f"/servers/{SERVER_ID}/ssh-keys", {"ssh_key_ids": [identifier]})
        print("OWNER_VM_TEMPORARY_KEY=attached", flush=True)
    else:
        request(token, "DELETE", f"/servers/{SERVER_ID}/ssh-keys/{identifier}")
        request(token, "DELETE", f"/ssh-keys/{identifier}")
        print("OWNER_VM_TEMPORARY_KEY=removed", flush=True)


if __name__ == "__main__":
    try:
        run(sys.argv[1] if len(sys.argv) == 2 else "")
    except (prepare.ProbeError, OSError, ValueError, KeyError) as error:
        print("OWNER_VM_ACCESS_ERROR=" + (str(error) if isinstance(error, prepare.ProbeError) else type(error).__name__), flush=True)
        sys.exit(1)
