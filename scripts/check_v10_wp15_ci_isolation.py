from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


BROKER_READ_CIPHERTEXT = Path(
    r"C:\ProgramData\OmniCIO\secrets\read-broker\broker-read.dpapi"
)
PRIVATE_OWNER_BINDING = Path(
    r"C:\ProgramData\OmniCIO\wp15\private\owner-account-binding.json"
)
_ALLOWED = {"ACCESS_DENIED", "NOT_VISIBLE"}


def classify_open(path: Path) -> str:
    """Classify open-for-read without reading or returning file contents."""
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except PermissionError:
        return "ACCESS_DENIED"
    except FileNotFoundError:
        return "NOT_VISIBLE"
    except OSError as exc:
        return f"ERROR_TYPE:{type(exc).__name__}"
    else:
        os.close(descriptor)
        return "READABLE"


def build_report() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "work_package": "WP15",
        "broker_read_ciphertext": classify_open(BROKER_READ_CIPHERTEXT),
        "private_owner_binding": classify_open(PRIVATE_OWNER_BINDING),
        "secret_value_read": False,
        "private_payload_read": False,
    }


def validate_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != "1" or report.get("work_package") != "WP15":
        raise ValueError("WP15_ISOLATION_REPORT_INVALID")
    for key in ("broker_read_ciphertext", "private_owner_binding"):
        value = report.get(key)
        if value not in _ALLOWED:
            raise ValueError(f"WP15_CI_BOUNDARY_UNSAFE:{key}:{value}")
    if report.get("secret_value_read") is not False:
        raise ValueError("WP15_CI_SECRET_READ_FLAG_INVALID")
    if report.get("private_payload_read") is not False:
        raise ValueError("WP15_CI_PRIVATE_READ_FLAG_INVALID")


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("WP15_ISOLATION_REPORT_INVALID")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enforce", type=Path)
    args = parser.parse_args()

    if bool(args.output) == bool(args.enforce):
        parser.error("choose exactly one of --output or --enforce")

    if args.output is not None:
        report = build_report()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(report, sort_keys=True))
        return 0

    try:
        report = _load(args.enforce)
        validate_report(report)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "work_package": "WP15",
                    "status": "FAIL",
                    "reason": str(exc),
                },
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "schema_version": "1",
                "work_package": "WP15",
                "status": "PASS",
                "reason": "WP15_CI_PRIVATE_BOUNDARIES_ISOLATED",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
