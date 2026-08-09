from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("tests", nargs="+")
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.is_dir():
        raise SystemExit("WP10_CONTINUITY_PYTEST_TARGET_MISSING")

    repo_root = Path.cwd().resolve()
    if not (repo_root / "AGENTS.md").is_file():
        raise SystemExit("WP10_CONTINUITY_REPO_ROOT_NOT_DETECTED")

    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(target))
    import pytest

    return int(pytest.main(["-q", *args.tests]))


if __name__ == "__main__":
    raise SystemExit(main())
