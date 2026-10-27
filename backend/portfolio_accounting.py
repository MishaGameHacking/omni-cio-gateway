"""Evidence-gated cash reconciliation and exact-flow portfolio return arithmetic.

Pure functions: no broker connection, database, model, price estimation or order.
These functions validate supplied evidence; they do not attest its provenance.
The caller must obtain complete independently reconciled observations first.
Coupon/dividend receipts and principal repayments are INTERNAL portfolio flows;
only owner deposits/withdrawals belong in external-flow TWR/XIRR inputs.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Context, Decimal, InvalidOperation, localcontext
from functools import wraps
import re

ZERO = Decimal(0)
ONE = Decimal(1)
MAX_ROWS = 4096


class AccountingError(ValueError):
    """Invalid inputs, distinct from valid but insufficient evidence."""


def isolated_arithmetic(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext(Context(prec=50)):
            return function(*args, **kwargs)
    return wrapped


def _amount(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise AccountingError("accounting_exact_amount_required")
    if len(str(value)) > 80:
        raise AccountingError("accounting_amount_too_large")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        raise AccountingError("accounting_amount_invalid") from None
    if (not amount.is_finite() or amount.copy_abs() > Decimal("1e24")
            or not -9 <= amount.as_tuple().exponent <= 24):
        raise AccountingError("accounting_amount_out_of_bounds")
    return amount


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise AccountingError("accounting_aware_time_required")
    return value.astimezone(timezone.utc)


def _identifier(value: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 200
            or value.strip() != value or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise AccountingError("accounting_identity_invalid")
    return value


def _currency(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Z]{3}", value) is None:
        raise AccountingError("accounting_currency_invalid")
    return value


def _rows(values, kind):
    if not isinstance(values, (tuple, list)) or len(values) > MAX_ROWS:
        raise AccountingError("accounting_rows_unbounded")
    if any(not isinstance(row, kind) for row in values):
        raise AccountingError("accounting_row_type_invalid")


def _text(value: Decimal) -> str:
    return format(value, "f")


@dataclass(frozen=True)
class Scope:
    owner: str
    broker_connection: str
    account: str

    def validate(self):
        for value in (self.owner, self.broker_connection, self.account):
            _identifier(value)


@dataclass(frozen=True)
class CashBalance:
    scope: Scope
    at: datetime
    currency: str
    amount: str
    evidence_id: str
    # Buying power/available-to-trade cannot be compared with settled cash.
    basis: str = "settled_cash"
    independent_of_operation_ledger: bool = False


@dataclass(frozen=True)
class CashMovement:
    scope: Scope
    identifier: str
    settled_at: datetime
    currency: str
    amount: str
    evidence_id: str
    state: str = "settled"


@dataclass(frozen=True)
class ObservedWindow:
    scope: Scope
    start: datetime
    end: datetime
    evidence_id: str
    complete: bool


@isolated_arithmetic
def reconcile_cash(opening: CashBalance, closing: CashBalance,
                   movements: list[CashMovement], windows: list[ObservedWindow], *,
                   tolerance: str = "0.01") -> dict:
    """Reconcile (opening.at, closing.at], separately for ONE currency/account.

    No annotation fees/taxes are added to payments a second time. This is not
    a tax-liability estimate, available-to-trade calculation or performance test.
    Input windows assert complete SETTLEMENT coverage, not merely order dates.
    """
    if not isinstance(opening, CashBalance) or not isinstance(closing, CashBalance):
        raise AccountingError("accounting_balance_type_invalid")
    if not isinstance(opening.scope, Scope) or opening.scope != closing.scope:
        raise AccountingError("accounting_scope_mismatch")
    opening.scope.validate()
    begin, end = _time(opening.at), _time(closing.at)
    if not begin < end or end - begin > timedelta(days=36600):
        raise AccountingError("accounting_interval_invalid")
    currency = _currency(opening.currency)
    if closing.currency != currency:
        raise AccountingError("accounting_currency_mismatch")
    first, last, epsilon = _amount(opening.amount), _amount(closing.amount), _amount(tolerance)
    if not ZERO <= epsilon <= Decimal("0.01"):
        raise AccountingError("accounting_tolerance_invalid")
    _rows(movements, CashMovement)
    _rows(windows, ObservedWindow)
    evidence = {_identifier(opening.evidence_id), _identifier(closing.evidence_id)}
    issues = set()
    if (opening.independent_of_operation_ledger is not True
            or closing.independent_of_operation_ledger is not True):
        issues.add("independent_cash_balances_required")
    if opening.basis != "settled_cash" or closing.basis != "settled_cash":
        issues.add("settled_cash_basis_required")
    covered = []
    for window in windows:
        if window.scope != opening.scope:
            raise AccountingError("accounting_window_scope_mismatch")
        left, right = _time(window.start), _time(window.end)
        if not left < right:
            raise AccountingError("accounting_window_invalid")
        evidence.add(_identifier(window.evidence_id))
        if window.complete is True:
            covered.append((left, right))
    cursor = begin
    for left, right in sorted(covered):
        if left <= cursor < right:
            cursor = right
    if cursor < end:
        issues.add("settlement_coverage_incomplete")
    seen, included = {}, {}
    for movement in movements:
        if movement.scope != opening.scope:
            raise AccountingError("accounting_movement_scope_mismatch")
        _identifier(movement.identifier)
        evidence.add(_identifier(movement.evidence_id))
        at = _time(movement.settled_at)
        amount = _amount(movement.amount)
        if _currency(movement.currency) != currency:
            raise AccountingError("accounting_movement_currency_mismatch")
        if movement.state not in {"settled", "pending", "cancelled", "unknown"}:
            raise AccountingError("accounting_movement_state_invalid")
        fingerprint = (at, amount, currency, movement.state)
        if movement.identifier in seen and seen[movement.identifier] != fingerprint:
            issues.add("conflicting_movement_versions")
        seen[movement.identifier] = fingerprint
        if not begin < at <= end:
            continue
        if movement.state in {"pending", "unknown"}:
            issues.add("unresolved_cash_movements")
        elif movement.state == "settled":
            included[movement.identifier] = amount
    if issues:
        return {"state": "incomplete", "reconciled": False, "reasons": sorted(issues),
                "currency": currency, "expected_closing": None, "difference": None,
                "evidence_ids": sorted(evidence), "tax_liability_estimated": False}
    expected = first + sum(included.values(), ZERO)
    difference = last - expected
    matched = difference.copy_abs() <= epsilon
    return {"state": "matched" if matched else "mismatch", "reconciled": matched,
            "reasons": [] if matched else ["independent_cash_balance_difference"],
            "currency": currency, "opening": _text(first), "observed_closing": _text(last),
            "expected_closing": _text(expected), "difference": _text(difference),
            "settled_movements": len(included), "evidence_ids": sorted(evidence),
            "tax_liability_estimated": False}


@dataclass(frozen=True)
class FlowValuation:
    at: datetime
    before_flow: str
    after_flow: str
    net_external_flow: str
    evidence_id: str


@isolated_arithmetic
def time_weighted_return(points: list[FlowValuation], *, currency: str,
                         all_external_flows_observed: bool,
                         all_valuations_reconciled: bool) -> dict:
    """Exact TWR from NAV immediately before/after EVERY external cash flow.

    Ratios between adjacent marks are chain-linked. This is not a daily-flow
    approximation. Coupons retained in the portfolio are already in NAV.
    """
    _currency(currency)
    _rows(points, FlowValuation)
    if all_external_flows_observed is not True or all_valuations_reconciled is not True:
        return {"state": "unavailable", "reason": "complete_reconciled_flow_valuations_required", "return": None}
    if len(points) < 2:
        return {"state": "unavailable", "reason": "two_valuations_required", "return": None}
    factor, previous, evidence = ONE, None, set()
    for point in points:
        at = _time(point.at)
        before, after, flow = map(_amount, (point.before_flow, point.after_flow, point.net_external_flow))
        evidence.add(_identifier(point.evidence_id))
        if min(before, after) < ZERO or after != before + flow:
            raise AccountingError("accounting_flow_valuation_not_reconciled")
        if previous is not None:
            if at <= previous[0]:
                raise AccountingError("accounting_valuation_times_not_strictly_ordered")
            if previous[1] <= ZERO:
                return {"state": "unavailable", "reason": "zero_invested_capital_segment", "return": None}
            factor *= before / previous[1]
        previous = (at, after)
    return {"state": "computed_from_supplied_evidence", "method": "exact_flow_twr",
            "return": _text(factor - ONE), "currency": currency,
            "start": _time(points[0].at).isoformat(), "end": _time(points[-1].at).isoformat(),
            "segments": len(points)-1, "evidence_ids": sorted(evidence),
            "annualized": False, "tax_liability_estimated": False}


@dataclass(frozen=True)
class InvestorCashFlow:
    on: date
    amount: str
    evidence_id: str


@isolated_arithmetic
def money_weighted_return(flows: list[InvestorCashFlow], *, currency: str,
                          all_external_flows_observed: bool,
                          terminal_value_reconciled: bool) -> dict:
    """Actual/365 XIRR with an explicit uniqueness gate and bounded root search.

    Investor sign: deposits/opening NAV negative; withdrawals/terminal NAV
    positive. Internal coupons/trades/principal payments must NOT be included.
    Multiple sign changes can imply multiple roots: return an explicit unknown,
    never select whichever root a Newton initial guess happens to find.
    """
    _currency(currency)
    _rows(flows, InvestorCashFlow)
    if all_external_flows_observed is not True or terminal_value_reconciled is not True:
        return {"state": "unavailable", "reason": "complete_reconciled_investor_flows_required", "return": None}
    grouped, evidence = defaultdict(Decimal), set()
    for flow in flows:
        if type(flow.on) is not date:
            raise AccountingError("accounting_calendar_day_required")
        evidence.add(_identifier(flow.evidence_id))
        grouped[flow.on] += _amount(flow.amount)
    rows = sorted((day, value) for day, value in grouped.items() if value)
    if len(rows) < 2 or rows[0][0] == rows[-1][0]:
        return {"state": "unavailable", "reason": "distinct_nonzero_cashflow_dates_required", "return": None}
    span = (rows[-1][0]-rows[0][0]).days
    if not 1 <= span <= 36600:
        raise AccountingError("accounting_xirr_horizon_invalid")
    signs = [value > ZERO for _, value in rows]
    changes = sum(a != b for a,b in zip(signs, signs[1:]))
    if changes != 1 or signs[0] or not signs[-1]:
        return {"state": "unavailable", "reason": "xirr_unique_investment_root_not_established", "return": None}
    dated = [(Decimal((day-rows[0][0]).days)/Decimal(365), value) for day,value in rows]
    def npv(log_factor):
        return sum((value*(-years*log_factor).exp() for years,value in dated), ZERO)
    left, right = Decimal("0.000000001").ln(), Decimal("10000001").ln()
    low, high = npv(left), npv(right)
    if low == ZERO:
        root = left
    elif high == ZERO:
        root = right
    elif low < ZERO or high > ZERO:
        return {"state": "unavailable", "reason": "xirr_root_outside_supported_bounds", "return": None}
    else:
        root = (left+right)/2
        for _ in range(200):
            root = (left+right)/2
            value = npv(root)
            if value > ZERO:
                left = root
            else:
                right = root
            if right-left <= Decimal("1e-35"):
                break
    return {"state": "computed_from_supplied_evidence", "method": "actual_365_xirr",
            "return": _text(root.exp()-ONE), "npv_residual": _text(npv(root)),
            "currency": currency, "start": rows[0][0].isoformat(), "end": rows[-1][0].isoformat(),
            "annualized": True, "evidence_ids": sorted(evidence), "tax_liability_estimated": False}
