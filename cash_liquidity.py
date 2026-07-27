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
    withdraw = (
        withdraw_limits_data
        if isinstance(withdraw_limits_data, dict)
        else {}
    )

    (
        reported_money,
        reported_money_present,
        invalid_reported_money,
    ) = _money_map(base=base, rows=positions.get("money"))
    (
        positions_blocked,
        positions_blocked_present,
        invalid_positions_blocked,
    ) = _money_map(base=base, rows=positions.get("blocked"))
    (
        withdrawable_money,
        withdrawable_money_present,
        invalid_withdrawable_money,
    ) = _money_map(base=base, rows=withdraw.get("money"))
    (
        withdraw_blocked,
        withdraw_blocked_present,
        invalid_withdraw_blocked,
    ) = _money_map(base=base, rows=withdraw.get("blocked"))
    (
        blocked_guarantee,
        blocked_guarantee_present,
        invalid_blocked_guarantee,
    ) = _money_map(base=base, rows=withdraw.get("blocked_guarantee"))

    currencies = sorted(
        reported_money_present
        | positions_blocked_present
        | withdrawable_money_present
        | withdraw_blocked_present
        | blocked_guarantee_present
    )

    rows: list[dict[str, Any]] = []
    currencies_matched = 0
    currencies_present_in_both_sources = 0
    source_discrepancies = 0
    negative_values_detected = 0

    for currency in currencies:
        has_positions = (
            currency in reported_money_present
            or currency in positions_blocked_present
        )
        has_withdraw = (
            currency in withdrawable_money_present
            or currency in withdraw_blocked_present
            or currency in blocked_guarantee_present
        )
        if has_positions and has_withdraw:
            currencies_present_in_both_sources += 1

        reported_value = reported_money.get(currency, Decimal("0"))
        positions_blocked_value = positions_blocked.get(
            currency,
            Decimal("0"),
        )
        withdrawable_value = withdrawable_money.get(
            currency,
            Decimal("0"),
        )
        withdraw_blocked_value = withdraw_blocked.get(
            currency,
            Decimal("0"),
        )
        guarantee_value = blocked_guarantee.get(
            currency,
            Decimal("0"),
        )

        negative_values_detected += sum(
            value < 0
            for value, present_set in (
                (reported_value, reported_money_present),
                (positions_blocked_value, positions_blocked_present),
                (withdrawable_value, withdrawable_money_present),
                (withdraw_blocked_value, withdraw_blocked_present),
                (guarantee_value, blocked_guarantee_present),
            )
            if currency in present_set
        )

        reasons: list[str] = []
        cash_difference: str = "unavailable"
        if (
            currency in reported_money_present
            and currency in withdrawable_money_present
        ):
            difference = reported_value - withdrawable_value
            cash_difference = base.decimal_string(difference)
            if difference != 0:
                reasons.append("reported_money_differs_from_withdrawable_money")
        else:
            reasons.append("money_value_missing_from_one_source")

        if (
            currency in positions_blocked_present
            and currency in withdraw_blocked_present
            and positions_blocked_value != withdraw_blocked_value
        ):
            reasons.append("blocked_value_differs_between_sources")
        elif (
            currency in positions_blocked_present
        ) != (
            currency in withdraw_blocked_present
        ):
            reasons.append("blocked_value_missing_from_one_source")

        if not has_positions:
            reasons.append("currency_missing_from_positions")
        if not has_withdraw:
            reasons.append("currency_missing_from_withdraw_limits")

        if reasons:
            source_discrepancies += 1
            if has_positions and has_withdraw:
                cash_status = "source_difference"
            elif has_positions:
                cash_status = "positions_only"
            elif has_withdraw:
                cash_status = "withdraw_limits_only"
            else:
                cash_status = "unavailable"
        else:
            cash_status = "matched"
            currencies_matched += 1

        rows.append(
            {
                "currency": currency,
                "reported_money": _value_or_unavailable(
                    base=base,
                    values=reported_money,
                    present=reported_money_present,
                    currency=currency,
                ),
                "positions_blocked": _value_or_unavailable(
                    base=base,
                    values=positions_blocked,
                    present=positions_blocked_present,
                    currency=currency,
                ),
                "withdrawable_money": _value_or_unavailable(
                    base=base,
                    values=withdrawable_money,
                    present=withdrawable_money_present,
                    currency=currency,
                ),
                "withdraw_blocked": _value_or_unavailable(
                    base=base,
                    values=withdraw_blocked,
                    present=withdraw_blocked_present,
                    currency=currency,
                ),
                "blocked_guarantee": _value_or_unavailable(
                    base=base,
                    values=blocked_guarantee,
                    present=blocked_guarantee_present,
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
        )

    invalid_money_rows = sum(
        (
            invalid_reported_money,
            invalid_positions_blocked,
            invalid_withdrawable_money,
            invalid_withdraw_blocked,
            invalid_blocked_guarantee,
        )
    )
    limits_loading_in_progress = bool(
        positions.get("limits_loading_in_progress", False)
    )
    both_sources_ok = (
        positions_status == "ok" and withdraw_limits_status == "ok"
    )
    complete = (
        both_sources_ok
        and invalid_money_rows == 0
        and not limits_loading_in_progress
    )

    if positions_status == "error" and withdraw_limits_status == "error":
        status = "error"
    elif not complete:
        status = "partial"
    else:
        status = "ok"

    if not currencies:
        cash_mode = "empty"
    elif len(currencies) == 1:
        cash_mode = "single_currency"
    else:
        cash_mode = "multi_currency"

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
            "currencies_present_in_both_sources": (
                currencies_present_in_both_sources
            ),
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
        "warnings": warnings,
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
                withdraw_limits_response = (
                    client.operations.get_withdraw_limits(
                        account_id=account_id
                    )
                )
                withdraw_limits_data = base.proto_to_dict(
                    withdraw_limits_response
                )
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
