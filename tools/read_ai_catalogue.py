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
        result.append({key:row.get(key) for key in ("id","name","slug","provider")} | {
            "parameters":{key:parameters.get(key) for key in ("cost_in","cost_out","context_window","max_tokens","context_length","max_output_tokens")}})
    report={"status":"available","models":result}
except (urllib.error.URLError, ValueError, TypeError):
    report={"status":"unavailable"}
Path("plan-reports").mkdir(exist_ok=True)
Path("plan-reports/ai-catalogue.json").write_text(json.dumps(report))
print("AI_CATALOGUE="+json.dumps(report),flush=True)
