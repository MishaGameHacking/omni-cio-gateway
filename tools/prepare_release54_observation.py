from pathlib import Path
import shutil
root = Path("deploy/plan-20261027")
shutil.copyfile("deploy/observe_release54.py", root / "operation.py")
(root / "payload.json").write_text("{}")
