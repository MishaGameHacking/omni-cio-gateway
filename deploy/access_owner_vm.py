"""Temporary administrative access to the one verified new VM; no VM creation."""
import json
import hashlib
import io
import ipaddress
import os
import re
import shlex
import socket
import ssl
import sys
import subprocess
import tempfile
import tarfile
import time
from pathlib import Path
import urllib.error
import urllib.request
import uuid

import prepare_owner_vm as prepare

SERVER_ID = 9407735
EXPECTED_IP = "201.34.156.98"
KEY_NAME = "analyst-ai-install-20261023"
PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM7lcv6ujGptd74KPdQGz3jCsZoV51WLNePFGRyrfit7 analyst-ai-install-20261023"
HOST_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPsWdiuF70XIWeWMiDBFvJF51PUVKnggvLcKk8JUOHSf"


def request(token, method, path, data=None, *, api_version=1):
    allowed = method == "GET" and path in {"/ssh-keys", "/floating-ips", f"/servers/{SERVER_ID}", f"/projects/{prepare.PROJECT}/resources"}
    allowed |= method == "POST" and path in {"/ssh-keys", "/floating-ips", f"/servers/{SERVER_ID}/ssh-keys"}
    allowed |= method == "POST" and re.fullmatch(r"/floating-ips/[a-f0-9-]{36}/bind", path) is not None
    allowed |= method in {"GET", "POST"} and path == "/domains/" + prepare.HOST + "/dns-records"
    allowed |= method == "PATCH" and path == "/domains/" + prepare.HOST + "/dns-records/95034169"
    allowed |= method == "DELETE" and path == "/domains/" + prepare.HOST + "/dns-records/95034169"
    allowed |= method == "DELETE" and re.fullmatch(r"/(?:servers/" + str(SERVER_ID) + r"/)?ssh-keys/[1-9]\d*", path) is not None
    if not allowed:
        raise prepare.ProbeError("unapproved_access_endpoint")
    if api_version != 1 and not (api_version == 2 and method == "PATCH" and path == "/domains/" + prepare.HOST + "/dns-records/95034169"):
        raise prepare.ProbeError("unapproved_api_version")
    req = urllib.request.Request("https://api.timeweb.cloud/api/v" + str(api_version) + path, method=method,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Authorization": "Bearer " + token, "Accept": "application/json", "Content-Type": "application/json"})
    try:
        opener = urllib.request.build_opener(prepare.NoRedirect(), urllib.request.HTTPSHandler(context=prepare.verified_ssl_context()))
        with opener.open(req, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        print("OWNER_API_FAILURE=" + json.dumps({"method": method, "version": api_version, "path": path, "status": error.code,
            **prepare.cloud.error_details(error.read(2 * 1024 * 1024 + 1))}), flush=True)
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


def ensure_domain_dns(token, address):
    existing = prepare.domain_api(token, "GET")
    domain = {} if existing is None else existing.get("domain", {})
    if domain.get("is_technical") is not True or domain.get("linked_ip") not in {None, address}:
        raise prepare.ProbeError("expected_new_technical_domain_changed")
    path = "/domains/" + prepare.HOST + "/dns-records"

    def roots():
        document = request(token, "GET", path)
        records = document.get("dns_records")
        if not isinstance(records, list) or document.get("meta", {}).get("total") != len(records):
            raise prepare.ProbeError("incomplete_domain_dns_inventory")
        result = [row for row in records if row.get("data", {}).get("subdomain") in {None, "", "@", prepare.HOST, prepare.HOST + "."}
                  and row.get("type") in {"A", "AAAA", "CNAME"}]
        print("OWNER_DOMAIN_ADDRESS_RECORDS=" + json.dumps(result), flush=True)
        return result

    records = roots()
    if not records:
        request(token, "POST", path, {"type": "A", "subdomain": prepare.HOST, "value": address, "ttl": 300})
        records = roots()
    if len(records) != 1 or records[0].get("type") != "A" or records[0].get("data", {}).get("value") != address:
        raise prepare.ProbeError("domain_address_conflict_no_existing_record_changed")
    print("OWNER_DOMAIN_DNS_CONFIGURED=" + prepare.HOST, flush=True)


def verify_prepared_server(command, address):
    archive = subprocess.check_output(["git", "archive", "--format=tar.gz", prepare.SOURCE, "backend", "deploy"], cwd=prepare.ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        expected = {item.name: hashlib.sha256(source.extractfile(item).read()).hexdigest()
                    for item in source.getmembers() if item.isfile()}
    script = '''import hashlib,json,os,socket,ssl,stat,subprocess,sys,time
from pathlib import Path
root=Path("/root/analyst-ai-source")
expected=json.load(sys.stdin)
for name,digest in expected.items():
    path=root/name
    assert path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,"source_mismatch"
for path,mode in ((root,0o700),(Path("/root/analyst-ai-enrollment.json"),0o600)):
    info=path.lstat()
    assert info.st_uid==0 and stat.S_IMODE(info.st_mode)==mode and not path.is_symlink(),"private_permissions_mismatch"
sys.path.insert(0,str(root/"deploy"))
import install_owner_backend as installer
values=installer.load_config(enrollment=True)
installer.source_files()
installer.check_target()
report={"source_files_verified":len(expected),"private_permissions_verified":True,"empty_install_target_verified":True}
for name,command in (("telegram_route",["ip","route","get","149.154.167.99"]),("output_firewall",["iptables","-S","OUTPUT"]),("nft_rules",["nft","list","ruleset"])):
    try:
        result=subprocess.run(command,capture_output=True,text=True,timeout=10)
        report[name]={"exit":result.returncode,"output":result.stdout[:8000]}
    except OSError as error:
        report[name]={"error":type(error).__name__}
try:
    installer.check_address(values)
    report["vm_dns_and_local_ip_verified"]=True
except (installer.InstallError,OSError) as error:
    report["vm_dns_and_local_ip_verified"]=False
    report["address_error"]=str(error)
report["outbound_tls_checks"]=[]
for hostname in ("oauth.telegram.org","api.timeweb.cloud","pypi.org"):
    try:
        endpoints=socket.getaddrinfo(hostname,443,type=socket.SOCK_STREAM)
    except OSError as error:
        report["outbound_tls_checks"].append({"hostname":hostname,"dns_error":type(error).__name__,"errno":error.errno})
        continue
    seen=set()
    for family,kind,protocol,_,endpoint in endpoints:
        if endpoint[0] in seen or len(seen)>=4:
            continue
        seen.add(endpoint[0])
        result={"hostname":hostname,"address":endpoint[0],"family":int(family)}
        started=time.monotonic()
        try:
            with socket.socket(family,kind,protocol) as raw:
                raw.settimeout(12)
                raw.connect(endpoint)
                result["tcp_connected"]=True
                with ssl.create_default_context().wrap_socket(raw,server_hostname=hostname) as conn:
                    result["tls"]=conn.version()
                    if hostname=="oauth.telegram.org":
                        report["telegram_direct_tls"]=conn.version()
        except (OSError,ssl.SSLError) as error:
            result["error"]=type(error).__name__
            result["errno"]=error.errno
        result["seconds"]=round(time.monotonic()-started,2)
        report["outbound_tls_checks"].append(result)
print(json.dumps(report))
'''
    report = json.loads(prepare.remote(command, "python3 -c " + shlex.quote(script), json.dumps(expected).encode(), timeout=180))
    try:
        addresses = sorted({row[4][0] for row in socket.getaddrinfo(prepare.HOST, 443, type=socket.SOCK_STREAM)})
    except OSError as error:
        addresses = []
        report["runner_dns_error"] = type(error).__name__
    report["runner_dns_addresses"] = addresses
    print("OWNER_PREPARATION_VERIFIED=" + json.dumps(report), flush=True)
    if addresses != [address] or not report.get("vm_dns_and_local_ip_verified") or not report.get("telegram_direct_tls"):
        raise prepare.ProbeError("live_install_prerequisite_not_verified")


def develop_backend(command):
    development_source = "79be182168e21ae8248e0e0dfa6deb0abfbacbcf"
    archive = subprocess.check_output(["git", "archive", "--format=tar.gz", development_source], cwd=prepare.ROOT)
    materialize = '''import hashlib,io,json,pathlib,sys,tarfile
data=sys.stdin.buffer.read()
root=pathlib.Path("/root/analyst-ai-development-79be1821")
assert not root.is_symlink()
with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as source:
    entries=source.getmembers()
    assert all(item.isdir() or item.isfile() for item in entries)
    if not root.exists():
        root.mkdir(mode=0o700)
        source.extractall(root,filter="data")
    count=0
    for item in entries:
        if item.isfile():
            path=root/item.name
            assert path.resolve().is_relative_to(root) and path.is_file() and not path.is_symlink()
            assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(source.extractfile(item).read()).digest()
            count+=1
print(json.dumps({"development_source":"79be182168e21ae8248e0e0dfa6deb0abfbacbcf","verified_files":count,"archive_sha256":hashlib.sha256(data).hexdigest()}))
'''
    materialized = prepare.remote(command, "python3 -c " + shlex.quote(materialize), archive, timeout=120)
    print("OWNER_TIMEWEB_SOURCE=" + materialized.decode().strip(), flush=True)
    script = '''import json,os,pathlib,subprocess,sys,tempfile
root=pathlib.Path("/root/analyst-ai-development-79be1821")
venv=pathlib.Path("/root/analyst-ai-development-venv")
def run(args,**kwargs):
    result=subprocess.run(args,cwd=root,capture_output=True,text=True,**kwargs)
    if result.returncode:
        print(json.dumps({"phase":args[0:3],"exit":result.returncode,"output":(result.stdout+result.stderr)[-18000:]}),flush=True)
        raise SystemExit(result.returncode)
    return result.stdout+result.stderr
run(["apt-get","update","-qq"],timeout=300)
run(["apt-get","install","-y","python3-venv","nodejs"],env=dict(os.environ,DEBIAN_FRONTEND="noninteractive"),timeout=300)
print(json.dumps({"development_host":"timeweb-9408159","node_version":run(["node","--version"],timeout=30).strip()}),flush=True)
assert not venv.is_symlink()
if not venv.exists(): run(["python3","-m","venv",str(venv)],timeout=120)
python=str(venv/"bin/python")
run([python,"-m","pip","install","--disable-pip-version-check","--no-cache-dir","-r","backend/requirements-dev.txt"],timeout=480)
with tempfile.TemporaryDirectory(prefix="analyst-development-") as temp:
    env={"PATH":str(venv/"bin")+":/usr/bin:/bin","HOME":temp,"LANG":"C.UTF-8","PYTHONPATH":str(root),
         "TELEGRAM_CLIENT_ID":"123456","TELEGRAM_CLIENT_SECRET":"test-only","BACKEND_PUBLIC_URL":"https://example.invalid",
         "FERNET_KEY":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","ANALYSIS_SCHEDULER_ENABLED":"false",
         "AI_EXTERNAL_PROCESSING_APPROVED":"false","DATABASE_PATH":temp+"/tests.sqlite3"}
    sys.path.insert(0,str(root/".github/scripts"))
    import audit_python_sources
    audit=audit_python_sources.audit(root,[str(path.relative_to(root)) for path in root.rglob("*.py")])
    print(json.dumps({"development_host":"timeweb-9408159","python_source_audit":audit}),flush=True)
    assert not audit["failures"],"python_source_audit_failed"
    for phase,args in (("backend_tests",[python,"-m","pytest","backend/tests","-q"]),
                       ("ci_script_tests",[python,"-m","unittest","discover","-s",".github/scripts/tests","-p","test_*.py"]),
                       ("tool_tests",[python,"-m","unittest","discover","-s","tools/tests","-p","test_*.py"])):
        output=run(args,env=env,timeout=360)
        print(json.dumps({"development_host":"timeweb-9408159","development_source":"79be182168e21ae8248e0e0dfa6deb0abfbacbcf",phase:output[-6000:],"live_authentication_verified":False}),flush=True)
run([python,"-m","pip","check"],timeout=60)
'''
    result = subprocess.run(command + ["python3 -c " + shlex.quote(script)], capture_output=True, timeout=1200)
    # This command uses only synthetic test configuration. Preserve its bounded
    # JSON diagnostics instead of hiding pytest collection failures behind SSH.
    for line in result.stdout.decode(errors="replace").splitlines():
        if line.startswith("{"):
            report = json.loads(line)
            print("OWNER_TIMEWEB_DEVELOPMENT=" + json.dumps(report), flush=True)
    if result.returncode:
        raise prepare.ProbeError("timeweb_development_failed_" + str(result.returncode))


def stage_server(token, server, *, verify_only=False, development=False):
    address = prepare.cloud.public_ipv4(server)
    if address != EXPECTED_IP:
        raise prepare.ProbeError("server_address_changed")
    if verify_only:
        result = {"host": "oauth.telegram.org"}
        try:
            with socket.create_connection(("oauth.telegram.org", 443), timeout=15) as raw:
                with ssl.create_default_context().wrap_socket(raw, server_hostname="oauth.telegram.org") as connection:
                    result["tls"] = connection.version()
        except OSError as error:
            result["error"] = type(error).__name__
            result["errno"] = error.errno
        print("OWNER_RUNNER_TELEGRAM_TLS=" + json.dumps(result), flush=True)
    if not verify_only:
        values = [os.environ.get(k, "").strip() for k in ("TELEGRAM_CLIENT_ID", "TELEGRAM_CLIENT_SECRET")]
        if not all(values):
            raise prepare.ProbeError("telegram_credentials_missing")
        ensure_domain_dns(token, address)
    with tempfile.TemporaryDirectory(prefix="owner-stage-", dir=os.environ["RUNNER_TEMP"]) as root:
        folder = Path(root)
        prepare.cloud.generate_key(folder / "client")
        public = (folder / "client.pub").read_text().strip()
        name = "analyst-ai-stage-" + os.environ["GITHUB_RUN_ID"]
        created = request(token, "POST", "/ssh-keys", {"name": name, "body": public, "is_default": False})
        key = created.get("ssh_key", created.get("ssh-key", {}))
        if key.get("body", "").split()[:2] != public.split()[:2] or type(key.get("id")) is not int:
            raise prepare.ProbeError("stage_key_mismatch_reconcile_inventory")
        identifier = key["id"]
        print("OWNER_STAGE_KEY_ID=" + str(identifier), flush=True)
        attached = False
        try:
            request(token, "POST", f"/servers/{SERVER_ID}/ssh-keys", {"ssh_key_ids": [identifier]})
            attached = True
            command = prepare.ssh_command(folder, address, HOST_KEY)
            for attempt in range(12):
                try:
                    prepare.remote(command, "test $(id -u) = 0", timeout=12)
                    break
                except (prepare.ProbeError, subprocess.TimeoutExpired):
                    if attempt == 11:
                        raise prepare.ProbeError("stage_ssh_unreachable") from None
                    time.sleep(5)
            status = prepare.remote(command, "cloud-init status --wait", timeout=60)
            if b"status: done" not in status:
                raise prepare.ProbeError("cloud_init_not_done")
            if verify_only:
                verify_prepared_server(command, address)
                if development:
                    develop_backend(command)
            else:
                report = prepare.stage(command, address, *values)
                print("OWNER_VM_PREPARED=" + json.dumps({"id": SERVER_ID, "ip": address, "hostname": prepare.HOST,
                    "backend_started": False, "owner_enrollment_required": True, **report}), flush=True)
        finally:
            if attached:
                request(token, "DELETE", f"/servers/{SERVER_ID}/ssh-keys/{identifier}")
            request(token, "DELETE", f"/ssh-keys/{identifier}")
            print("OWNER_STAGE_KEY=removed", flush=True)


def run(mode):
    if mode not in {"inspect", "connect", "attach", "stage", "verify", "develop", "cleanup"}:
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
    if mode in {"stage", "verify", "develop"}:
        stage_server(token, server, verify_only=mode != "stage", development=mode == "develop")
        return
    if mode == "connect":
        connect_ipv4(token, server)
    document = request(token, "GET", "/ssh-keys")
    if mode == "inspect":
        domain = prepare.domain_api(token, "GET")
        print("OWNER_DOMAIN_OBSERVED=" + json.dumps(None if domain is None else {
            k: domain.get("domain", {}).get(k) for k in ("fqdn", "idn_name", "is_technical", "linked_ip")}), flush=True)
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
    if mode == "stage":
        stage_server(token, server)
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
    except (prepare.ProbeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("OWNER_VM_ACCESS_ERROR=" + (str(error) if isinstance(error, prepare.ProbeError) else type(error).__name__), flush=True)
        sys.exit(1)
