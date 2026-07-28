from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]


class OperationCategory(StrEnum):
    DEPOSITS = "deposits"
    WITHDRAWALS = "withdrawals"
    PURCHASES = "purchases"
    SALES = "sales"
    BROKER_COMMISSIONS = "broker_commissions"
    SERVICE_FEES = "service_fees"
    MARGIN_FEES = "margin_fees"
    OTHER_FEES = "other_fees"
    TAXES = "taxes"
    COUPONS = "coupons"
    DIVIDENDS = "dividends"
    BOND_REDEMPTIONS = "bond_redemptions"
    OTHER = "other"


class CheckStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    APPLIED = "applied"


class ReconciliationStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"


class ExpectedPaymentSign(StrEnum):
    NONNEGATIVE = "nonnegative"
    NONPOSITIVE = "nonpositive"


class OperationsPeriodV1(ContractModel):
    started_at: datetime
    ended_at: datetime
    days: PositiveInt

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("operation period timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_period(self) -> OperationsPeriodV1:
        if self.started_at > self.ended_at:
            raise ValueError("operation period start cannot follow end")
        return self


class OperationsPaginationV1(ContractModel):
    pages_fetched: NonNegativeInt
    page_limit: PositiveInt
    max_pages: PositiveInt
    items_received: NonNegativeInt
    has_next: bool
    truncated: bool
    cursor_loop_detected: bool
    server_period_filter_applied: bool

    @model_validator(mode="after")
    def validate_pagination(self) -> OperationsPaginationV1:
        if self.pages_fetched > self.max_pages:
            raise ValueError("pages_fetched cannot exceed max_pages")
        expected_truncated = self.has_next or self.cursor_loop_detected
        if self.truncated != expected_truncated:
            raise ValueError("truncated must match unfinished pagination state")
        return self


class CashFlowBucketV1(ContractModel):
    count: NonNegativeInt
    gross_amount: NonNegativeDecimal
    net_payment: FiniteDecimal
    inflow: NonNegativeDecimal
    outflow: NonNegativeDecimal

    @model_validator(mode="after")
    def validate_arithmetic(self) -> CashFlowBucketV1:
        if self.gross_amount != self.inflow + self.outflow:
            raise ValueError("gross_amount must equal inflow plus outflow")
        if self.net_payment != self.inflow - self.outflow:
            raise ValueError("net_payment must equal inflow minus outflow")
        if self.count == 0 and any(
            value != 0
            for value in (
                self.gross_amount,
                self.net_payment,
                self.inflow,
                self.outflow,
            )
        ):
            raise ValueError("zero-count cash-flow buckets must contain zero amounts")
        return self


class CategoryCashFlowV1(ContractModel):
    category: OperationCategory
    bucket: CashFlowBucketV1


class CurrencyCashFlowV1(ContractModel):
    currency: CurrencyCode
    categories: tuple[CategoryCashFlowV1, ...]

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_categories(self) -> CurrencyCashFlowV1:
        categories = [row.category for row in self.categories]
        if len(categories) != len(set(categories)):
            raise ValueError("cash-flow categories must be unique per currency")
        if set(categories) != set(OperationCategory):
            raise ValueError("cash-flow summary must contain every operation category")
        return self


class NetExternalFlowV1(ContractModel):
    currency: CurrencyCode
    deposits: NonNegativeDecimal
    withdrawals: NonNegativeDecimal
    net_external_flow: FiniteDecimal

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_arithmetic(self) -> NetExternalFlowV1:
        if self.net_external_flow != self.deposits - self.withdrawals:
            raise ValueError("net_external_flow must equal deposits minus withdrawals")
        return self


class TurnoverV1(ContractModel):
    currency: CurrencyCode
    purchases: NonNegativeDecimal
    sales: NonNegativeDecimal
    turnover: NonNegativeDecimal

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_arithmetic(self) -> TurnoverV1:
        if self.turnover != self.purchases + self.sales:
            raise ValueError("turnover must equal purchases plus sales")
        return self


class InstrumentActivityV1(ContractModel):
    currency: CurrencyCode
    operation_count: NonNegativeInt
    purchases: NonNegativeDecimal
    sales: NonNegativeDecimal
    coupons: NonNegativeDecimal
    dividends: NonNegativeDecimal
    bond_redemptions: NonNegativeDecimal
    net_payment: FiniteDecimal
    instrument_uid: Annotated[str | None, Field(max_length=128)] = None
    position_uid: Annotated[str | None, Field(max_length=128)] = None
    figi: Annotated[str | None, Field(max_length=32)] = None
    name: Annotated[str | None, Field(max_length=256)] = None
    instrument_type: Annotated[str | None, Field(max_length=64)] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_activity(self) -> InstrumentActivityV1:
        if not any((self.instrument_uid, self.position_uid, self.figi, self.name)):
            raise ValueError("instrument activity requires identity or a source name")
        expected_net = (
            self.sales
            + self.coupons
            + self.dividends
            + self.bond_redemptions
            - self.purchases
        )
        if self.net_payment != expected_net:
            raise ValueError("instrument activity net_payment does not reconcile")
        return self


class OperationStateCountV1(ContractModel):
    state: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,127}$")]
    count: NonNegativeInt


class OperationCategoryCountV1(ContractModel):
    category: OperationCategory
    count: NonNegativeInt


class PaymentSignExampleV1(ContractModel):
    operation_type: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,127}$")]
    category: OperationCategory
    currency: CurrencyCode
    payment: FiniteDecimal
    expected_sign: ExpectedPaymentSign

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


class PaymentSignCheckV1(ContractModel):
    status: CheckStatus
    checked: NonNegativeInt
    mismatches: NonNegativeInt
    examples: tuple[PaymentSignExampleV1, ...] = ()

    @model_validator(mode="after")
    def validate_check(self) -> PaymentSignCheckV1:
        if self.mismatches > self.checked:
            raise ValueError("payment sign mismatches cannot exceed checked rows")
        if len(self.examples) > self.mismatches:
            raise ValueError("payment sign examples cannot exceed mismatch count")
        if self.status == CheckStatus.PASSED and self.mismatches != 0:
            raise ValueError("passed payment sign check cannot contain mismatches")
        if self.status == CheckStatus.WARNING and self.mismatches == 0:
            raise ValueError("warning payment sign check requires a mismatch")
        if self.status not in (CheckStatus.PASSED, CheckStatus.WARNING):
            raise ValueError("payment sign status must be passed or warning")
        return self


class CategoryTotalCheckV1(ContractModel):
    currency: CurrencyCode
    operations_net_payment: FiniteDecimal
    categories_net_payment: FiniteDecimal
    difference: FiniteDecimal
    status: CheckStatus

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_check(self) -> CategoryTotalCheckV1:
        expected = self.categories_net_payment - self.operations_net_payment
        if self.difference != expected:
            raise ValueError("category total difference does not reconcile")
        expected_status = CheckStatus.PASSED if self.difference == 0 else CheckStatus.FAILED
        if self.status != expected_status:
            raise ValueError("category total status does not match difference")
        return self


class CategoryTotalsCheckV1(ContractModel):
    status: CheckStatus
    checks: tuple[CategoryTotalCheckV1, ...]

    @model_validator(mode="after")
    def validate_check(self) -> CategoryTotalsCheckV1:
        currencies = [row.currency for row in self.checks]
        if len(currencies) != len(set(currencies)):
            raise ValueError("category total checks require unique currencies")
        all_passed = all(row.status == CheckStatus.PASSED for row in self.checks)
        expected = CheckStatus.PASSED if all_passed else CheckStatus.WARNING
        if self.status != expected:
            raise ValueError("category totals status does not match row checks")
        return self


class CommissionDoubleCountProtectionV1(ContractModel):
    status: CheckStatus
    canonical_cash_basis: Annotated[str, Field(min_length=1, max_length=128)]
    nested_commission_fields_excluded: NonNegativeInt
    parent_type_updates_collapsed: NonNegativeInt
    passed: bool

    @model_validator(mode="after")
    def validate_protection(self) -> CommissionDoubleCountProtectionV1:
        if self.status != CheckStatus.APPLIED or not self.passed:
            raise ValueError("commission double-count protection must be applied")
        return self


class ParentChildDoubleCountProtectionV1(ContractModel):
    status: CheckStatus
    top_level_operations_only: bool
    embedded_child_operations_excluded: NonNegativeInt
    embedded_trades_excluded: NonNegativeInt
    top_level_parent_linked_operations: NonNegativeInt
    passed: bool

    @model_validator(mode="after")
    def validate_protection(self) -> ParentChildDoubleCountProtectionV1:
        if (
            self.status != CheckStatus.APPLIED
            or not self.top_level_operations_only
            or not self.passed
        ):
            raise ValueError("parent-child double-count protection must be applied")
        return self


class OperationsReconciliationV1(ContractModel):
    executed_only: bool
    payment_sign_check: PaymentSignCheckV1
    category_totals_check: CategoryTotalsCheckV1
    commission_double_count_protection: CommissionDoubleCountProtectionV1
    parent_child_double_count_protection: ParentChildDoubleCountProtectionV1
    status: ReconciliationStatus

    @model_validator(mode="after")
    def validate_reconciliation(self) -> OperationsReconciliationV1:
        passed = (
            self.executed_only
            and self.payment_sign_check.status == CheckStatus.PASSED
            and self.category_totals_check.status == CheckStatus.PASSED
            and self.commission_double_count_protection.passed
            and self.parent_child_double_count_protection.passed
        )
        expected = ReconciliationStatus.OK if passed else ReconciliationStatus.WARNING
        if self.status != expected:
            raise ValueError("operations reconciliation status is inconsistent")
        return self


class OperationsSourceQualityV1(ContractModel):
    raw_items_received: NonNegativeInt
    items_outside_period: NonNegativeInt
    invalid_date_rows: NonNegativeInt
    exact_duplicates_removed: NonNegativeInt
    commission_updates_collapsed: NonNegativeInt
    currencies_detected: NonNegativeInt
    unknown_operation_types: NonNegativeInt
    invalid_money_rows: NonNegativeInt
    pagination_complete: bool
    reconciliation_confirmed: bool
    instrument_groups_total: NonNegativeInt
    instrument_groups_returned: NonNegativeInt
    instrument_groups_skipped_by_limit: NonNegativeInt
    complete: bool
    no_cross_currency_aggregation: bool
    read_only: bool

    @model_validator(mode="after")
    def validate_quality(self) -> OperationsSourceQualityV1:
        if not self.no_cross_currency_aggregation:
            raise ValueError("cross-currency aggregation is forbidden")
        if not self.read_only:
            raise ValueError("operations analytics source must be read-only")
        if self.instrument_groups_returned + self.instrument_groups_skipped_by_limit != self.instrument_groups_total:
            raise ValueError("instrument group counts do not reconcile")
        expected_complete = (
            self.pagination_complete
            and self.reconciliation_confirmed
            and self.invalid_date_rows == 0
            and self.invalid_money_rows == 0
        )
        if self.complete != expected_complete:
            raise ValueError("source quality completeness is inconsistent")
        return self


class OperationsAnalyticsV1(ContractModel):
    metadata: ContractMetadata
    period: OperationsPeriodV1
    pagination: OperationsPaginationV1
    operations_count: NonNegativeInt
    duplicates_removed: NonNegativeInt
    executed_operations: NonNegativeInt
    canceled_operations: NonNegativeInt
    operations_in_progress: NonNegativeInt
    state_counts: tuple[OperationStateCountV1, ...]
    category_counts: tuple[OperationCategoryCountV1, ...]
    cash_flows_by_currency: tuple[CurrencyCashFlowV1, ...]
    net_external_flow: tuple[NetExternalFlowV1, ...]
    turnover: tuple[TurnoverV1, ...]
    instrument_activity: tuple[InstrumentActivityV1, ...]
    reconciliation: OperationsReconciliationV1
    source_quality: OperationsSourceQualityV1

    @model_validator(mode="after")
    def validate_analytics(self) -> OperationsAnalyticsV1:
        if self.metadata.schema_name != "operations_analytics":
            raise ValueError("schema_name must be operations_analytics")

        states = [row.state for row in self.state_counts]
        if len(states) != len(set(states)):
            raise ValueError("state_counts must contain unique states")
        if sum(row.count for row in self.state_counts) != self.operations_count:
            raise ValueError("state_counts must reconcile with operations_count")

        categories = [row.category for row in self.category_counts]
        if len(categories) != len(set(categories)):
            raise ValueError("category_counts must contain unique categories")
        if set(categories) != set(OperationCategory):
            raise ValueError("category_counts must contain every operation category")
        if sum(row.count for row in self.category_counts) != self.operations_count:
            raise ValueError("category_counts must reconcile with operations_count")

        if (
            self.executed_operations
            + self.canceled_operations
            + self.operations_in_progress
            > self.operations_count
        ):
            raise ValueError("operation state subtotals cannot exceed operations_count")
        if self.duplicates_removed > self.source_quality.raw_items_received:
            raise ValueError("duplicates_removed cannot exceed raw_items_received")

        cash_currencies = [row.currency for row in self.cash_flows_by_currency]
        external_currencies = [row.currency for row in self.net_external_flow]
        turnover_currencies = [row.currency for row in self.turnover]
        for currencies in (
            cash_currencies,
            external_currencies,
            turnover_currencies,
        ):
            if len(currencies) != len(set(currencies)):
                raise ValueError("currency summary rows must be unique")
        if set(cash_currencies) != set(external_currencies) or set(
            cash_currencies
        ) != set(turnover_currencies):
            raise ValueError("currency summary sections must cover the same currencies")
        if self.source_quality.currencies_detected != len(cash_currencies):
            raise ValueError("currencies_detected does not match currency summaries")
        if any(
            row.currency not in set(cash_currencies)
            for row in self.instrument_activity
        ):
            raise ValueError("instrument activity currency is absent from cash summaries")
        return self
