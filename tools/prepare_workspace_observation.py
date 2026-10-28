from pathlib import Path
import json
import shutil
destination=Path("deploy/plan-20261027")
shutil.copyfile("deploy/observe_workspace.py",destination/"operation.py")
(destination/"payload.json").write_text(json.dumps({"source_commit":"aad0a117074a1b083021f93ef9ff928102b95557"}))
