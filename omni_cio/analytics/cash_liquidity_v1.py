from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import grpc
from fastapi import HTTPException


BUYING_POWER_REASON = (
    "T-Invest GetWithdrawLimits describes funds available for withdrawal, "
    "not guaranteed purchasing power for a securities order."
)


def _decimal(base: Any, value: Any) -> Decimal | None:
    return base.decimal_from_any(value)


def _money_map(
    *,
    base: Any,
    rows: Any,
) -> tuple[dict[str, Decimal], set[str], int]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    present: set[str] = set()
    invalid_rows = 0

    if rows is None:
        return totals, present, invalid_rows
    if not isinstance(rows, list):
        return totals, present, 1

    for row in rows:
        if not isinstance(row, dict):
            invalid_rows += 1
            continue

        currency = str(row.get("currency", "") or "").strip().upper()
        amount = _decimal(base, row)
        if not currency or amount is None:
            invalid_rows += 1
            continue

        totals[currency] += amount
        present.add(currency)

    return totals, present, invalid_rows


def _component_error(base: Any, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, grpc.RpcError):
        _, payload = base.grpc_error_payload(exc)
        return payload
    return {
        "code": (
            "GATEWAY_SDK_COMPATIBILITY_ERROR"
            if isinstance(exc, (AttributeError, TypeError))
            else "GATEWAY_CLIENT_ERROR"
        ),
        "exception_type": type(exc).__name__,
        "message": base.safe_error_message(exc),
    }


def _value_or_unavailable(
    *,
    base: Any,
    values: dict[str, Decimal],
    present: set[str],
    currency: str,
) -> str:
    if currency not in present:
        return "unavailable"
    return base.decimal_string(values.get(currency, Decimal("0")))


def _cash_sources(
    *,
    base: Any,
    positions: dict[str, Any],
    withdraw: dict[str, Any],
) -> dict[str, tuple[dict[str, Decimal], set[str], int]]:
    return {
        "reported_money": _money_map(base=base, rows=positions.get("money")),
        "positions_blocked": _money_map(base=base, rows=positions.get("blocked")),
        "withdrawable_money": _money_map(base=base, rows=withdraw.get("money")),
        "withdraw_blocked": _money_map(base=base, rows=withdraw.get("blocked")),
        "blocked_guarantee": _money_map(
            base=base,
            rows=withdraw.get("blocked_guarantee"),
        ),
    }


def _source_value(
    sources: dict[str, tuple[dict[str, Decimal], set[str], int]],
    name: str,
    currency: str,
) -> tuple[Decimal, bool]:
    values, present, _ = sources[name]
    return values.get(currency, Decimal("0")), currency in present


def _cash_discrepancies(
    *,
    reported_value: Decimal,
    reported_present: bool,
    positions_blocked_value: Decimal,
    positions_blocked_present: bool,
    withdrawable_value: Decimal,
    withdrawable_present: bool,
    withdraw_blocked_value: Decimal,
    withdraw_blocked_present: bool,
    has_positions: bool,
    has_withdraw: bool,
) -> tuple[list[str], Decimal | None]:
    reasons: list[str] = []
    difference = (
        reported_value - withdrawable_value
        if reported_present and withdrawable_present
        else None
    )
    if difference is None:
        reasons.append("money_value_missing_from_one_source")
    elif difference != 0:
        reasons.append("reported_money_differs_from_withdrawable_money")

    if positions_blocked_present and withdraw_blocked_present:
        if positions_blocked_value != withdraw_blocked_value:
            reasons.append("blocked_value_differs_between_sources")
    elif positions_blocked_present != withdraw_blocked_present:
        reasons.append("blocked_value_missing_from_one_source")

    if not has_positions:
        reasons.append("currency_missing_from_positions")
    if not has_withdraw:
        reasons.append("currency_missing_from_withdraw_limits")
    return reasons, difference


def _cash_status(
    *,
    reasons: list[str],
    has_positions: bool,
    has_withdraw: bool,
) -> str:
    if not reasons:
        return "matched"
    if has_positions and has_withdraw:
        return "source_difference"
    if has_positions:
        return "positions_only"
    if has_withdraw:
        return "withdraw_limits_only"
    return "unavailable"


def _cash_row(
    *,
    base: Any,
    currency: str,
    sources: dict[str, tuple[dict[str, Decimal], set[str], int]],
) -> tuple[dict[str, Any], bool, bool, int]:
    reported_value, reported_present = _source_value(
        sources, "reported_money", currency
    )
    positions_blocked_value, positions_blocked_present = _source_value(
        sources, "positions_blocked", currency
    )
    withdrawable_value, withdrawable_present = _source_value(
        sources, "withdrawable_money", currency
    )
    withdraw_blocked_value, withdraw_blocked_present = _source_value(
        sources, "withdraw_blocked", currency
    )
    guarantee_value, guarantee_present = _source_value(
        sources, "blocked_guarantee", currency
    )

    has_positions = reported_present or positions_blocked_present
    has_withdraw = withdrawable_present or withdraw_blocked_present or guarantee_present
    negative_values = sum(
        (
            reported_present and reported_value < 0,
            positions_blocked_present and positions_blocked_value < 0,
            withdrawable_present and withdrawable_value < 0,
            withdraw_blocked_present and withdraw_blocked_value < 0,
            guarantee_present and guarantee_value < 0,
        )
    )

    reasons, difference = _cash_discrepancies(
        reported_value=reported_value,
        reported_present=reported_present,
        positions_blocked_value=positions_blocked_value,
        positions_blocked_present=positions_blocked_present,
        withdrawable_value=withdrawable_value,
        withdrawable_present=withdrawable_present,
        withdraw_blocked_value=withdraw_blocked_value,
        withdraw_blocked_present=withdraw_blocked_present,
        has_positions=has_positions,
        has_withdraw=has_withdraw,
    )
    cash_difference = (
        base.decimal_string(difference) if difference is not None else "unavailable"
    )
    cash_status = _cash_status(
        reasons=reasons,
        has_positions=has_positions,
        has_withdraw=has_withdraw,
    )

    row = {
        "currency": currency,
        "reported_money": _value_or_unavailable(
            base=base,
            values=sources["reported_money"][0],
            present=sources["reported_money"][1],
            currency=currency,
        ),
        "positions_blocked": _value_or_unavailable(
            base=base,
            values=sources["positions_blocked"][0],
            present=sources["positions_blocked"][1],
            currency=currency,
        ),
        "withdrawable_money": _value_or_unavailable(
            base=base,
            values=sources["withdrawable_money"][0],
            present=sources["withdrawable_money"][1],
            currency=currency,
        ),
        "withdraw_blocked": _value_or_unavailable(
            base=base,
            values=sources["withdraw_blocked"][0],
            present=sources["withdraw_blocked"][1],
            currency=currency,
        ),
        "blocked_guarantee": _value_or_unavailable(
            base=base,
            values=sources["blocked_guarantee"][0],
            present=sources["blocked_guarantee"][1],
            currency=currency,
        ),
        "cash_difference": cash_difference,
        "cash_difference_basis": "reported_money_minus_withdrawable_money",
        "cash_status": cash_status,
        "source_presence": {
            "positions": has_positions,
            "withdraw_limits": has_withdraw,
        },
        "discrepancy_reasons": reasons,
    }
    matched = not reasons
    both_sources = has_positions and has_withdraw
    return row, matched, both_sources, negative_values


def _cash_warnings(
    *,
    limits_loading_in_progress: bool,
    source_discrepancies: int,
    negative_values_detected: int,
) -> list[str]:
    warnings = [
        BUYING_POWER_REASON,
        (
            "reported_money and positions_blocked come from GetPositions; "
            "withdrawable_money, withdraw_blocked, and blocked_guarantee come "
            "from GetWithdrawLimits. Their meanings are preserved and are not "
            "silently merged."
        ),
        (
            "Currencies are compared independently. The gateway performs no "
            "cross-currency aggregation or FX conversion."
        ),
    ]
    if limits_loading_in_progress:
        warnings.append(
            "GetPositions reports limits_loading_in_progress=true; cash limits "
            "may still be loading."
        )
    if source_discrepancies:
        warnings.append(
            "At least one currency differs between the two source responses or "
            "is absent from one source. See cash_status and discrepancy_reasons."
        )
    if negative_values_detected:
        warnings.append(
            "At least one source returned a negative money value; the raw sign "
            "was preserved."
        )
    return warnings


def _cash_snapshot_status(
    *,
    positions_status: str,
    withdraw_limits_status: str,
    complete: bool,
) -> str:
    if positions_status == "error" and withdraw_limits_status == "error":
        return "error"
    if complete:
        return "ok"
    return "partial"


def _cash_mode(currencies: list[str]) -> str:
    if not currencies:
        return "empty"
    if len(currencies) == 1:
        return "single_currency"
    return "multi_currency"


def build_cash_liquidity_snapshot(
    *,
    base: Any,
    app_version: str,
    account: dict[str, Any],
    positions_data: dict[str, Any] | None,
    withdraw_limits_data: dict[str, Any] | None,
    positions_status: str,
    withdraw_limits_status: str,
    component_errors: list[dict[str, Any]] | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    positions = positions_data if isinstance(positions_data, dict) else {}
    withdraw = withdraw_limits_data if isinstance(withdraw_limits_data, dict) else {}
    sources = _cash_sources(base=base, positions=positions, withdraw=withdraw)

    currencies = sorted(set().union(*(present for _, present, _ in sources.values())))
    rows: list[dict[str, Any]] = []
    currencies_matched = 0
    currencies_present_in_both_sources = 0
    negative_values_detected = 0
    for currency in currencies:
        row, matched, both_sources, negative_values = _cash_row(
            base=base,
            currency=currency,
            sources=sources,
        )
        rows.append(row)
        currencies_matched += int(matched)
        currencies_present_in_both_sources += int(both_sources)
        negative_values_detected += negative_values

    source_discrepancies = len(currencies) - currencies_matched
    invalid_money_rows = sum(invalid for _, _, invalid in sources.values())
    limits_loading_in_progress = bool(
        positions.get("limits_loading_in_progress", False)
    )
    complete = (
        positions_status == "ok"
        and withdraw_limits_status == "ok"
        and invalid_money_rows == 0
        and not limits_loading_in_progress
    )
    status = _cash_snapshot_status(
        positions_status=positions_status,
        withdraw_limits_status=withdraw_limits_status,
        complete=complete,
    )
    cash_mode = _cash_mode(currencies)

    payload = {
        "status": status,
        "version": app_version,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "account": account,
        "cash_mode": cash_mode,
        "cash_by_currency": rows,
        "components": {
            "positions": {
                "status": positions_status,
                "source": "T-Invest GetPositions",
                "limits_loading_in_progress": limits_loading_in_progress,
            },
            "withdraw_limits": {
                "status": withdraw_limits_status,
                "source": "T-Invest GetWithdrawLimits",
            },
        },
        "buying_power": {
            "confirmed": False,
            "reason": BUYING_POWER_REASON,
        },
        "quality": {
            "positions_source_status": positions_status,
            "withdraw_limits_source_status": withdraw_limits_status,
            "currencies_detected": len(currencies),
            "currencies_present_in_both_sources": currencies_present_in_both_sources,
            "currencies_matched": currencies_matched,
            "source_discrepancies": source_discrepancies,
            "negative_values_detected": negative_values_detected,
            "invalid_money_rows": invalid_money_rows,
            "limits_loading_in_progress": limits_loading_in_progress,
            "buying_power_confirmed": False,
            "complete": complete,
            "no_cross_currency_aggregation": True,
        },
        "component_errors": component_errors or [],
        "trading_methods": False,
        "warnings": _cash_warnings(
            limits_loading_in_progress=limits_loading_in_progress,
            source_discrepancies=source_discrepancies,
            negative_values_detected=negative_values_detected,
        ),
    }
    return base.json_safe_value(payload)


def get_cash_liquidity_snapshot(
    *,
    base: Any,
    app_version: str,
) -> dict[str, Any]:
    base.ensure_configured()
    retrieved_at = datetime.now(timezone.utc).isoformat()

    try:
        with base.Client(base.TINVEST_TOKEN) as client:
            account_id, safe_account = base.get_open_account(client)

            positions_data: dict[str, Any] | None = None
            withdraw_limits_data: dict[str, Any] | None = None
            positions_status = "error"
            withdraw_limits_status = "error"
            errors: list[dict[str, Any]] = []

            try:
                positions_response = client.operations.get_positions(
                    account_id=account_id
                )
                positions_data = base.proto_to_dict(positions_response)
                positions_status = "ok"
            except Exception as exc:
                errors.append(
                    {
                        "component": "positions",
                        "error": _component_error(base, exc),
                    }
                )

            try:
                withdraw_limits_response = client.operations.get_withdraw_limits(
                    account_id=account_id
                )
                withdraw_limits_data = base.proto_to_dict(withdraw_limits_response)
                withdraw_limits_status = "ok"
            except Exception as exc:
                errors.append(
                    {
                        "component": "withdraw_limits",
                        "error": _component_error(base, exc),
                    }
                )

            return build_cash_liquidity_snapshot(
                base=base,
                app_version=app_version,
                account=safe_account,
                positions_data=positions_data,
                withdraw_limits_data=withdraw_limits_data,
                positions_status=positions_status,
                withdraw_limits_status=withdraw_limits_status,
                component_errors=errors,
                retrieved_at=retrieved_at,
            )
    except HTTPException:
        raise
    except grpc.RpcError as exc:
        http_status, payload = base.grpc_error_payload(exc)
        raise HTTPException(status_code=http_status, detail=payload) from exc
    except Exception as exc:
        safe_message = base.safe_error_message(exc)
        raise HTTPException(
            status_code=502,
            detail={
                "code": (
                    "GATEWAY_SDK_COMPATIBILITY_ERROR"
                    if isinstance(exc, (AttributeError, TypeError))
                    else "GATEWAY_CLIENT_ERROR"
                ),
                "exception_type": type(exc).__name__,
                "message": safe_message,
            },
        ) from exc
