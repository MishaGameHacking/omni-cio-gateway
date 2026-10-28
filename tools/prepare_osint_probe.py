import json
from pathlib import Path
import shutil
source = Path("deploy/observe_investment_osint.py").read_text()
if "observed = None" not in source or "time.monotonic() + 650" not in source:
    raise RuntimeError("observation_contract_changed")
source = source.replace("observed = None", "observed = sample()").replace("time.monotonic() + 650", "time.monotonic()")
prefix = "import json\nfrom pathlib import Path\nENVELOPE['payload'] = json.loads(Path('/var/lib/analyst-ai-build/development/server-runtime-40700323988/deployment.json').read_text())\n"
destination = Path("deploy/plan-20261027")
(destination / "operation.py").write_text(prefix + source)
(destination / "payload.json").write_text("{}")
