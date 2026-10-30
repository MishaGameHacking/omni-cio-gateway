"""Stage pinned source and weights without activation for the reviewed owner transport."""
import json
from pathlib import Path


def main():
    target = Path("deploy/plan-20261027")
    if not target.is_dir() or target.is_symlink():
        raise ValueError("transport_directory_missing")
    (target / "operation.py").write_bytes(Path("deploy/prepare_local_ai_runtime.py").read_bytes())
    (target / "payload.json").write_text(json.dumps({"source_commit": "853090e11dcefef693366159c97316e55045c4c9"}))


if __name__ == "__main__":
    main()
