"""Offline inspector restricted to named JSON evidence in its local workspace.

Inputs: .runtime-inspection/inputs/{snapshot,strategy}.json below this checkout.
Output: .runtime-inspection/reports/hierarchy.json, created exclusively.
CLI values select named inputs; they never become arbitrary filesystem paths.
No runtime database, credential file, broker or external model is opened.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / ".runtime-inspection"
MAX_INPUT_BYTES = 2 * 1024 * 1024
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


def _unlinked(info):
    return not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400


def _directory(path):
    if not path.is_absolute():
        raise ValueError("absolute_evidence_root_required")
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if not _unlinked(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError("linked_or_non_directory_evidence_path")


def _regular(info):
    if not _unlinked(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("single_regular_evidence_file_required")


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _input_file(name):
    # Select complete fixed paths, not a concatenated caller-controlled path.
    if name == "snapshot.json":
        return EVIDENCE_ROOT / "inputs" / "snapshot.json"
    if name == "strategy.json":
        return EVIDENCE_ROOT / "inputs" / "strategy.json"
    raise ValueError("unknown_named_evidence_input")


def _read_input(path):
    _directory(path.parent)
    before = path.lstat()
    _regular(before)
    if not 0 < before.st_size <= MAX_INPUT_BYTES:
        raise ValueError("input_size_limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        _regular(opened)
        if _identity(opened) != _identity(before):
            raise ValueError("evidence_replaced_before_read")
        raw = stream.read(MAX_INPUT_BYTES + 1)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    _regular(final)
    if len(raw) != before.st_size or _identity(before) != _identity(after) or _identity(before) != _identity(final):
        raise ValueError("evidence_changed_during_read")
    _directory(path.parent)
    return raw


def load(name):
    raw = _read_input(_input_file(name))
    value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("input_object_required")
    return value


def save_report(name, text):
    if name != "hierarchy.json":
        raise ValueError("unknown_named_evidence_output")
    # The checkout must already exist; only the two fixed evidence directories
    # may be created. Reject links before opening or changing any file.
    _directory(EVIDENCE_ROOT.parent)
    EVIDENCE_ROOT.mkdir(exist_ok=True)
    _directory(EVIDENCE_ROOT)
    reports = EVIDENCE_ROOT / "reports"
    reports.mkdir(exist_ok=True)
    _directory(reports)
    destination = reports / "hierarchy.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        _regular(os.fstat(stream.fileno()))
        stream.write(text.encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    _directory(reports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", choices=("snapshot.json",), help="Named snapshot in .runtime-inspection/inputs")
    parser.add_argument("--strategy", choices=("strategy.json",), help="Named strategy in .runtime-inspection/inputs")
    parser.add_argument("--at", help="Required aware ISO timestamp when a snapshot is supplied")
    parser.add_argument("--output", choices=("hierarchy.json",), help="Create .runtime-inspection/reports/hierarchy.json; never overwrite")
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
        save_report(args.output, text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RecursionError):
        print("offline_inspection_input_or_output_invalid", file=sys.stderr)
        raise SystemExit(2)
