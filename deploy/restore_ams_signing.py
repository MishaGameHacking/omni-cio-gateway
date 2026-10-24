import hashlib,json,os,pathlib,shlex,subprocess,sys,tempfile,time,urllib.request,urllib.error
sys.path[:0]=["deploy","tools"]
import prepare_owner_vm as p
import access_owner_vm as access
token=p.validated_token(os.environ["TIMEWEB_CLOUD_TOKEN"])
def api(method,path,body=None):
    req=urllib.request.Request("https://api.timeweb.cloud/api/v1"+path,method=method,data=None if body is None else json.dumps(body).encode(),headers={"Authorization":"Bearer "+token,"Accept":"application/json","Content-Type":"application/json"})
    try:
        with urllib.request.build_opener(p.NoRedirect(),urllib.request.HTTPSHandler(context=p.verified_ssl_context())).open(req,timeout=45) as r:
            raw=r.read(4194305);assert len(raw)<=4194304
            return r.status,json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:return e.code,p.cloud.error_details(e.read(65536))

sys.path.insert(0,".github/scripts")
from verify_cached_jdk import discover
home=discover(os.environ.get("RUNNER_TOOL_CACHE",""))
source=pathlib.Path.home()/".android/debug.keystore"
assert source.is_file() and not source.is_symlink() and 256<=source.stat().st_size<=65536,"original_signing_key_missing"
cert=subprocess.check_output([str(home/"bin/keytool.exe"),"-exportcert","-alias","androiddebugkey","-keystore",str(source),"-storepass","android"],stderr=subprocess.DEVNULL,timeout=30)
assert hashlib.sha256(cert).hexdigest()=="bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1","original_signing_identity_mismatch"
sid=9415007;ip="83.217.195.29";host="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIItaYR3yYmfPA7lJwNgOBGMr0Tu/ioG+Zarm+Utc33z0"
status,data=api("GET","/servers/"+str(sid));assert status==200
server=data["server"];assert server["name"]=="Analyst AI PRO" and server["project_id"]==2941515 and p.cloud.public_ipv4(server)==ip
access.SERVER_ID=sid
with tempfile.TemporaryDirectory(prefix="analyst-signing-restore-",dir=os.environ["RUNNER_TEMP"]) as directory:
    folder=pathlib.Path(directory);p.cloud.generate_key(folder/"client");public=(folder/"client.pub").read_text().strip()
    created=access.request(token,"POST","/ssh-keys",{"name":"analyst-key-restore-"+os.environ["GITHUB_RUN_ID"],"body":public,"is_default":False})
    key=created.get("ssh_key",created.get("ssh-key",{}));kid=key["id"];assert type(kid) is int
    attached=False
    try:
        access.request(token,"POST","/servers/"+str(sid)+"/ssh-keys",{"ssh_key_ids":[kid]});attached=True
        cmd=p.ssh_command(folder,ip,host)
        for attempt in range(12):
            try:p.remote(cmd,"test $(id -u) = 0",timeout=12);break
            except (p.ProbeError,subprocess.TimeoutExpired):
                if attempt==11:raise
                time.sleep(5)
        out=p.remote(cmd,"python3 -c "+shlex.quote("\nimport sys,pathlib,os,pwd,tempfile,subprocess,hashlib,json\nraw=sys.stdin.buffer.read(65537)\nassert 256<=len(raw)<=65536,\"invalid_keystore_size\"\nowner=pwd.getpwnam(\"analyst-build\")\ndirectory=pathlib.Path(\"/var/lib/analyst-ai-build/.android\")\ndirectory.mkdir(mode=0o700,exist_ok=True);os.chown(directory,owner.pw_uid,owner.pw_gid);directory.chmod(0o700)\ntarget=directory/\"debug.keystore\"\nwith tempfile.NamedTemporaryFile(dir=directory,delete=False) as f:\n    f.write(raw);temporary=pathlib.Path(f.name)\ntry:\n    temporary.chmod(0o600)\n    cert=subprocess.check_output([\"keytool\",\"-exportcert\",\"-alias\",\"androiddebugkey\",\"-keystore\",str(temporary),\"-storepass\",\"android\"],stderr=subprocess.DEVNULL)\n    digest=hashlib.sha256(cert).hexdigest()\n    assert digest==\"bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1\",\"signing_certificate_mismatch\"\n    if target.exists():\n        assert hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(raw).digest(),\"existing_keystore_changed\"\n    else:\n        os.chown(temporary,owner.pw_uid,owner.pw_gid);os.link(temporary,target)\n    print(\"AMS_ORIGINAL_SIGNING_KEY_RESTORED=\"+json.dumps({\"certificate_sha256\":digest,\"mode\":oct(target.stat().st_mode&0o777),\"build_user_can_read\":target.stat().st_uid==owner.pw_uid}),flush=True)\nfinally:\n    temporary.unlink(missing_ok=True)\n"),source.read_bytes(),timeout=40)
        print(out.decode(errors="replace"),flush=True)
    finally:
        if attached:access.request(token,"DELETE","/servers/"+str(sid)+"/ssh-keys/"+str(kid))
        access.request(token,"DELETE","/ssh-keys/"+str(kid))
        print("AMS_KEY_RESTORE_ACCESS_REMOVED=true",flush=True)
