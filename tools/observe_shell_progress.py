from pathlib import Path
import json,re,os,datetime
assert os.environ.get("COMPUTERNAME") == "LAPTOP-NPSGA016"
rows=[]
for runner in ("actions-runner","actions-runner-2","actions-runner-3","actions-runner-4"):
    root=Path("C:/")/runner/"_work/_temp/server-version-client-40674568527-1"
    steps=root/"shell-build-steps.json"
    if not steps.is_file() or steps.stat().st_size>1048576: continue
    data=json.loads(steps.read_text())
    result={"runner":runner,"steps":[{"label":s["label"],"exit_code":s.get("exit_code")} for s in data["steps"]]}
    for log in root.glob("shell-build-steps-*-gradle.log"):
        if log.stat().st_size<=2000000:
            text=log.read_text(encoding="utf-8",errors="replace")
            result["gradle_tasks"]=re.findall(r"^> Task ([A-Za-z0-9:_-]+)(?: (UP-TO-DATE|NO-SOURCE|FAILED|FROM-CACHE))?",text,re.M)[-10:]
            result["build_successful"]="BUILD SUCCESSFUL" in text
            result["build_failed"]="BUILD FAILED" in text
    rows.append(result)
print(json.dumps({"checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"build_run":40674568527,"checks":rows}))
