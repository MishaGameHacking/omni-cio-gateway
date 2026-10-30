"""Stage fixed read-only prerequisites for the reviewed owner transport."""
import json
from pathlib import Path


def main():
    target = Path("deploy/plan-20261027")
    if not target.is_dir() or target.is_symlink():
        raise ValueError("transport_directory_missing")
    (target / "operation.py").write_bytes(Path("deploy/local_ai_preflight.py").read_bytes())
    (target / "payload.json").write_text(json.dumps({"source_commit": "68e0fb73feddf178c29d990633edae42aa7adda3"}))


if __name__ == "__main__":
    main()
