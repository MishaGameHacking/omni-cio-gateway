import hashlib,json,os,pathlib,shlex,subprocess,sys,tempfile,time,urllib.request,urllib.error
sys.path[:0]=[".transport-admin/deploy",".transport-admin/tools"]
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

def with_ams(remote_script, *, timeout=300, capture=False, binary_input=None):
    sid=9417611;ip="83.217.195.29";host="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILN7hxzg6D6GjaE9OYQ19wH86tSm10pTnv+s81eqOfIU runner@runnervmtai0g"
    status,data=api("GET","/servers/"+str(sid));assert status==200
    server=data["server"]
    assert server["name"]=="Analyst AI runtime 20261025" and server["project_id"]==2941515 and server["availability_zone"]=="ams-1" and p.cloud.public_ipv4(server)==ip
    access.SERVER_ID=sid
    with tempfile.TemporaryDirectory(prefix="analyst-ams-admin-",dir=os.environ["RUNNER_TEMP"]) as directory:
        folder=pathlib.Path(directory);p.cloud.generate_key(folder/"client");public=(folder/"client.pub").read_text().strip()
        created=access.request(token,"POST","/ssh-keys",{"name":"analyst-ams-admin-"+os.environ["GITHUB_RUN_ID"],"body":public,"is_default":False})
        key=created.get("ssh_key",created.get("ssh-key",{}));kid=key["id"]
        assert type(kid) is int and key["body"].split()[:2]==public.split()[:2]
        attached=False
        try:
            access.request(token,"POST","/servers/"+str(sid)+"/ssh-keys",{"ssh_key_ids":[kid]});attached=True
            cmd=p.ssh_command(folder,ip,host);cmd[1:1]=["-o","ServerAliveInterval=20","-o","ServerAliveCountMax=3"]
            for attempt in range(12):
                try:p.remote(cmd,"test $(id -u) = 0",timeout=12);break
                except (p.ProbeError,subprocess.TimeoutExpired):
                    if attempt==11:raise
                    time.sleep(5)
            payload=remote_script.encode() if binary_input is None else binary_input
            remote_command="python3 -" if binary_input is None else "python3 -c "+shlex.quote(remote_script)
            result=subprocess.run([*cmd,remote_command],input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
            if not capture:print(result.stdout.decode(errors="replace"),flush=True)
            if result.returncode:
                print("AMS_REMOTE_ERROR="+result.stderr.decode(errors="replace")[-4000:],flush=True)
                raise RuntimeError("remote_task_failed")
            return result.stdout
        finally:
            try:
                if attached:access.request(token,"DELETE","/servers/"+str(sid)+"/ssh-keys/"+str(kid))
            finally:
                access.request(token,"DELETE","/ssh-keys/"+str(kid))
            print("AMS_TEMP_KEY_REMOVED=true",flush=True)



REMOTE_SHA256 = '6ce23ba3ad32e18e6b91824af70e2e76fc77d6c975c54227d5c596d24b91c066'
remote = '"""Read current runtime capacity. No application imports or runtime mutations."""\nimport datetime\nimport json\nimport os\nfrom pathlib import Path\nimport shutil\nimport stat\nimport subprocess\nimport time\nimport urllib.request\n\n\ndef main():\n    assert os.geteuid() == 0\n    memory = {}\n    for line in Path(\'/proc/meminfo\').read_text().splitlines():\n        key, value = line.split(\':\', 1)\n        if key in {\'MemTotal\', \'MemAvailable\', \'SwapTotal\', \'SwapFree\'}:\n            memory[key] = int(value.split()[0]) * 1024\n    services = {}\n    allowed = {\'ActiveState\', \'SubState\', \'NRestarts\', \'MemoryCurrent\', \'MemoryPeak\', \'CPUUsageNSec\'}\n    for unit in (\'analyst-ai-owner.service\', \'analyst-ai-updates.service\', \'caddy.service\'):\n        result = subprocess.run([\'systemctl\', \'show\', unit, \'--property=\' + \',\'.join(sorted(allowed))],\n                                capture_output=True, text=True, timeout=8, check=True)\n        values = dict(line.split(\'=\', 1) for line in result.stdout.splitlines() if \'=\' in line)\n        assert set(values) <= allowed\n        services[unit] = values\n    timings = []\n    for _ in range(3):\n        start = time.monotonic()\n        with urllib.request.urlopen(\'http://127.0.0.1:8080/health\', timeout=5) as response:\n            assert response.status == 200 and response.read(1024) == b\'{"status":"ok"}\'\n        timings.append(round((time.monotonic() - start) * 1000, 2))\n    latest = Path(\'/var/lib/analyst-ai-ops/latest-resource-sample.json\')\n    observation = {\'available\': False}\n    if latest.exists():\n        info = latest.lstat()\n        assert stat.S_ISREG(info.st_mode) and not latest.is_symlink() and info.st_size <= 16384\n        value = json.loads(latest.read_bytes())\n        observation = {\'available\': True, \'sample_at_utc\': value.get(\'at_utc\'),\n                       \'sample_age_seconds\': int(time.time()) - int(value[\'at\']),\n                       \'cpu_busy_percent\': value.get(\'cpu_busy_percent\'), \'sqlite_bytes\': value.get(\'sqlite_bytes\')}\n    disk = shutil.disk_usage(\'/var/lib/analyst-ai\')\n    print(json.dumps({\'schema\': 1, \'kind\': \'runtime_capacity_readonly\', \'runtime_server_id\': 9417611,\n        \'observed_at\': datetime.datetime.now(datetime.timezone.utc).isoformat(),\n        \'memory_bytes\': memory, \'load_average\': list(os.getloadavg()),\n        \'disk_bytes\': {\'total\': disk.total, \'used\': disk.used, \'free\': disk.free},\n        \'services\': services, \'local_health_ms\': timings, \'existing_sample\': observation,\n        \'runtime_files_written\': False, \'database_opened\': False, \'services_restarted\': False,\n        \'model_or_broker_calls\': False, \'representative_load_test\': False}, sort_keys=True))\n\n\nif __name__ == \'__main__\':\n    main()\n'
assert __debug__ and os.environ['GITHUB_REPOSITORY']=='MishaGameHacking/omni-cio-gateway'
assert os.environ['GITHUB_REF']=='refs/heads/codex/timeweb-owner-prepare-2026-10-23'
assert hashlib.sha256(remote.encode()).hexdigest()==REMOTE_SHA256
raw=with_ams(remote,timeout=120,capture=True)
assert 0<len(raw)<32768
value=json.loads(raw)
assert value['kind']=='runtime_capacity_readonly' and value['runtime_server_id']==9417611
for key in ('runtime_files_written','database_opened','services_restarted','model_or_broker_calls','representative_load_test'):
    assert value[key] is False
folder=pathlib.Path(os.environ['RUNNER_TEMP'])/('free-runtime-capacity-'+os.environ['GITHUB_RUN_ID'])
folder.mkdir(exist_ok=False)
(folder/'capacity.json').write_bytes(raw)
print('RUNTIME_CAPACITY='+json.dumps(value,sort_keys=True),flush=True)
