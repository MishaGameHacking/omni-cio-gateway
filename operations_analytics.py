from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import grpc
from fastapi import HTTPException


PAGE_LIMIT = 1000
MAX_PAGES = 50
MAX_INSTRUMENT_GROUPS = 100

CATEGORY_ORDER = (
    "deposits",
    "withdrawals",
    "purchases",
    "sales",
    "broker_commissions",
    "service_fees",
    "margin_fees",
    "other_fees",
    "taxes",
    "coupons",
    "dividends",
    "bond_redemptions",
    "other",
)

TYPE_TO_CATEGORY = {
    # External cash flows.
    "OPERATION_TYPE_INPUT": "deposits",
    "OPERATION_TYPE_INPUT_SWIFT": "deposits",
    "OPERATION_TYPE_INPUT_ACQUIRING": "deposits",
    "OPERATION_TYPE_INP_MULTI": "deposits",
    "OPERATION_TYPE_FUNDING": "deposits",
    "OPERATION_TYPE_OUTPUT": "withdrawals",
    "OPERATION_TYPE_OUTPUT_SWIFT": "withdrawals",
    "OPERATION_TYPE_OUTPUT_ACQUIRING": "withdrawals",
    "OPERATION_TYPE_OUT_MULTI": "withdrawals",
    "OPERATION_TYPE_OUTPUT_PENALTY": "withdrawals",
    # Trades.
    "OPERATION_TYPE_BUY": "purchases",
    "OPERATION_TYPE_BUY_CARD": "purchases",
    "OPERATION_TYPE_BUY_MARGIN": "purchases",
    "OPERATION_TYPE_DELIVERY_BUY": "purchases",
    "OPERATION_TYPE_PRIMARY_ORDER": "purchases",
    "OPERATION_TYPE_SELL": "sales",
    "OPERATION_TYPE_SELL_CARD": "sales",
    "OPERATION_TYPE_SELL_MARGIN": "sales",
    "OPERATION_TYPE_DELIVERY_SELL": "sales",
    # Fees. These categories intentionally use only top-level operation.payment.
    "OPERATION_TYPE_BROKER_FEE": "broker_commissions",
    "OPERATION_TYPE_SERVICE_FEE": "service_fees",
    "OPERATION_TYPE_SUCCESS_FEE": "service_fees",
    "OPERATION_TYPE_ADVICE_FEE": "service_fees",
    "OPERATION_TYPE_TRACK_MFEE": "service_fees",
    "OPERATION_TYPE_TRACK_PFEE": "service_fees",
    "OPERATION_TYPE_OVER_COM": "service_fees",
    "OPERATION_TYPE_MARGIN_FEE": "margin_fees",
    "OPERATION_TYPE_CASH_FEE": "other_fees",
    "OPERATION_TYPE_OUT_FEE": "other_fees",
    "OPERATION_TYPE_OUT_STAMP_DUTY": "other_fees",
    "OPERATION_TYPE_OTHER_FEE": "other_fees",
    # Income and redemptions.
    "OPERATION_TYPE_COUPON": "coupons",
    "OPERATION_TYPE_DIVIDEND": "dividends",
    "OPERATION_TYPE_DIVIDEND_TRANSFER": "dividends",
    "OPERATION_TYPE_DIV_EXT": "dividends",
    "OPERATION_TYPE_BOND_REPAYMENT": "bond_redemptions",
    "OPERATION_TYPE_BOND_REPAYMENT_FULL": "bond_redemptions",
    "OPERATION_TYPE_DFA_REDEMPTION": "bond_redemptions",
}

KNOWN_OTHER_TYPES = {
    "OPERATION_TYPE_UNSPECIFIED",
    "OPERATION_TYPE_OUTPUT_SECURITIES",
    "OPERATION_TYPE_OVERNIGHT",
    "OPERATION_TYPE_INPUT_SECURITIES",
    "OPERATION_TYPE_ACCRUING_VARMARGIN",
    "OPERATION_TYPE_WRITING_OFF_VARMARGIN",
    "OPERATION_TYPE_TRANS_IIS_BS",
    "OPERATION_TYPE_TRANS_BS_BS",
    "OPERATION_TYPE_OVER_PLACEMENT",
    "OPERATION_TYPE_OVER_INCOME",
    "OPERATION_TYPE_OPTION_EXPIRATION",
    "OPERATION_TYPE_FUTURE_EXPIRATION",
    "OPERATION_TYPE_OTHER",
}

POSITIVE_EXPECTED_CATEGORIES = {
    "deposits",
    "sales",
    "coupons",
    "dividends",
    "bond_redemptions",
}
NEGATIVE_EXPECTED_CATEGORIES = {
    "withdrawals",
    "purchases",
    "broker_commissions",
    "service_fees",
    "margin_fees",
    "other_fees",
}

INSTRUMENT_ACTIVITY_CATEGORIES = {
    "purchases",
    "sales",
    "coupons",
    "dividends",
    "bond_redemptions",
}


def _operation_type(base: Any, operation: dict[str, Any]) -> str:
    return base.normalized_operation_enum(
        operation.get("type"),
        base.OPERATION_TYPE_NUMBER_TO_NAME,
        "OPERATION_TYPE_UNSPECIFIED",
    )


def _operation_state(base: Any, operation: dict[str, Any]) -> str:
    return base.normalized_operation_enum(
        operation.get("state"),
        base.OPERATION_STATE_NUMBER_TO_NAME,
        "OPERATION_STATE_UNSPECIFIED",
    )


def classify_operation(operation_type: str) -> str:
    normalized = str(operation_type or "OPERATION_TYPE_UNSPECIFIED").upper()
    if "TAX" in normalized:
        return "taxes"
    return TYPE_TO_CATEGORY.get(normalized, "other")


def _money_parts(base: Any, value: Any) -> tuple[Decimal | None, str]:
    if not isinstance(value, dict):
        return None, ""
    amount = base.decimal_from_any(value)
    currency = str(value.get("currency", "") or "").strip().upper()
    return amount, currency


def _operation_fingerprint(base: Any, operation: dict[str, Any]) -> str:
    # Operation ids can change over time, so the id itself is intentionally omitted.
    fingerprint_fields = {
        "parent_operation_id": operation.get("parent_operation_id"),
        "date": operation.get("date"),
        "type": _operation_type(base, operation),
        "state": _operation_state(base, operation),
        "instrument_uid": operation.get("instrument_uid"),
        "position_uid": operation.get("position_uid"),
        "figi": operation.get("figi"),
        "payment": operation.get("payment"),
        "quantity": operation.get("quantity"),
        "quantity_done": operation.get("quantity_done"),
        "name": operation.get("name"),
        "description": operation.get("description"),
    }
    payload = json.dumps(
        base.json_safe_value(fingerprint_fields),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _operation_sort_time(base: Any, operation: dict[str, Any]) -> datetime:
    parsed = base.parse_datetime(operation.get("date"))
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


def deduplicate_operations(
    *,
    base: Any,
    operations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    exact_seen: set[str] = set()
    commission_positions: dict[tuple[str, str, str], int] = {}
    result: list[dict[str, Any]] = []
    exact_duplicates_removed = 0
    commission_updates_collapsed = 0

    for operation in operations:
        fingerprint = _operation_fingerprint(base, operation)
        if fingerprint in exact_seen:
            exact_duplicates_removed += 1
            continue
        exact_seen.add(fingerprint)

        operation_type = _operation_type(base, operation)
        category = classify_operation(operation_type)
        parent_id = str(operation.get("parent_operation_id", "") or "").strip()
        _, currency = _money_parts(base, operation.get("payment"))

        if category in {
            "broker_commissions",
            "service_fees",
            "margin_fees",
            "other_fees",
        } and parent_id:
            semantic_key = (parent_id, operation_type, currency or "UNKNOWN")
            existing_index = commission_positions.get(semantic_key)
            if existing_index is not None:
                commission_updates_collapsed += 1
                existing = result[existing_index]
                if _operation_sort_time(base, operation) > _operation_sort_time(
                    base,
                    existing,
                ):
                    result[existing_index] = operation
                continue
            commission_positions[semantic_key] = len(result)

        result.append(operation)

    return result, {
        "exact_duplicates_removed": exact_duplicates_removed,
        "commission_updates_collapsed": commission_updates_collapsed,
        "duplicates_removed": (
            exact_duplicates_removed + commission_updates_collapsed
        ),
    }


def _empty_bucket() -> dict[str, Any]:
    return {
        "count": 0,
        "gross_amount": Decimal("0"),
        "net_payment": Decimal("0"),
        "inflow": Decimal("0"),
        "outflow": Decimal("0"),
    }


def _add_to_bucket(bucket: dict[str, Any], amount: Decimal) -> None:
    bucket["count"] += 1
    bucket["gross_amount"] += abs(amount)
    bucket["net_payment"] += amount
    if amount >= 0:
        bucket["inflow"] += amount
    else:
        bucket["outflow"] += -amount


def _serialize_bucket(base: Any, bucket: dict[str, Any]) -> dict[str, Any]:
    return {
        "count": int(bucket["count"]),
        "amount": base.decimal_string(bucket["gross_amount"]),
        "net_payment": base.decimal_string(bucket["net_payment"]),
        "inflow": base.decimal_string(bucket["inflow"]),
        "outflow": base.decimal_string(bucket["outflow"]),
    }


def _instrument_key(operation: dict[str, Any]) -> str:
    for field in ("instrument_uid", "position_uid", "figi"):
        value = str(operation.get(field, "") or "").strip()
        if value:
            return f"{field}:{value}"
    name = str(operation.get("name", "") or "").strip()
    return f"name:{name}" if name else "unidentified"


def _request_with_period(
    *,
    base: Any,
    account_id: str,
    cursor: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[Any, bool]:
    common = {
        "account_id": account_id,
        "cursor": cursor,
        "limit": PAGE_LIMIT,
        "without_commissions": False,
        "without_trades": False,
        "without_overnights": True,
    }

    try:
        return (
            base.GetOperationsByCursorRequest(
                from_=start_time,
                to=end_time,
                **common,
            ),
            True,
        )
    except TypeError:
        request = base.GetOperationsByCursorRequest(**common)
        period_fields_set = 0
        for field_name, value in (("from_", start_time), ("to", end_time)):
            if hasattr(request, field_name):
                try:
                    setattr(request, field_name, value)
                    period_fields_set += 1
                except (AttributeError, TypeError, ValueError):
                    pass
        return request, period_fields_set == 2


def load_operations_pages(
    *,
    base: Any,
    client: Any,
    account_id: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cursor = ""
    seen_cursors: set[str] = set()
    items: list[dict[str, Any]] = []
    pages_fetched = 0
    has_next = False
    cursor_loop_detected = False
    server_period_filter_applied = True

    while pages_fetched < MAX_PAGES:
        request, request_has_period = _request_with_period(
            base=base,
            account_id=account_id,
            cursor=cursor,
            start_time=start_time,
            end_time=end_time,
        )
        server_period_filter_applied = (
            server_period_filter_applied and request_has_period
        )
        response = client.operations.get_operations_by_cursor(request)
        page_items, page_has_next, next_cursor = base.operation_response_items(
            response
        )
        items.extend(page_items)
        pages_fetched += 1

        if not page_has_next or not next_cursor:
            has_next = False
            break

        has_next = True
        if next_cursor == cursor or next_cursor in seen_cursors:
            cursor_loop_detected = True
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    truncated = has_next or cursor_loop_detected
    return items, {
        "pages_fetched": pages_fetched,
        "page_limit": PAGE_LIMIT,
        "max_pages": MAX_PAGES,
        "items_received": len(items),
        "has_next": has_next,
        "truncated": truncated,
        "cursor_loop_detected": cursor_loop_detected,
        "server_period_filter_applied": server_period_filter_applied,
    }


def build_operations_analytics(
    *,
    base: Any,
    app_version: str,
    account: dict[str, Any],
    raw_operations: list[dict[str, Any]],
    period: dict[str, Any],
    pagination: dict[str, Any],
    component_errors: list[dict[str, Any]] | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    start_time = base.parse_datetime(period.get("from"))
    end_time = base.parse_datetime(period.get("to"))

    in_period: list[dict[str, Any]] = []
    outside_period = 0
    invalid_date_rows = 0
    for operation in raw_operations:
        operation_date = base.parse_datetime(operation.get("date"))
        if operation_date is None:
            invalid_date_rows += 1
            in_period.append(operation)
            continue
        if start_time is not None and operation_date < start_time:
            outside_period += 1
            continue
        if end_time is not None and operation_date > end_time:
            outside_period += 1
            continue
        in_period.append(operation)

    deduplicated, duplicate_quality = deduplicate_operations(
        base=base,
        operations=in_period,
    )
    deduplicated.sort(
        key=lambda item: _operation_sort_time(base, item),
        reverse=True,
    )

    state_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
    currency_buckets: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: {category: _empty_bucket() for category in CATEGORY_ORDER}
    )
    currency_total_net: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    instrument_groups: dict[str, dict[str, Any]] = {}

    unknown_operation_types = 0
    invalid_money_rows = 0
    executed_operations = 0
    canceled_operations = 0
    operations_in_progress = 0
    nested_commission_fields_excluded = 0
    embedded_child_operations_excluded = 0
    embedded_trades_excluded = 0
    top_level_parent_linked_operations = 0
    sign_checked = 0
    sign_mismatches: list[dict[str, Any]] = []
    currencies_detected: set[str] = set()

    for operation in deduplicated:
        operation_type = _operation_type(base, operation)
        state = _operation_state(base, operation)
        category = classify_operation(operation_type)
        state_counts[state] += 1
        category_counts[category] += 1

        if operation_type == "OPERATION_TYPE_UNSPECIFIED" or (
            operation_type not in TYPE_TO_CATEGORY
            and operation_type not in KNOWN_OTHER_TYPES
            and "TAX" not in operation_type
        ):
            unknown_operation_types += 1

        if state == "OPERATION_STATE_EXECUTED":
            executed_operations += 1
        elif state == "OPERATION_STATE_CANCELED":
            canceled_operations += 1
        elif state == "OPERATION_STATE_PROGRESS":
            operations_in_progress += 1

        child_operations = operation.get("child_operations")
        if isinstance(child_operations, list):
            embedded_child_operations_excluded += len(child_operations)
        trades_info = operation.get("trades_info")
        if isinstance(trades_info, dict):
            trades = trades_info.get("trades")
            if isinstance(trades, list):
                embedded_trades_excluded += len(trades)
        if str(operation.get("parent_operation_id", "") or "").strip():
            top_level_parent_linked_operations += 1

        nested_commission_amount, _ = _money_parts(
            base,
            operation.get("commission"),
        )
        if nested_commission_amount not in (None, Decimal("0")):
            nested_commission_fields_excluded += 1

        # Only executed top-level operation.payment changes the financial summary.
        if state != "OPERATION_STATE_EXECUTED":
            continue

        amount, currency = _money_parts(base, operation.get("payment"))
        if amount is None or not currency:
            invalid_money_rows += 1
            continue

        currencies_detected.add(currency)
        _add_to_bucket(currency_buckets[currency][category], amount)
        currency_total_net[currency] += amount

        if category in POSITIVE_EXPECTED_CATEGORIES:
            sign_checked += 1
            if amount < 0:
                sign_mismatches.append(
                    {
                        "type": operation_type,
                        "category": category,
                        "currency": currency,
                        "payment": base.decimal_string(amount),
                        "expected_sign": "nonnegative",
                    }
                )
        elif category in NEGATIVE_EXPECTED_CATEGORIES:
            sign_checked += 1
            if amount > 0:
                sign_mismatches.append(
                    {
                        "type": operation_type,
                        "category": category,
                        "currency": currency,
                        "payment": base.decimal_string(amount),
                        "expected_sign": "nonpositive",
                    }
                )

        if category in INSTRUMENT_ACTIVITY_CATEGORIES:
            key = _instrument_key(operation)
            group = instrument_groups.setdefault(
                key,
                {
                    "instrument_uid": operation.get("instrument_uid") or None,
                    "position_uid": operation.get("position_uid") or None,
                    "figi": operation.get("figi") or None,
                    "name": operation.get("name") or None,
                    "instrument_type": operation.get("instrument_type") or None,
                    "currency": currency,
                    "operation_count": 0,
                    "purchases": Decimal("0"),
                    "sales": Decimal("0"),
                    "coupons": Decimal("0"),
                    "dividends": Decimal("0"),
                    "bond_redemptions": Decimal("0"),
                    "net_payment": Decimal("0"),
                },
            )
            group["operation_count"] += 1
            group[category] += abs(amount)
            group["net_payment"] += amount

    cash_rows: list[dict[str, Any]] = []
    net_external_flow: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    category_total_checks: list[dict[str, Any]] = []

    for currency in sorted(currencies_detected):
        categories = currency_buckets[currency]
        cash_rows.append(
            {
                "currency": currency,
                **{
                    category: _serialize_bucket(base, categories[category])
                    for category in CATEGORY_ORDER
                },
            }
        )

        deposits = categories["deposits"]["gross_amount"]
        withdrawals = categories["withdrawals"]["gross_amount"]
        purchases = categories["purchases"]["gross_amount"]
        sales = categories["sales"]["gross_amount"]
        net_external_flow.append(
            {
                "currency": currency,
                "deposits": base.decimal_string(deposits),
                "withdrawals": base.decimal_string(withdrawals),
                "net_external_flow": base.decimal_string(
                    deposits - withdrawals
                ),
            }
        )
        turnover.append(
            {
                "currency": currency,
                "purchases": base.decimal_string(purchases),
                "sales": base.decimal_string(sales),
                "turnover": base.decimal_string(purchases + sales),
            }
        )

        categories_net = sum(
            (
                categories[category]["net_payment"]
                for category in CATEGORY_ORDER
            ),
            Decimal("0"),
        )
        operations_net = currency_total_net[currency]
        difference = categories_net - operations_net
        category_total_checks.append(
            {
                "currency": currency,
                "operations_net_payment": base.decimal_string(operations_net),
                "categories_net_payment": base.decimal_string(categories_net),
                "difference": base.decimal_string(difference),
                "status": "passed" if difference == 0 else "failed",
            }
        )

    sign_status = "passed" if not sign_mismatches else "warning"
    category_totals_status = (
        "passed"
        if all(check["status"] == "passed" for check in category_total_checks)
        and invalid_money_rows == 0
        else "warning"
    )

    commission_protection = {
        "status": "applied",
        "canonical_cash_basis": "top_level_operation.payment",
        "nested_commission_fields_excluded": nested_commission_fields_excluded,
        "parent_type_updates_collapsed": duplicate_quality[
            "commission_updates_collapsed"
        ],
        "passed": True,
    }
    parent_child_protection = {
        "status": "applied",
        "top_level_operations_only": True,
        "embedded_child_operations_excluded": (
            embedded_child_operations_excluded
        ),
        "embedded_trades_excluded": embedded_trades_excluded,
        "top_level_parent_linked_operations": (
            top_level_parent_linked_operations
        ),
        "passed": True,
    }

    reconciliation_status = (
        "ok"
        if sign_status == "passed" and category_totals_status == "passed"
        else "warning"
    )
    reconciliation_confirmed = reconciliation_status == "ok"

    serialized_instrument_groups: list[dict[str, Any]] = []
    for group in instrument_groups.values():
        serialized_instrument_groups.append(
            {
                **{
                    key: value
                    for key, value in group.items()
                    if key
                    not in {
                        "purchases",
                        "sales",
                        "coupons",
                        "dividends",
                        "bond_redemptions",
                        "net_payment",
                    }
                },
                "purchases": base.decimal_string(group["purchases"]),
                "sales": base.decimal_string(group["sales"]),
                "coupons": base.decimal_string(group["coupons"]),
                "dividends": base.decimal_string(group["dividends"]),
                "bond_redemptions": base.decimal_string(
                    group["bond_redemptions"]
                ),
                "net_payment": base.decimal_string(group["net_payment"]),
            }
        )
    serialized_instrument_groups.sort(
        key=lambda row: Decimal(str(row["purchases"]))
        + Decimal(str(row["sales"])),
        reverse=True,
    )
    instrument_groups_total = len(serialized_instrument_groups)
    instrument_groups_skipped = max(
        0,
        instrument_groups_total - MAX_INSTRUMENT_GROUPS,
    )
    serialized_instrument_groups = serialized_instrument_groups[
        :MAX_INSTRUMENT_GROUPS
    ]

    pagination_complete = not bool(pagination.get("truncated", False))
    errors = component_errors or []
    complete = (
        not errors
        and pagination_complete
        and invalid_date_rows == 0
        and invalid_money_rows == 0
        and reconciliation_confirmed
    )
    status = "ok" if complete else "partial"

    warnings = [
        (
            "Financial summaries include only OPERATION_STATE_EXECUTED top-level "
            "operations. Canceled and in-progress operations are counted but do "
            "not affect cash totals."
        ),
        (
            "Commission totals use top-level operation.payment only. Nested "
            "commission fields are diagnostic metadata and are not added again."
        ),
        (
            "Repeated parent-linked fee updates are collapsed by "
            "parent_operation_id, operation type, and currency."
        ),
        (
            "Embedded child_operations and trades_info are not independently "
            "summed, preventing parent/child double counting."
        ),
        (
            "Currencies are calculated independently. The gateway performs no "
            "FX conversion or cross-currency aggregation."
        ),
        (
            "Operation IDs are omitted from analytics because T-Invest states "
            "that operation IDs can change over time."
        ),
        (
            "API operation history can be incomplete after corporate actions. "
            "Use the official broker report for exact reconciliation."
        ),
        (
            "The operations service reports instrument quantities in units, not "
            "lots. This endpoint remains read-only and exposes no trading methods."
        ),
    ]
    if pagination.get("truncated"):
        warnings.append(
            "Pagination did not finish; totals cover only the pages received."
        )
    if not pagination.get("server_period_filter_applied", True):
        warnings.append(
            "The installed SDK did not accept period fields in the cursor request; "
            "the gateway applied the requested UTC period locally."
        )
    if sign_mismatches:
        warnings.append(
            "At least one executed payment had an unexpected sign for its "
            "category. Raw signs were preserved; see payment_sign_check."
        )
    if invalid_money_rows:
        warnings.append(
            "At least one executed operation had no valid payment amount or "
            "currency and was excluded from financial totals."
        )
    if unknown_operation_types:
        warnings.append(
            "At least one operation type was not recognized by the local "
            "classification table and was placed in other."
        )
    if instrument_groups_skipped:
        warnings.append(
            f"Instrument activity was limited to {MAX_INSTRUMENT_GROUPS} groups."
        )

    payload = {
        "status": status,
        "version": app_version,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "account": account,
        "period": period,
        "pagination": pagination,
        "operations_count": len(deduplicated),
        "duplicates_removed": duplicate_quality["duplicates_removed"],
        "executed_operations": executed_operations,
        "canceled_operations": canceled_operations,
        "operations_in_progress": operations_in_progress,
        "state_counts": dict(sorted(state_counts.items())),
        "category_counts": {
            category: int(category_counts.get(category, 0))
            for category in CATEGORY_ORDER
        },
        "cash_summary_by_currency": cash_rows,
        "net_external_flow": net_external_flow,
        "turnover": turnover,
        "instrument_activity": serialized_instrument_groups,
        "reconciliation": {
            "executed_only": True,
            "payment_sign_check": {
                "status": sign_status,
                "checked": sign_checked,
                "mismatches": len(sign_mismatches),
                "examples": sign_mismatches[:20],
            },
            "category_totals_check": {
                "status": category_totals_status,
                "checks": category_total_checks,
            },
            "commission_double_count_protection": commission_protection,
            "parent_child_double_count_protection": parent_child_protection,
            "status": reconciliation_status,
        },
        "quality": {
            "raw_items_received": len(raw_operations),
            "items_outside_period": outside_period,
            "invalid_date_rows": invalid_date_rows,
            "exact_duplicates_removed": duplicate_quality[
                "exact_duplicates_removed"
            ],
            "commission_updates_collapsed": duplicate_quality[
                "commission_updates_collapsed"
            ],
            "currencies_detected": len(currencies_detected),
            "unknown_operation_types": unknown_operation_types,
            "invalid_money_rows": invalid_money_rows,
            "pagination_complete": pagination_complete,
            "reconciliation_confirmed": reconciliation_confirmed,
            "instrument_groups_total": instrument_groups_total,
            "instrument_groups_returned": len(serialized_instrument_groups),
            "instrument_groups_skipped_by_limit": instrument_groups_skipped,
            "complete": complete,
            "no_cross_currency_aggregation": True,
            "read_only": True,
        },
        "complete": complete,
        "component_errors": errors,
        "trading_methods": False,
        "warnings": warnings,
    }
    return base.json_safe_value(payload)


def get_operations_analytics(
    *,
    base: Any,
    app_version: str,
    days: int,
) -> dict[str, Any]:
    base.ensure_configured()
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    try:
        with base.Client(base.TINVEST_TOKEN) as client:
            account_id, safe_account = base.get_open_account(client)
            raw_operations, pagination = load_operations_pages(
                base=base,
                client=client,
                account_id=account_id,
                start_time=start_time,
                end_time=end_time,
            )
            return build_operations_analytics(
                base=base,
                app_version=app_version,
                account=safe_account,
                raw_operations=raw_operations,
                period={
                    "from": start_time.isoformat(),
                    "to": end_time.isoformat(),
                    "days": days,
                },
                pagination=pagination,
                component_errors=[],
                retrieved_at=end_time.isoformat(),
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
                    else "GATEWAY_OPERATIONS_ANALYTICS_ERROR"
                ),
                "exception_type": type(exc).__name__,
                "message": safe_message,
            },
        ) from exc
