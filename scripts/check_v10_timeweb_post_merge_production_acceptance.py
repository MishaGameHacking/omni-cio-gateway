from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "docs/architecture/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_CONTRACT.json"
)


def _read_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("TIMEWEB_P6_CONTRACT_UNREADABLE") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_P6_CONTRACT_INVALID")
    return payload


def _require(payload: dict[str, Any], key: str, expected: Any) -> None:
    if payload.get(key) != expected:
        raise RuntimeError(f"TIMEWEB_P6_CONTRACT_DRIFT:{key}")


def validate(root: Path = ROOT) -> None:
    payload = _read_contract(
        root
        / "docs/architecture/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_CONTRACT.json"
    )
    _require(
        payload,
        "schema",
        "omni-cio.v10.timeweb-post-merge-production-acceptance.v1",
    )
    _require(payload, "owning_pr", 584)
    _require(payload, "milestone", "P6_POST_MERGE_PRODUCTION_ACCEPTANCE")
    _require(payload, "canonical_origin", "https://omnicio.ru")

    live = payload.get("live_probes")
    if not isinstance(live, dict):
        raise RuntimeError("TIMEWEB_P6_LIVE_PROBES_INVALID")
    if live.get("sole_provider") != "telegram":
        raise RuntimeError("TIMEWEB_P6_PROVIDER_DRIFT")
    if live.get("provider_enabled") is not True:
        raise RuntimeError("TIMEWEB_P6_PROVIDER_DRIFT")
    if live.get("exact_release_sha_required") is not True:
        raise RuntimeError("TIMEWEB_P6_RELEASE_SHA_POLICY_DRIFT")

    protected = payload.get("protected_invariants")
    if not isinstance(protected, dict):
        raise RuntimeError("TIMEWEB_P6_INVARIANTS_INVALID")
    if any(value is not False for value in protected.values()):
        raise RuntimeError("TIMEWEB_P6_AUTHORITY_WIDENED")


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(f"V10_TIMEWEB_POST_MERGE_ACCEPTANCE=FAIL code={exc}", file=sys.stderr)
        return 1
    print("V10_TIMEWEB_POST_MERGE_ACCEPTANCE=PASS scope=P6 exact_main=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
