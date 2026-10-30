"""Activate only the isolated public-document model on the resized existing host."""
from contextlib import closing
from datetime import datetime, timezone
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request

SOURCE = "853090e11dcefef693366159c97316e55045c4c9"
MODEL_SHA = "0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0"
LOCAL = Path("/opt/analyst-local-ai")
UNIT = Path("/etc/systemd/system/analyst-local-research.service")
SERVICE = "analyst-local-research.service"
DATABASE = Path("/var/lib/analyst-ai/backend.db")
SOCKET = Path("/run/analyst-local-ai/research.sock")
FILES = {
    "backend/local_research.py": "13560fbce8557673d892cacc1a5f447c7f4255e4abbbc131b0259be33e7c284c",
    "deploy/local_research_worker.py": "73b0b2d488b2306ef9e4631bca019f8a966077b6674b08ef0734f2409f94f972",
    "deploy/analyst-local-research.service": "9161820a769464b667edd39d1bfd358f24dc34bef1cea56f7e92f2ab7a112f97",
}
HOSTS = {"moex_reports": {"www.moex.com", "moex.com", "fs.moex.com"},
         "nornickel_reports": {"nornickel.ru", "www.nornickel.ru"},
         "gazprom_reports": {"www.gazprom.ru", "gazprom.ru"}}
CLIENT = '''import json,sys,time
sys.path.insert(0,"/opt/analyst-local-ai/backend")
import local_research
row=json.load(sys.stdin)
started=time.monotonic()
result=local_research.select_public_fragments(row["title"],row["body"],enabled=True)
print(json.dumps({"status":result["status"],"trade_permission":result["trade_permission"],
 "source_sha256":result.get("source_sha256"),"model_sha256":result.get("model_sha256"),
 "excerpt_count":len(result.get("excerpts",[])),"seconds":round(time.monotonic()-started,3)}))
'''


def need(value, code):
    if not value:
        raise RuntimeError(code)


def regular(path, maximum=1024*1024):
    need(path.is_file() and not path.is_symlink() and path.resolve(strict=True) == path,
         "activation_path_invalid")
    info = path.stat()
    need(info.st_uid == 0 and info.st_nlink == 1 and info.st_mode & 0o022 == 0
         and info.st_size <= maximum, "activation_file_metadata_invalid")
    return path.read_bytes()


def command(args, *, data=None, timeout=20):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout,
        env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin", "LANG":"C.UTF-8"})
    need(result.returncode == 0 and len(result.stdout) <= 65536, "activation_command_failed")
    return result.stdout


def health():
    with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=6) as response:
        need(response.status == 200, "application_health_unavailable")


def account_valid(account, group):
    return (account.pw_uid > 0 and account.pw_gid == group.gr_gid
            and account.pw_dir == "/nonexistent" and account.pw_shell in {"/usr/sbin/nologin", "/sbin/nologin"})


def ensure_account():
    group = grp.getgrnam("analyst-ai")
    try:
        account = pwd.getpwnam("analyst-local-ai")
    except KeyError:
        command(["/usr/sbin/useradd", "--system", "--no-create-home", "--home-dir", "/nonexistent",
                 "--shell", "/usr/sbin/nologin", "--gid", "analyst-ai", "analyst-local-ai"])
        account = pwd.getpwnam("analyst-local-ai")
    need(account_valid(account, group), "local_account_identity_invalid")


def public_document(db, now):
    rows = db.execute("""SELECT p.source_id,p.url,o.title,o.body,p.object_sha
        FROM osint_publications_v1 p JOIN osint_objects_v1 o ON o.sha=p.object_sha
        JOIN osint_originals_v1 original ON original.sha=p.raw_sha
        WHERE p.kind='report' AND p.primary_source=1 AND p.expires_at>?
        AND original.media_type='application/pdf' AND length(o.body) BETWEEN 1 AND 240000
        ORDER BY p.last_changed DESC LIMIT 5""", (now,)).fetchall()
    for source, url, title, body, checksum in rows:
        parsed = urllib.parse.urlsplit(url)
        if (source not in HOSTS or parsed.scheme != "https" or parsed.hostname not in HOSTS[source]
                or parsed.username or parsed.password or parsed.port not in (None,443)):
            continue
        if hashlib.sha256((title + "\0" + body).encode()).hexdigest() != checksum:
            continue
        if not 1 <= len(title) <= 400:
            continue
        # Retain complete source lines only. The selector marks bounded coverage.
        lines, used = [], 0
        for line in body.splitlines():
            if used + len(line) + 1 > 120000:
                break
            lines.append(line)
            used += len(line) + 1
        excerpt = "\n".join(lines)
        if excerpt.strip():
            return {"title":title,"body":excerpt,"original_object_sha256":checksum,"source_id":source}
    raise RuntimeError("public_report_unavailable")


def smoke(document):
    # The client has no inherited secrets. The model user cannot read the DB.
    public = {key:document[key] for key in ("title","body")}
    raw = command(["/usr/sbin/runuser", "-u", "analyst-ai", "--", "/usr/bin/python3", "-I", "-c", CLIENT],
                  data=json.dumps(public,ensure_ascii=False).encode(), timeout=25)
    result = json.loads(raw)
    expected = hashlib.sha256((document["title"] + "\n" + document["body"]).encode()).hexdigest()
    need(result.get("status") == "source_excerpt_selection" and result.get("trade_permission") is False
         and result.get("model_sha256") == MODEL_SHA and result.get("source_sha256") == expected,
         "local_inference_failed")
    return result


def activate(envelope):
    need(os.getuid() == 0 and envelope.get("payload") == {"source_commit":SOURCE}, "activation_scope_invalid")
    memory = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    need(memory >= 7680 * 1024**2 and (os.cpu_count() or 0) >= 4, "activation_host_too_small")
    for relative, checksum in FILES.items():
        need(hashlib.sha256(regular(LOCAL / relative)).hexdigest() == checksum, "activation_source_changed")
    preparation = json.loads(regular(LOCAL / "preparation-receipt.json",65536))
    need(preparation.get("status") == "prepared" and preparation.get("source_commit") == SOURCE
         and preparation.get("model_sha256") == MODEL_SHA, "activation_weights_unverified")
    health()
    need(DATABASE.is_file() and not DATABASE.is_symlink() and DATABASE.resolve(strict=True) == DATABASE,
         "activation_corpus_path_invalid")
    with closing(sqlite3.connect(DATABASE.as_uri()+"?mode=ro",uri=True,timeout=3)) as db:
        db.execute("PRAGMA query_only=ON")
        document = public_document(db,int(time.time()))
    ensure_account()
    unit = regular(LOCAL / "deploy/analyst-local-research.service")
    existed = UNIT.exists() or UNIT.is_symlink()
    if existed:
        need(regular(UNIT) == unit, "activation_existing_unit_changed")
    else:
        with UNIT.open("xb") as output:
            os.fchmod(output.fileno(),0o644)
            output.write(unit)
    try:
        command(["/usr/bin/systemctl","daemon-reload"])
        command(["/usr/bin/systemctl","enable","--now",SERVICE],timeout=75)
        deadline=time.monotonic()+90
        while not SOCKET.is_socket():
            need(time.monotonic()<deadline,"activation_socket_timeout")
            state=command(["/usr/bin/systemctl","show",SERVICE,"--property=ActiveState","--value"]).decode().strip()
            need(state not in {"failed","inactive"},"activation_worker_stopped")
            time.sleep(2)
        result=smoke(document)
        command(["/usr/bin/systemctl","is-active","--quiet",SERVICE])
        health()
    except BaseException:
        command(["/usr/bin/systemctl","disable","--now",SERVICE],timeout=25)
        if not existed:
            UNIT.unlink()
            command(["/usr/bin/systemctl","daemon-reload"])
        raise
    receipt={"status":"local_worker_active","observed_at":datetime.now(timezone.utc).isoformat(),
        "server_id":9417611,"source_commit":SOURCE,"model_sha256":MODEL_SHA,
        "host_memory_mib":memory//1024**2,"host_cpu_count":os.cpu_count(),
        "public_report_source":document["source_id"],"public_report_object_sha256":document["original_object_sha256"],
        "smoke":result,"broker_called":False,"paid_inference_called":False,
        "application_source_changed":False,"application_local_route_enabled":False,
        "model_network_allowed":False,"model_broker_credentials":False}
    target=LOCAL/"activation-receipt.json"
    if target.exists() or target.is_symlink():
        regular(target,65536)
    target.write_text(json.dumps(receipt,indent=2)+"\n")
    print("LOCAL_RESEARCH_ACTIVE="+json.dumps(receipt),flush=True)


if __name__ == "__main__":
    try:
        activate(ENVELOPE)
    except Exception as error:
        allowed={"activation_host_too_small","public_report_unavailable","local_inference_failed",
                 "activation_socket_timeout","activation_worker_stopped","activation_existing_unit_changed"}
        code=str(error) if type(error) is RuntimeError and str(error) in allowed else "local_activation_failed"
        print(json.dumps({"status":"failed","code":code,"application_source_changed":False}),flush=True)
        raise SystemExit(1) from None
