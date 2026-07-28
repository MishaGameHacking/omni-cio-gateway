from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, TypeVar

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataIssue,
    DataQuality,
    IssueSeverity,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.operations import (
    CashFlowBucketV1,
    CategoryCashFlowV1,
    CategoryTotalCheckV1,
    CategoryTotalsCheckV1,
    CheckStatus,
    CommissionDoubleCountProtectionV1,
    CurrencyCashFlowV1,
    ExpectedPaymentSign,
    InstrumentActivityV1,
    NetExternalFlowV1,
    OperationCategory,
    OperationCategoryCountV1,
    OperationsAnalyticsV1,
    OperationsPaginationV1,
    OperationsPeriodV1,
    OperationsReconciliationV1,
    OperationsSourceQualityV1,
    OperationStateCountV1,
    ParentChildDoubleCountProtectionV1,
    PaymentSignCheckV1,
    PaymentSignExampleV1,
    ReconciliationStatus,
    TurnoverV1,
)


class OperationsAnalyticsAdapterError(ValueError):
    """The legacy operations analytics payload cannot satisfy contract v1."""


EnumT = TypeVar("EnumT", bound=StrEnum)


def _obj(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OperationsAnalyticsAdapterError(f"{field} must be an object")
    return value


def _rows(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise OperationsAnalyticsAdapterError(f"{field} must be an array")
    return value


def _text(
    value: object,
    field: str,
    *,
    optional: bool = False,
) -> str | None:
    if value is None and optional:
        return None
    text = str(value or "").strip()
    if not text:
        if optional:
            return None
        raise OperationsAnalyticsAdapterError(f"{field} must not be empty")
    return text


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise OperationsAnalyticsAdapterError(f"{field} must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value)
        except ValueError as exc:
            raise OperationsAnalyticsAdapterError(
                f"{field} must be an integer"
            ) from exc
    else:
        raise OperationsAnalyticsAdapterError(f"{field} must be an integer")
    if result < 0:
        raise OperationsAnalyticsAdapterError(f"{field} must be nonnegative")
    return result


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise OperationsAnalyticsAdapterError(f"{field} must be a boolean")
    return value


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise OperationsAnalyticsAdapterError(f"{field} must be a decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise OperationsAnalyticsAdapterError(
            f"{field} must be a decimal"
        ) from exc
    if not result.is_finite():
        raise OperationsAnalyticsAdapterError(f"{field} must be finite")
    return result


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        text = _text(value, field)
        assert text is not None
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise OperationsAnalyticsAdapterError(
                f"{field} must be an ISO timestamp"
            ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise OperationsAnalyticsAdapterError(
            f"{field} must be timezone-aware"
        )
    return result


def _currency(value: object, field: str) -> str:
    text = _text(value, field)
    assert text is not None
    result = text.upper()
    if len(result) != 3 or not result.isalpha():
        raise OperationsAnalyticsAdapterError(
            f"{field} must be a three-letter currency"
        )
    return result


def _enum_value(
    enum_type: type[EnumT],
    value: object,
    field: str,
) -> EnumT:
    text = _text(value, field)
    assert text is not None
    try:
        return enum_type(text)
    except ValueError as exc:
        raise OperationsAnalyticsAdapterError(
            f"{field} contains an unsupported value"
        ) from exc


def _count(row: Mapping[str, Any], field: str) -> int:
    return _integer(row.get(field), field)


def _cash_flow_rows(
    payload: Mapping[str, Any],
) -> tuple[CurrencyCashFlowV1, ...]:
    result: list[CurrencyCashFlowV1] = []
    items = _rows(
        payload.get("cash_summary_by_currency", ()),
        "cash_summary_by_currency",
    )
    for index, item in enumerate(items):
        row = _obj(item, f"cash_summary_by_currency[{index}]")
        categories: list[CategoryCashFlowV1] = []
        for category in OperationCategory:
            bucket = _obj(
                row.get(category.value),
                f"cash_summary_by_currency[{index}].{category.value}",
            )
            categories.append(
                CategoryCashFlowV1(
                    category=category,
                    bucket=CashFlowBucketV1(
                        count=_integer(bucket.get("count"), "count"),
                        gross_amount=_decimal(bucket.get("amount"), "amount"),
                        net_payment=_decimal(
                            bucket.get("net_payment"),
                            "net_payment",
                        ),
                        inflow=_decimal(bucket.get("inflow"), "inflow"),
                        outflow=_decimal(bucket.get("outflow"), "outflow"),
                    ),
                )
            )
        result.append(
            CurrencyCashFlowV1(
                currency=_currency(row.get("currency"), "currency"),
                categories=tuple(categories),
            )
        )
    return tuple(result)


def _external_flow_rows(
    payload: Mapping[str, Any],
) -> tuple[NetExternalFlowV1, ...]:
    result: list[NetExternalFlowV1] = []
    for index, item in enumerate(
        _rows(payload.get("net_external_flow", ()), "net_external_flow")
    ):
        row = _obj(item, f"net_external_flow[{index}]")
        result.append(
            NetExternalFlowV1(
                currency=_currency(row.get("currency"), "currency"),
                deposits=_decimal(row.get("deposits"), "deposits"),
                withdrawals=_decimal(row.get("withdrawals"), "withdrawals"),
                net_external_flow=_decimal(
                    row.get("net_external_flow"),
                    "net_external_flow",
                ),
            )
        )
    return tuple(result)


def _turnover_rows(payload: Mapping[str, Any]) -> tuple[TurnoverV1, ...]:
    result: list[TurnoverV1] = []
    for index, item in enumerate(
        _rows(payload.get("turnover", ()), "turnover")
    ):
        row = _obj(item, f"turnover[{index}]")
        result.append(
            TurnoverV1(
                currency=_currency(row.get("currency"), "currency"),
                purchases=_decimal(row.get("purchases"), "purchases"),
                sales=_decimal(row.get("sales"), "sales"),
                turnover=_decimal(row.get("turnover"), "turnover"),
            )
        )
    return tuple(result)


def _instrument_rows(
    payload: Mapping[str, Any],
) -> tuple[InstrumentActivityV1, ...]:
    result: list[InstrumentActivityV1] = []
    for index, item in enumerate(
        _rows(payload.get("instrument_activity", ()), "instrument_activity")
    ):
        row = _obj(item, f"instrument_activity[{index}]")
        result.append(
            InstrumentActivityV1(
                currency=_currency(row.get("currency"), "currency"),
                operation_count=_integer(
                    row.get("operation_count"),
                    "operation_count",
                ),
                purchases=_decimal(row.get("purchases"), "purchases"),
                sales=_decimal(row.get("sales"), "sales"),
                coupons=_decimal(row.get("coupons"), "coupons"),
                dividends=_decimal(row.get("dividends"), "dividends"),
                bond_redemptions=_decimal(
                    row.get("bond_redemptions"),
                    "bond_redemptions",
                ),
                net_payment=_decimal(row.get("net_payment"), "net_payment"),
                instrument_uid=_text(
                    row.get("instrument_uid"),
                    "instrument_uid",
                    optional=True,
                ),
                position_uid=_text(
                    row.get("position_uid"),
                    "position_uid",
                    optional=True,
                ),
                figi=_text(row.get("figi"), "figi", optional=True),
                name=_text(row.get("name"), "name", optional=True),
                instrument_type=_text(
                    row.get("instrument_type"),
                    "instrument_type",
                    optional=True,
                ),
            )
        )
    return tuple(result)


def _payment_sign_check(row: Mapping[str, Any]) -> PaymentSignCheckV1:
    examples: list[PaymentSignExampleV1] = []
    for index, item in enumerate(_rows(row.get("examples", ()), "examples")):
        example = _obj(item, f"examples[{index}]")
        examples.append(
            PaymentSignExampleV1(
                operation_type=_text(example.get("type"), "type") or "",
                category=_enum_value(
                    OperationCategory,
                    example.get("category"),
                    "category",
                ),
                currency=_currency(example.get("currency"), "currency"),
                payment=_decimal(example.get("payment"), "payment"),
                expected_sign=_enum_value(
                    ExpectedPaymentSign,
                    example.get("expected_sign"),
                    "expected_sign",
                ),
            )
        )
    return PaymentSignCheckV1(
        status=_enum_value(CheckStatus, row.get("status"), "status"),
        checked=_integer(row.get("checked"), "checked"),
        mismatches=_integer(row.get("mismatches"), "mismatches"),
        examples=tuple(examples),
    )


def _category_totals_check(row: Mapping[str, Any]) -> CategoryTotalsCheckV1:
    checks: list[CategoryTotalCheckV1] = []
    for index, item in enumerate(_rows(row.get("checks", ()), "checks")):
        check = _obj(item, f"checks[{index}]")
        checks.append(
            CategoryTotalCheckV1(
                currency=_currency(check.get("currency"), "currency"),
                operations_net_payment=_decimal(
                    check.get("operations_net_payment"),
                    "operations_net_payment",
                ),
                categories_net_payment=_decimal(
                    check.get("categories_net_payment"),
                    "categories_net_payment",
                ),
                difference=_decimal(check.get("difference"), "difference"),
                status=_enum_value(
                    CheckStatus,
                    check.get("status"),
                    "status",
                ),
            )
        )
    return CategoryTotalsCheckV1(
        status=_enum_value(CheckStatus, row.get("status"), "status"),
        checks=tuple(checks),
    )


def _reconciliation(payload: Mapping[str, Any]) -> OperationsReconciliationV1:
    row = _obj(payload.get("reconciliation"), "reconciliation")
    commission = _obj(
        row.get("commission_double_count_protection"),
        "commission_double_count_protection",
    )
    parent_child = _obj(
        row.get("parent_child_double_count_protection"),
        "parent_child_double_count_protection",
    )
    return OperationsReconciliationV1(
        executed_only=_boolean(row.get("executed_only"), "executed_only"),
        payment_sign_check=_payment_sign_check(
            _obj(row.get("payment_sign_check"), "payment_sign_check")
        ),
        category_totals_check=_category_totals_check(
            _obj(row.get("category_totals_check"), "category_totals_check")
        ),
        commission_double_count_protection=(
            CommissionDoubleCountProtectionV1(
                status=_enum_value(
                    CheckStatus,
                    commission.get("status"),
                    "status",
                ),
                canonical_cash_basis=_text(
                    commission.get("canonical_cash_basis"),
                    "canonical_cash_basis",
                )
                or "",
                nested_commission_fields_excluded=_integer(
                    commission.get("nested_commission_fields_excluded"),
                    "nested_commission_fields_excluded",
                ),
                parent_type_updates_collapsed=_integer(
                    commission.get("parent_type_updates_collapsed"),
                    "parent_type_updates_collapsed",
                ),
                passed=_boolean(commission.get("passed"), "passed"),
            )
        ),
        parent_child_double_count_protection=(
            ParentChildDoubleCountProtectionV1(
                status=_enum_value(
                    CheckStatus,
                    parent_child.get("status"),
                    "status",
                ),
                top_level_operations_only=_boolean(
                    parent_child.get("top_level_operations_only"),
                    "top_level_operations_only",
                ),
                embedded_child_operations_excluded=_integer(
                    parent_child.get("embedded_child_operations_excluded"),
                    "embedded_child_operations_excluded",
                ),
                embedded_trades_excluded=_integer(
                    parent_child.get("embedded_trades_excluded"),
                    "embedded_trades_excluded",
                ),
                top_level_parent_linked_operations=_integer(
                    parent_child.get("top_level_parent_linked_operations"),
                    "top_level_parent_linked_operations",
                ),
                passed=_boolean(parent_child.get("passed"), "passed"),
            )
        ),
        status=_enum_value(
            ReconciliationStatus,
            row.get("status"),
            "status",
        ),
    )


def _source_quality(payload: Mapping[str, Any]) -> OperationsSourceQualityV1:
    row = _obj(payload.get("quality"), "quality")
    return OperationsSourceQualityV1(
        raw_items_received=_count(row, "raw_items_received"),
        items_outside_period=_count(row, "items_outside_period"),
        invalid_date_rows=_count(row, "invalid_date_rows"),
        exact_duplicates_removed=_count(row, "exact_duplicates_removed"),
        commission_updates_collapsed=_count(
            row,
            "commission_updates_collapsed",
        ),
        currencies_detected=_count(row, "currencies_detected"),
        unknown_operation_types=_count(row, "unknown_operation_types"),
        invalid_money_rows=_count(row, "invalid_money_rows"),
        pagination_complete=_boolean(
            row.get("pagination_complete"),
            "pagination_complete",
        ),
        reconciliation_confirmed=_boolean(
            row.get("reconciliation_confirmed"),
            "reconciliation_confirmed",
        ),
        instrument_groups_total=_count(row, "instrument_groups_total"),
        instrument_groups_returned=_count(
            row,
            "instrument_groups_returned",
        ),
        instrument_groups_skipped_by_limit=_count(
            row,
            "instrument_groups_skipped_by_limit",
        ),
        complete=_boolean(row.get("complete"), "complete"),
        no_cross_currency_aggregation=_boolean(
            row.get("no_cross_currency_aggregation"),
            "no_cross_currency_aggregation",
        ),
        read_only=_boolean(row.get("read_only"), "read_only"),
    )


def _issues(
    payload: Mapping[str, Any],
    quality: OperationsSourceQualityV1,
    instrument_activity: tuple[InstrumentActivityV1, ...],
    component_error_count: int,
) -> tuple[DataIssue, ...]:
    result: list[DataIssue] = []

    def add(
        code: str,
        severity: IssueSeverity,
        message: str,
        component: str,
    ) -> None:
        result.append(
            DataIssue(
                code=code,
                severity=severity,
                message=message,
                component=component,
            )
        )

    if quality.items_outside_period:
        add(
            "ITEMS_OUTSIDE_PERIOD",
            IssueSeverity.INFO,
            "Source rows outside the requested period were excluded.",
            "period",
        )
    if quality.exact_duplicates_removed:
        add(
            "EXACT_DUPLICATES_REMOVED",
            IssueSeverity.INFO,
            "Exact duplicate operation rows were removed.",
            "deduplication",
        )
    if quality.commission_updates_collapsed:
        add(
            "COMMISSION_UPDATES_COLLAPSED",
            IssueSeverity.INFO,
            "Repeated parent-linked commission updates were collapsed.",
            "deduplication",
        )
    if quality.invalid_date_rows:
        add(
            "INVALID_OPERATION_DATES",
            IssueSeverity.ERROR,
            "At least one operation row had no valid timestamp.",
            "period",
        )
    if quality.invalid_money_rows:
        add(
            "INVALID_OPERATION_MONEY",
            IssueSeverity.ERROR,
            "At least one executed operation had invalid amount or currency.",
            "cash_flow",
        )
    if quality.unknown_operation_types:
        add(
            "UNKNOWN_OPERATION_TYPES",
            IssueSeverity.WARNING,
            "At least one operation type was classified as other.",
            "classification",
        )
    if not quality.pagination_complete:
        add(
            "OPERATIONS_PAGINATION_TRUNCATED",
            IssueSeverity.ERROR,
            "Operation totals cover only the pages received.",
            "pagination",
        )
    if not quality.reconciliation_confirmed:
        add(
            "OPERATIONS_RECONCILIATION_UNCONFIRMED",
            IssueSeverity.ERROR,
            "Operation category and sign reconciliation was not confirmed.",
            "reconciliation",
        )
    if quality.instrument_groups_skipped_by_limit:
        add(
            "INSTRUMENT_ACTIVITY_TRUNCATED",
            IssueSeverity.WARNING,
            "Instrument activity groups were limited by the source response.",
            "instrument_activity",
        )
    if component_error_count:
        add(
            "OPERATIONS_COMPONENT_ERRORS",
            IssueSeverity.ERROR,
            "One or more source components returned an error.",
            "source",
        )
    if any(
        not any((row.instrument_uid, row.position_uid, row.figi))
        for row in instrument_activity
    ):
        add(
            "UNSTABLE_INSTRUMENT_IDENTITY",
            IssueSeverity.WARNING,
            "At least one instrument activity row has no stable identifier.",
            "instrument_activity",
        )
    if str(payload.get("status", "")).lower() != "ok" and not any(
        issue.severity in (IssueSeverity.WARNING, IssueSeverity.ERROR)
        for issue in result
    ):
        add(
            "SOURCE_STATUS_PARTIAL",
            IssueSeverity.WARNING,
            "The source marked operations analytics as partial.",
            "source",
        )
    return tuple(result)


def operations_analytics_v1_from_payload(
    payload: Mapping[str, Any],
) -> OperationsAnalyticsV1:
    """Validate and map the current read-only operations analytics payload."""
    if payload.get("trading_methods") is not False:
        raise OperationsAnalyticsAdapterError(
            "trading_methods must be explicitly false"
        )

    retrieved_at = _timestamp(payload.get("retrieved_at"), "retrieved_at")
    period = _obj(payload.get("period"), "period")
    pagination = _obj(payload.get("pagination"), "pagination")
    account = _obj(payload.get("account"), "account")
    component_errors = _rows(
        payload.get("component_errors", ()),
        "component_errors",
    )

    cash_flows = _cash_flow_rows(payload)
    external_flows = _external_flow_rows(payload)
    turnovers = _turnover_rows(payload)
    instruments = _instrument_rows(payload)
    reconciliation = _reconciliation(payload)
    source_quality = _source_quality(payload)
    issues = _issues(
        payload,
        source_quality,
        instruments,
        len(component_errors),
    )

    blocking_errors = any(
        issue.severity == IssueSeverity.ERROR for issue in issues
    )
    blocking_warnings = any(
        issue.severity == IssueSeverity.WARNING for issue in issues
    )
    source_complete = (
        str(payload.get("status", "")).lower() == "ok"
        and payload.get("complete") is True
        and source_quality.complete
        and not blocking_errors
        and not blocking_warnings
    )
    if source_complete:
        data_quality = DataQuality.VERIFIED
        completeness = Completeness.COMPLETE
    elif blocking_errors:
        data_quality = DataQuality.DEGRADED
        completeness = Completeness.INCOMPLETE
    else:
        data_quality = DataQuality.PARTIAL
        completeness = Completeness.PARTIAL

    warnings = tuple(
        str(item)[:512]
        for item in _rows(payload.get("warnings", ()), "warnings")
        if str(item).strip()
    )
    metadata = ContractMetadata(
        schema_name="operations_analytics",
        retrieved_at=retrieved_at,
        account=AccountReference(
            masked_id=_text(account.get("masked_id"), "account.masked_id") or "",
            account_type=_text(
                account.get("name") or account.get("account_type"),
                "account.account_type",
                optional=True,
            ),
        ),
        provenance=(
            SourceReference(
                provider="t-invest",
                operation="get_operations_analytics",
                retrieved_at=retrieved_at,
                source_id=_text(payload.get("version"), "version", optional=True),
            ),
        ),
        quality=QualityMetadata(
            quality=data_quality,
            completeness=completeness,
            issues=issues,
            warnings=warnings,
        ),
    )

    state_counts_row = _obj(payload.get("state_counts"), "state_counts")
    category_counts_row = _obj(
        payload.get("category_counts"),
        "category_counts",
    )

    return OperationsAnalyticsV1(
        metadata=metadata,
        period=OperationsPeriodV1(
            started_at=_timestamp(period.get("from"), "period.from"),
            ended_at=_timestamp(period.get("to"), "period.to"),
            days=_integer(period.get("days"), "period.days"),
        ),
        pagination=OperationsPaginationV1(
            pages_fetched=_integer(
                pagination.get("pages_fetched"),
                "pagination.pages_fetched",
            ),
            page_limit=_integer(
                pagination.get("page_limit"),
                "pagination.page_limit",
            ),
            max_pages=_integer(
                pagination.get("max_pages"),
                "pagination.max_pages",
            ),
            items_received=_integer(
                pagination.get("items_received"),
                "pagination.items_received",
            ),
            has_next=_boolean(
                pagination.get("has_next"),
                "pagination.has_next",
            ),
            truncated=_boolean(
                pagination.get("truncated"),
                "pagination.truncated",
            ),
            cursor_loop_detected=_boolean(
                pagination.get("cursor_loop_detected"),
                "pagination.cursor_loop_detected",
            ),
            server_period_filter_applied=_boolean(
                pagination.get("server_period_filter_applied"),
                "pagination.server_period_filter_applied",
            ),
        ),
        operations_count=_integer(
            payload.get("operations_count"),
            "operations_count",
        ),
        duplicates_removed=_integer(
            payload.get("duplicates_removed"),
            "duplicates_removed",
        ),
        executed_operations=_integer(
            payload.get("executed_operations"),
            "executed_operations",
        ),
        canceled_operations=_integer(
            payload.get("canceled_operations"),
            "canceled_operations",
        ),
        operations_in_progress=_integer(
            payload.get("operations_in_progress"),
            "operations_in_progress",
        ),
        state_counts=tuple(
            OperationStateCountV1(
                state=str(state),
                count=_integer(count, f"state_counts.{state}"),
            )
            for state, count in sorted(state_counts_row.items())
        ),
        category_counts=tuple(
            OperationCategoryCountV1(
                category=category,
                count=_integer(
                    category_counts_row.get(category.value),
                    f"category_counts.{category.value}",
                ),
            )
            for category in OperationCategory
        ),
        cash_flows_by_currency=cash_flows,
        net_external_flow=external_flows,
        turnover=turnovers,
        instrument_activity=instruments,
        reconciliation=reconciliation,
        source_quality=source_quality,
    )
