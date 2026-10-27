"""Offline hierarchy/evidence inspector. Never loads runtime credentials or DBs."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.application_hierarchy import hierarchy
from backend.workspace_readiness import build_status


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_input_key")
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError("nonfinite_input_number")


def load(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("input_size_limit")
    value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("input_object_required")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", help="Explicit local materialized snapshot JSON; no broker is contacted")
    parser.add_argument("--strategy", help="Optional explicit local strategy JSON")
    parser.add_argument("--at", help="Required aware ISO timestamp when a snapshot is supplied")
    parser.add_argument("--output", help="New output path; existing evidence is never overwritten")
    args = parser.parse_args()
    if args.snapshot:
        if not args.at:
            parser.error("--at is required for reproducible evidence assessment")
        at = datetime.fromisoformat(args.at.replace("Z", "+00:00"))
        report = build_status(load(args.snapshot), load(args.strategy) if args.strategy else None,
                              connected=True, now=at)
    else:
        if args.strategy or args.at:
            parser.error("--strategy and --at require --snapshot")
        report = hierarchy()
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        with Path(args.output).open("x", encoding="utf-8") as stream:
            stream.write(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RecursionError):
        print("offline_inspection_input_or_output_invalid", file=sys.stderr)
        raise SystemExit(2)
