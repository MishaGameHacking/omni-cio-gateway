from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from scripts.validate_v10_node_profile import assess_exit_gate, validate_shape


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute canonical WP5 node Exit Gate state")
    parser.add_argument("profile")
    parser.add_argument("--thresholds", required=True)
    args = parser.parse_args(argv)

    profile_path = Path(args.profile)
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        thresholds = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WP5 assessment failed: {exc}", file=sys.stderr)
        return 1
    if not isinstance(profile, dict) or not isinstance(thresholds, dict):
        print("WP5 assessment failed: profile and thresholds must be JSON objects", file=sys.stderr)
        return 1

    failures = validate_shape(profile)
    if failures:
        print("WP5 assessment failed before Exit Gate computation:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    blockers = assess_exit_gate(profile, thresholds)
    profile["exit_gate"] = {
        "status": "PASS" if not blockers else "BLOCKED",
        "blocking_reasons": blockers,
    }
    profile_path.write_text(
        json.dumps(profile, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"WP5 Exit Gate assessment written: {profile['exit_gate']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
