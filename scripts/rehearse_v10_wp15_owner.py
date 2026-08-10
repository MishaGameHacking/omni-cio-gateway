from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from omni_cio.adapters.tinvest_market_v1 import TInvestMarketReadAdapter
from omni_cio.adapters.tinvest_read_v1 import (
    BrokerAccountBindingV1,
    FreshnessState,
    TInvestReadAdapter,
    TInvestReadPolicyV1,
    discover_owner_account_binding,
)
from omni_cio.adapters.tinvest_secret_v1 import broker_read_client


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_BINDING = Path(
    r"C:\ProgramData\OmniCIO\wp15\private\owner-account-binding.json"
)
SANITIZED_EVIDENCE = Path(
    r"C:\ProgramData\OmniCIO\wp15\evidence\wp15-owner-live-evidence.json"
)
IMPLEMENTATION_FILES = (
    "omni_cio/adapters/tinvest_read_v1.py",
    "omni_cio/adapters/tinvest_market_v1.py",
    "omni_cio/adapters/tinvest_secret_v1.py",
    "scripts/rehearse_v10_wp15_owner.py",
    "infrastructure/windows/run_wp15_owner_gate.ps1",
    "docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md",
)


class OwnerGateError(RuntimeError):
    """Sanitized OWNER-gate failure."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = completed.stdout.strip()
    if len(value) != 40:
        raise OwnerGateError("GIT_SHA_INVALID")
    return value


def _git_clean() -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return not bool(completed.stdout.strip())


def _implementation_sha256() -> str:
    digest = hashlib.sha256()
    for relative in IMPLEMENTATION_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise OwnerGateError("IMPLEMENTATION_FILE_MISSING")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    encoded = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    try:
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_binding() -> BrokerAccountBindingV1 | None:
    if not PRIVATE_BINDING.exists():
        return None
    try:
        payload = json.loads(PRIVATE_BINDING.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OwnerGateError("OWNER_BINDING_INVALID") from exc
    if not isinstance(payload, dict) or str(payload.get("schema_version", "")) != "1":
        raise OwnerGateError("OWNER_BINDING_INVALID")
    try:
        return BrokerAccountBindingV1.model_validate(payload["binding"])
    except Exception as exc:
        raise OwnerGateError("OWNER_BINDING_INVALID") from exc


def _confirm(prompt: str) -> bool:
    response = input(f"{prompt} Type YES to confirm: ").strip()
    return response == "YES"


def _write_binding(binding: BrokerAccountBindingV1) -> None:
    _atomic_json(
        PRIVATE_BINDING,
        {
            "schema_version": "1",
            "provider": "t_invest",
            "bound_at": _utc_now().isoformat(),
            "binding": binding.model_dump(mode="json"),
        },
    )


def _safe_position_label(position: Any) -> str:
    instrument = position.instrument
    return instrument.ticker or instrument.name or "sample-position"


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _write_evidence(
    *,
    status: str,
    reason: str,
    git_sha: str,
    implementation_sha256: str,
    checks: dict[str, bool],
    counts: dict[str, int],
) -> None:
    _atomic_json(
        SANITIZED_EVIDENCE,
        {
            "schema_version": "1",
            "work_package": "WP15",
            "audit": "owner_live_read_only",
            "status": status,
            "reason": reason,
            "git_sha": git_sha,
            "implementation_sha256": implementation_sha256,
            "recorded_at": _utc_now().isoformat(),
            "checks": checks,
            "counts": counts,
            "privacy": {
                "token_value_recorded": False,
                "full_account_id_recorded": False,
                "account_fingerprint_recorded": False,
                "portfolio_values_recorded": False,
                "position_values_recorded": False,
                "raw_broker_payload_recorded": False,
            },
            "authority": {
                "broker_read": True,
                "broker_write": False,
                "trading_methods": False,
                "real_trading_enabled": False,
            },
        },
    )


def _print_safe_summary(
    *,
    status: str,
    reason: str,
    checks: dict[str, bool],
) -> None:
    print()
    print(f"WP15 OWNER live gate: {status}")
    print(f"Reason: {reason}")
    print(f"Read-only token confirmation: {checks.get('owner_read_only_token', False)}")
    print(f"Expected account binding: {checks.get('expected_account_binding', False)}")
    print(f"Portfolio confirmation: {checks.get('portfolio_summary_confirmed', False)}")
    print(
        "Sample position confirmation: "
        f"{checks.get('sample_position_confirmed', False)}"
    )
    print(f"Freshness confirmation: {checks.get('freshness_confirmed', False)}")
    print(f"Implementation binding: {checks.get('implementation_binding', False)}")


def main() -> int:
    git_sha = ""
    implementation = ""
    checks = {
        "owner_read_only_token": False,
        "expected_account_binding": False,
        "snapshot_complete": False,
        "market_read": False,
        "operations_read": False,
        "portfolio_summary_confirmed": False,
        "sample_position_confirmed": False,
        "freshness_confirmed": False,
        "implementation_binding": False,
    }
    counts = {
        "normalized_positions": 0,
        "market_prices": 0,
        "operation_pages": 0,
        "operations": 0,
    }

    try:
        if not _git_clean():
            raise OwnerGateError("OWNER_CHECKOUT_NOT_CLEAN")
        git_sha = _git_sha()
        implementation = _implementation_sha256()
        checks["implementation_binding"] = True

        if not _confirm(
            "Confirm the locally provisioned T-Invest credential is READ-ONLY"
        ):
            raise OwnerGateError("READ_ONLY_TOKEN_NOT_CONFIRMED")
        checks["owner_read_only_token"] = True

        discovered = discover_owner_account_binding(broker_read_client)
        existing = _read_binding()
        if existing is not None:
            if (
                existing.broker_account_id != discovered.broker_account_id
                or existing.account_fingerprint_sha256
                != discovered.account_fingerprint_sha256
            ):
                raise OwnerGateError("OWNER_ACCOUNT_BINDING_CHANGED")
        print()
        print(f"Masked broker account: {discovered.masked_label}")
        print(f"Account type: {discovered.account_type or 'unknown'}")
        if not _confirm("Confirm this is the intended OWNER broker account"):
            raise OwnerGateError("OWNER_ACCOUNT_NOT_CONFIRMED")
        checks["expected_account_binding"] = True
        if existing is None:
            _write_binding(discovered)
        binding = existing or discovered

        policy = TInvestReadPolicyV1(
            stale_after_seconds=300,
            max_operation_pages=3,
            operation_page_limit=100,
            max_attempts=3,
        )
        read_adapter = TInvestReadAdapter(
            client_factory=broker_read_client,
            expected_account_fingerprint_sha256=(
                binding.account_fingerprint_sha256
            ),
            policy=policy,
        )
        snapshot = read_adapter.read_snapshot()
        if snapshot.unresolved_position_count != 0:
            raise OwnerGateError("LIVE_SNAPSHOT_INCOMPLETE")
        if snapshot.freshness.state is not FreshnessState.FRESH:
            raise OwnerGateError("LIVE_SNAPSHOT_STALE")
        checks["snapshot_complete"] = True
        counts["normalized_positions"] = snapshot.normalized_position_count

        if snapshot.portfolio_total is None:
            raise OwnerGateError("LIVE_PORTFOLIO_TOTAL_MISSING")
        if not snapshot.snapshot.positions:
            raise OwnerGateError("LIVE_SAMPLE_POSITION_MISSING")

        market_adapter = TInvestMarketReadAdapter(
            client_factory=broker_read_client,
            expected_account_fingerprint_sha256=(
                binding.account_fingerprint_sha256
            ),
            policy=policy,
        )
        market = market_adapter.read_last_prices(
            tuple(position.instrument for position in snapshot.snapshot.positions),
            allow_partial=False,
        )
        checks["market_read"] = market.missing_instrument_count == 0
        counts["market_prices"] = market.returned_instrument_count

        operations = read_adapter.read_operations()
        checks["operations_read"] = operations.pages_loaded >= 1
        counts["operation_pages"] = operations.pages_loaded
        counts["operations"] = len(operations.operations)

        sample = snapshot.snapshot.positions[0]
        sample_market = next(
            (
                row
                for row in market.prices
                if row.instrument_uid == sample.instrument.uid
            ),
            None,
        )
        if sample_market is None:
            raise OwnerGateError("LIVE_SAMPLE_MARKET_PRICE_MISSING")

        print()
        print("PRIVATE LOCAL COMPARISON — do not copy this block into GitHub/chat.")
        print(
            "Portfolio total: "
            f"{_decimal_text(snapshot.portfolio_total.amount)} "
            f"{snapshot.portfolio_total.currency}"
        )
        print(
            "Snapshot age: "
            f"{_decimal_text(snapshot.freshness.age_seconds)} seconds "
            f"({snapshot.freshness.state.value})"
        )
        print(f"Sample position: {_safe_position_label(sample)}")
        print(f"Sample quantity: {_decimal_text(sample.quantity_units)}")
        print(
            "Sample last market price: "
            f"{_decimal_text(sample_market.price)} "
            f"{sample.instrument.currency}"
        )
        print(
            "Sample market price age: "
            f"{_decimal_text(sample_market.age_seconds)} seconds "
            f"({sample_market.freshness.value})"
        )
        print(
            "Operations smoke: "
            f"{operations.pages_loaded} page(s), "
            f"{len(operations.operations)} normalized operation(s), "
            f"truncated={operations.truncated}"
        )
        print("END PRIVATE LOCAL COMPARISON")
        print()

        if not _confirm(
            "Confirm the portfolio summary matches the intended broker account"
        ):
            raise OwnerGateError("PORTFOLIO_SUMMARY_NOT_CONFIRMED")
        checks["portfolio_summary_confirmed"] = True

        if not _confirm(
            "Confirm the sample quantity and displayed current price/value "
            "match the broker view on the same basis"
        ):
            raise OwnerGateError("SAMPLE_POSITION_NOT_CONFIRMED")
        checks["sample_position_confirmed"] = True

        if not _confirm(
            "Confirm the displayed snapshot/market data ages are acceptable"
        ):
            raise OwnerGateError("FRESHNESS_NOT_CONFIRMED")
        checks["freshness_confirmed"] = True

        required = (
            "owner_read_only_token",
            "expected_account_binding",
            "snapshot_complete",
            "market_read",
            "operations_read",
            "portfolio_summary_confirmed",
            "sample_position_confirmed",
            "freshness_confirmed",
            "implementation_binding",
        )
        if not all(checks[item] for item in required):
            raise OwnerGateError("OWNER_LIVE_GATE_INCOMPLETE")

        _write_evidence(
            status="PASS",
            reason="WP15_OWNER_LIVE_READ_ONLY_ACCEPTED",
            git_sha=git_sha,
            implementation_sha256=implementation,
            checks=checks,
            counts=counts,
        )
        _print_safe_summary(
            status="PASS",
            reason="WP15_OWNER_LIVE_READ_ONLY_ACCEPTED",
            checks=checks,
        )
        return 0
    except OwnerGateError as exc:
        reason = str(exc)
    except Exception:
        reason = "OWNER_LIVE_GATE_UNEXPECTED_ERROR"

    if git_sha and implementation:
        _write_evidence(
            status="FAIL",
            reason=reason,
            git_sha=git_sha,
            implementation_sha256=implementation,
            checks=checks,
            counts=counts,
        )
    _print_safe_summary(status="FAIL", reason=reason, checks=checks)
    return 1


if __name__ == "__main__":
    sys.exit(main())
