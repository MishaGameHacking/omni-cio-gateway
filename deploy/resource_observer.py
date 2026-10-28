#!/usr/bin/env python3
"""Bounded local resource measurements; no cloud mutations or paid API calls."""
import datetime,json,os,pathlib,shutil,subprocess,time,urllib.request
os.umask(0o077)
root=pathlib.Path("/var/lib/analyst-ai-ops")
root.mkdir(mode=0o700,exist_ok=True)
now=int(time.time())
mem={l.split(":")[0]:int(l.split()[1])*1024 for l in pathlib.Path("/proc/meminfo").read_text().splitlines() if l.startswith(("MemTotal:","MemAvailable:","SwapTotal:","SwapFree:"))}
cpu=[int(x) for x in pathlib.Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
state_file=root/"previous-resource-sample.json"
previous=json.loads(state_file.read_text()) if state_file.exists() else None
sample={"at":now,"at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"memory":mem,"cpu_busy_percent":None,"disk":dict(zip(("total","used","free"),shutil.disk_usage("/"))),"services":{}}
if previous and now>previous["at"]:
    ticks=sum(cpu)-sum(previous["cpu"])
    idle=cpu[3]+cpu[4]-previous["cpu"][3]-previous["cpu"][4]
    if ticks>0:sample["cpu_busy_percent"]=round(100*(ticks-idle)/ticks,2)
state_file.write_text(json.dumps({"at":now,"cpu":cpu})+"\n")
for unit in ("analyst-ai-owner","caddy"):
    command=["systemctl","show",unit,"-p","ActiveState","-p","NRestarts","-p","MemoryCurrent","-p","MemoryPeak","-p","CPUUsageNSec","-p","ControlGroup"]
    result=subprocess.run(command,capture_output=True,text=True,timeout=8)
    values=dict(l.split("=",1) for l in result.stdout.splitlines() if "=" in l)
    entry={k:values.get(k) for k in ("ActiveState","NRestarts","MemoryCurrent","MemoryPeak","CPUUsageNSec")}
    cg=values.get("ControlGroup","")
    if cg.startswith("/system.slice/"):
        events=pathlib.Path("/sys/fs/cgroup"+cg+"/memory.events")
        if events.is_file():entry["memory_events"]=dict(l.split() for l in events.read_text().splitlines())
    sample["services"][unit]=entry
start=time.monotonic()
try:
    with urllib.request.urlopen("http://127.0.0.1:8080/health",timeout=5) as response:
        sample["health"]={"ok":response.status==200 and json.load(response)=={"status":"ok"},"milliseconds":round((time.monotonic()-start)*1000,2)}
except Exception as error:sample["health"]={"ok":False,"error_type":type(error).__name__}
data=pathlib.Path("/var/lib/analyst-ai")
sample["sqlite_bytes"]=sum(p.stat().st_size for p in data.rglob("*") if p.is_file() and (p.suffix in {".db",".sqlite",".sqlite3"} or p.name.endswith(("-wal","-shm"))))
path=root/"resource-usage.jsonl"
rows=[]
if path.exists():
    with path.open() as f:
        for line in f:
            try:
                old=json.loads(line)
                if old.get("at",0)>=now-14*86400:rows.append(old)
            except ValueError:continue
rows=rows[-4031:]+[sample]
temporary=root/"resource-usage.tmp"
temporary.write_text("".join(json.dumps(row,separators=(",",":"))+"\n" for row in rows))
temporary.replace(path)
(root/"latest-resource-sample.json").write_text(json.dumps(sample,indent=2)+"\n")
print(json.dumps({"sample_recorded":True,"health_ok":sample["health"]["ok"]}))
