"""Bounded read of current model prices; never create a paid resource."""
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

request=urllib.request.Request("https://api.timeweb.cloud/api/v3/cloud-ai/models",
    headers={"Authorization":"Bearer "+os.environ["TIMEWEB_CLOUD_TOKEN"],"Accept":"application/json"})
try:
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=30) as response:
        raw=response.read(2097153)
    if len(raw)>2097152:
        raise ValueError("catalogue_too_large")
    rows=json.loads(raw).get("models",[])
    result=[]
    for row in rows:
        parameters=row.get("parameter_values") or {}
        if row.get("id") in (5, 29, 39, 41, 75, 99, 121):
            result.append(row)
    report={"status":"available","models":result}
except (urllib.error.URLError, ValueError, TypeError):
    report={"status":"unavailable"}
Path("plan-reports").mkdir(exist_ok=True)
Path("plan-reports/ai-catalogue.json").write_text(json.dumps(report))
print("AI_CATALOGUE="+json.dumps(report),flush=True)
