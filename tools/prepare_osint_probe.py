import json
from pathlib import Path
import shutil
source = Path("deploy/observe_investment_osint.py").read_text()
if "observed = None" not in source or "time.monotonic() + 650" not in source:
    raise RuntimeError("observation_contract_changed")
source = "\ndef public_headers():\n    import urllib.parse\n    from datetime import timedelta\n    end = datetime.now(timezone.utc) - timedelta(minutes=30)\n    start = end - timedelta(hours=6)\n    query = urllib.parse.urlencode({\"query\": '(MOEX OR \"Moscow Exchange\" OR Gazprom OR Sberbank OR Nornickel OR \"московская биржа\")',\n        \"mode\":\"artlist\",\"format\":\"json\",\"maxrecords\":\"250\",\"sort\":\"datedesc\",\n        \"startdatetime\":start.strftime(\"%Y%m%d%H%M%S\"),\"enddatetime\":end.strftime(\"%Y%m%d%H%M%S\")})\n    urls = {\"moex_news\":\"https://www.moex.com/export/news.aspx?cat=100\",\n            \"moex_listing\":\"https://www.moex.com/export/news.aspx?cat=104\",\n            \"gdelt_finance\":\"https://api.gdeltproject.org/api/v2/doc/doc?\"+query}\n    results = {}\n    for key, url in urls.items():\n        request = urllib.request.Request(url, headers={\"User-Agent\":\"AnalystAIResearch/1.0 (+https://github.com/MishaGameHacking/omni-cio-gateway)\",\"Accept-Encoding\":\"identity\"})\n        try:\n            with urllib.request.urlopen(request, timeout=20) as response:\n                results[key] = {\"http_status\":response.status,\"length\":response.headers.get(\"Content-Length\"),\n                                \"content_type\":response.headers.get(\"Content-Type\")}\n        except Exception as error:\n            results[key] = {\"error_type\":type(error).__name__}\n    return results\n" + source
source = source.replace("    print(json.dumps(receipt, ensure_ascii=True), flush=True)", "    receipt[\"http_diagnostics\"] = public_headers()\n    print(json.dumps(receipt, ensure_ascii=True), flush=True)")
source = source.replace("observed = None", "observed = sample()").replace("time.monotonic() + 650", "time.monotonic()")
prefix = "import json\nfrom pathlib import Path\nENVELOPE['payload'] = json.loads(Path('/var/lib/analyst-ai-build/development/server-runtime-40700323988/deployment.json').read_text())\n"
destination = Path("deploy/plan-20261027")
(destination / "operation.py").write_text(prefix + source)
(destination / "payload.json").write_text("{}")
