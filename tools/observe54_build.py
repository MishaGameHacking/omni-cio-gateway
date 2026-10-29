"""Read-only diagnostics of this task's owner-laptop build logs."""
import os
from pathlib import Path
import json
if os.environ.get("COMPUTERNAME") != "LAPTOP-NPSGA016":
    raise RuntimeError("owner_laptop_required")
print("AI54_PROTECTED_KEY_PRESENT=" + str(bool(os.environ.get("TIMEWEB_AI_TOKEN","").startswith("sk-"))).lower())
for root in Path("C:/").glob("actions-runner*"):
    base=root/"_work"/"_temp"
    for name in ("server-version-client-40858844049-1","redesign-visual-40859518254-1"):
        path=base/name
        if not path.is_dir(): continue
        for steps in sorted(path.glob("*-steps.json")):
            if steps.stat().st_size > 1024*1024: continue
            report=json.loads(steps.read_text(encoding="utf-8"))
            print(json.dumps({"run":name,"steps":[{key:row.get(key) for key in ("label","started_at","finished_at","exit_code")} for row in report.get("steps",[])]}))
        for log in sorted(path.glob("*.log")):
            if not (log.name in {"gradle.log","render.log"} or "compose-preview-render" in log.name or log.name.endswith("-gradle.log")):
                continue
            if log.stat().st_size > 4*1024*1024: continue
            lines=log.read_text(encoding="utf-8",errors="replace").splitlines()
            filtered=[line[:700] for line in lines if any(word in line for word in ("> Task", "FAILED", "BUILD ", "e: ", "Exception", "Error", "Waiting", "Timeout", "WINDOWS_ANDROID_STEP", "daemon", "Daemon", "lock", "Downloading", "Configure project"))]
            print(json.dumps({"run":name,"log":log.name,"bytes":log.stat().st_size,"steps":filtered[-30:]},ensure_ascii=True))
