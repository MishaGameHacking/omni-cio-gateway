"""Check one replacement after cheaper offers failed availability or Telegram access."""
import json
import ipaddress
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import access_owner_vm as access
import prepare_owner_vm as prepare

OLD_SERVER = 9407735
OLD_IP_ID = "4121856b-33c2-457a-b328-8db251e9dd20"
NAME = "analyst-ai-owner-route-20261023"
CONFIGURATION = {"configurator_id": 153, "cpu": 1, "ram": 1024, "disk": 15360}
MARKER = "Analyst AI replacement for verified Telegram route failure 2026-10-23"


def validate(token):
    prepare.cloud.PRESET_ID = None
    prepare.cloud.OWNER_MARKER = prepare.MARKER
    old = prepare.owned_server(access.request(token, "GET", f"/servers/{OLD_SERVER}"))
    if old["id"] != OLD_SERVER or prepare.cloud.public_ipv4(old) != "201.34.156.98":
        raise prepare.ProbeError("original_vm_identity_changed")
    inventory = prepare.read_resource(token, "servers")
    if not prepare.summarize("servers", inventory)["complete"] or {row["id"] for row in inventory["servers"]} != {OLD_SERVER}:
        raise prepare.ProbeError("reconcile_existing_servers_before_replacement")
    project = access.request(token, "GET", f"/projects/{prepare.PROJECT}/resources")
    if not any(row.get("id") == OLD_SERVER for row in project.get("servers", [])):
        raise prepare.ProbeError("original_vm_project_changed")
    addresses = access.request(token, "GET", "/floating-ips")
    if addresses.get("meta", {}).get("total") != 1 or len(addresses.get("ips", [])) != 1:
        raise prepare.ProbeError("reconcile_addresses_before_replacement")
    ip = addresses["ips"][0]
    if ip.get("id") != OLD_IP_ID or ip.get("resource_id") != OLD_SERVER:
        raise prepare.ProbeError("original_address_changed")
    request = urllib.request.Request("https://api.timeweb.cloud/api/v1/configurator/servers", headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    opener = urllib.request.build_opener(prepare.NoRedirect(), urllib.request.HTTPSHandler(context=prepare.verified_ssl_context()))
    with opener.open(request, timeout=30) as response:
        rows = prepare.decode_response(response.read(2 * 1024 * 1024 + 1))["server_configurators"]
    offer, = [row for row in rows if row.get("id") == CONFIGURATION["configurator_id"]]
    sizes = tuple(CONFIGURATION[k] for k in ("cpu", "ram", "disk"))
    prices = offer["prices"]
    price = sizes[0] * prices["cpu"] + sizes[1] / 1024 * prices["ram"] + sizes[2] / 1024 * prices["disk"]
    if offer.get("location") != "nl-1" or price != 1620 or sizes != tuple(offer["requirements"][k + "_min"] for k in ("cpu", "ram", "disk")):
        raise prepare.ProbeError("replacement_offer_or_price_changed")
    print("OWNER_REPLACEMENT_OFFER=" + json.dumps({**CONFIGURATION, "location": "nl-1", "monthly_vm_rub": price}), flush=True)


def remove_ip(token, identifier, server_id):
    rows = access.request(token, "GET", "/floating-ips")
    if rows.get("meta", {}).get("total") != len(rows.get("ips", [])):
        raise prepare.ProbeError("replacement_ip_cleanup_inventory_incomplete")
    matches = [row for row in rows.get("ips", []) if row.get("id") == identifier]
    if not matches:
        return
    if len(matches) != 1 or matches[0].get("resource_id") not in {None, server_id}:
        raise prepare.ProbeError("replacement_ip_cleanup_identity_changed")
    req = urllib.request.Request("https://api.timeweb.cloud/api/v1/floating-ips/" + str(uuid.UUID(identifier)), method="DELETE", headers={"Authorization": "Bearer " + token})
    opener = urllib.request.build_opener(prepare.NoRedirect(), urllib.request.HTTPSHandler(context=prepare.verified_ssl_context()))
    with opener.open(req, timeout=30) as response:
        if response.status not in {200, 204}:
            raise prepare.ProbeError("replacement_ip_cleanup_failed")
    rows = access.request(token, "GET", "/floating-ips")
    if rows.get("meta", {}).get("total") != len(rows.get("ips", [])) or any(row.get("id") == identifier for row in rows.get("ips", [])):
        raise prepare.ProbeError("replacement_ip_cleanup_not_verified")


def run():
    token = prepare.validated_token(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
    validate(token)
    prepare.NAME, prepare.MARKER = NAME, MARKER
    prepare.CONFIGURATION, prepare.CONFIG_LOCATION = CONFIGURATION, "nl-1"
    prepare.cloud.OWNER_MARKER = MARKER
    with tempfile.TemporaryDirectory(prefix="owner-route-", dir=os.environ["RUNNER_TEMP"]) as root:
        folder = Path(root)
        for name in ("client", "host"):
            prepare.cloud.generate_key(folder / name)
        client, host = [(folder / (name + ".pub")).read_text().strip() for name in ("client", "host")]
        config = {"users": [{"name": "root", "lock_passwd": True, "ssh_authorized_keys": [client]}], "ssh_pwauth": False, "disable_root": False, "ssh_deletekeys": True,
            "ssh_keys": {"ed25519_private": (folder / "host").read_text(), "ed25519_public": host}, "ssh": {"emit_keys_to_console": False}, "no_ssh_fingerprints": True,
            "runcmd": [["systemctl", "restart", "ssh"]]}
        server = prepare.owned_server(prepare.cloud.request(token, "POST", "/api/v1/servers", {"name": NAME, "hostname": NAME, "comment": MARKER, "configuration": CONFIGURATION,
            "os_id": 99, "project_id": prepare.PROJECT, "cloud_init": "#cloud-config\n" + json.dumps(config) + "\n"}))
        server_id = server["id"]
        access.SERVER_ID = server_id
        print("OWNER_REPLACEMENT_CREATED=" + json.dumps({"id": server_id, "host_key": host, "zone": server.get("availability_zone")}), flush=True)
        keep, ip_id, command = False, None, None
        try:
            address = prepare.cloud.public_ipv4(server)
            if not address:
                zone = server.get("availability_zone", "")
                if not re.fullmatch(r"[a-z]{2,8}-[1-9][0-9]*", zone):
                    raise prepare.ProbeError("replacement_zone_mismatch")
                ip = access.request(token, "POST", "/floating-ips", {"is_ddos_guard": False, "availability_zone": zone})["ip"]
                ip_id = str(uuid.UUID(ip["id"]))
                print("OWNER_REPLACEMENT_IP_CREATED=" + json.dumps({"id": ip_id, "ip": ip["ip"]}), flush=True)
                if ip.get("availability_zone") != zone or ip.get("is_ddos_guard") is not False or not ipaddress.IPv4Address(ip["ip"]).is_global:
                    raise prepare.ProbeError("replacement_ip_attributes_changed")
                access.request(token, "POST", f"/floating-ips/{ip_id}/bind", {"resource_type": "server", "resource_id": server_id})
            command, address = prepare.ready(token, server_id, folder, host)
            script = '''import json,socket,ssl,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
url="https://oauth.telegram.org/.well-known/jwks.json"
opener=urllib.request.build_opener(NoRedirect(),urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
with opener.open(url,timeout=20) as response:
    result=json.loads(response.read(131073))
    assert response.status==200 and isinstance(result.get("keys"),list) and result["keys"],"invalid_public_jwks"
    print(json.dumps({"telegram_jwks_https":True,"public_key_count":len(result["keys"])}))
'''
            evidence = json.loads(prepare.remote(command, "python3 -c " + shlex.quote(script), timeout=30))
            keep = evidence.get("telegram_jwks_https") is True
            print("OWNER_REPLACEMENT_REACHABILITY=" + json.dumps({"id": server_id, "ip": address, "ip_id": ip_id, **evidence}), flush=True)
        finally:
            if keep:
                script = "python3 -c 'import pathlib,sys; p=pathlib.Path(\"/root/.ssh/authorized_keys\"); k=sys.stdin.read().strip(); p.write_text(\"\\n\".join(x for x in p.read_text().splitlines() if k not in x)+\"\\n\")'"
                prepare.remote(command, script, client.encode())
                print("OWNER_REPLACEMENT_TEMPORARY_ACCESS=removed", flush=True)
            else:
                current = prepare.owned_server(prepare.cloud.request(token, "GET", f"/api/v1/servers/{server_id}"))
                if current["id"] != server_id:
                    raise prepare.ProbeError("replacement_cleanup_identity_changed")
                prepare.cloud.request(token, "DELETE", f"/api/v1/servers/{server_id}")
                for _ in range(24):
                    inventory = prepare.read_resource(token, "servers")
                    if prepare.summarize("servers", inventory)["complete"] and not any(row["id"] == server_id for row in inventory["servers"]):
                        break
                    time.sleep(5)
                else:
                    raise prepare.ProbeError("replacement_delete_not_confirmed")
                if ip_id:
                    remove_ip(token, ip_id, server_id)
                print("OWNER_REPLACEMENT_CLEANUP=server_and_new_address_removed", flush=True)


if __name__ == "__main__":
    try:
        run()
    except (prepare.ProbeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("OWNER_REPLACEMENT_ERROR=" + (str(error) if isinstance(error, prepare.ProbeError) else type(error).__name__), flush=True)
        sys.exit(1)
