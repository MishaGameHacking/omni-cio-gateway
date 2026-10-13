"""Offline, deterministic checks for a proposed long-only portfolio.

No quotes, ratings, forecasts, orders or probabilities are invented here.
The caller must supply validated same-currency valuations and aligned scenarios.
This module is not connected to production recommendations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Mapping, Sequence
from urllib.parse import urlsplit
import re

ZERO = Decimal(0)
ONE = Decimal(1)


class RiskInputError(ValueError):
    """Missing, stale or incompatible data; no numerical recommendation allowed."""


def number(value: Decimal | int | str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise RiskInputError('use_decimal_not_binary_float')
    try:
        result = Decimal(value)
    except (ValueError, TypeError, ArithmeticError):
        raise RiskInputError('invalid_number') from None
    if not result.is_finite():
        raise RiskInputError('nonfinite_number')
    return result


def aware(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RiskInputError('timezone_required')


def fraction(value: Decimal | int | str) -> Decimal:
    result = number(value)
    if not ZERO <= result <= ONE:
        raise RiskInputError('fraction_out_of_range')
    return result


@dataclass(frozen=True)
class Rating:
    agency: str
    scale: str
    grade: str
    subject_id: str
    source: str
    published_at: datetime
    valid_until: datetime
    outlook: str = 'unknown'
    withdrawn: bool = False

    def bucket(self, at: datetime) -> str:
        aware(at)
        aware(self.published_at)
        aware(self.valid_until)
        if (not all((self.agency, self.scale, self.grade, self.subject_id, self.source))
                or not self.published_at <= at < self.valid_until or self.withdrawn):
            return 'UNVERIFIED'
        # National scales and agencies deliberately are not merged or averaged.
        return f'{self.agency}|{self.scale}|{self.grade}'


@dataclass(frozen=True)
class Exposure:
    instrument_id: str
    issuer_group: str
    sector: str
    asset_class: str
    quote_currency: str
    value_base: Decimal
    valuation_currency: str
    valuation_at: datetime
    source: str
    is_cash: bool = False
    rating: Rating | None = None
    requires_rating: bool = False


@dataclass(frozen=True)
class TailRisk:
    var_loss: Decimal
    expected_shortfall: Decimal
    alpha: Decimal
    observations: int
    horizon_days: int
    source: str
    as_of: datetime
    warning: str = 'История и сценарии не гарантируют будущий результат.'


def empirical_tail_risk(
    losses: Sequence[Decimal], *, alpha: Decimal, horizon_days: int,
    source: str, as_of: datetime, now: datetime,
    max_age: timedelta, min_tail_observations: int = 5,
) -> TailRisk:
    """Equal-probability empirical VaR and ES, fractional mass at the tail boundary.

    Positive loss = loss; negative loss = gain. ES is not a maximum possible loss,
    and alpha is not the probability of avoiding bankruptcy.
    """
    confidence = fraction(alpha)
    aware(as_of)
    aware(now)
    if not ZERO < confidence < ONE:
        raise RiskInputError('alpha_must_be_inside_unit_interval')
    if type(horizon_days) is not int or horizon_days < 1 or not source:
        raise RiskInputError('scenario_metadata_required')
    if max_age.total_seconds() <= 0 or not now - max_age <= as_of <= now:
        raise RiskInputError('scenario_data_stale_or_future')
    if type(min_tail_observations) is not int or min_tail_observations < 1:
        raise RiskInputError('invalid_minimum_tail')
    data = sorted(number(v) for v in losses)
    tail_mass = Decimal(len(data)) * (ONE - confidence)
    if tail_mass < min_tail_observations:
        raise RiskInputError('insufficient_tail_observations')
    index = int((confidence * len(data)).to_integral_value(rounding=ROUND_CEILING)) - 1
    remaining = tail_mass
    total = ZERO
    for loss in reversed(data):
        weight = min(ONE, remaining)
        total += weight * loss
        remaining -= weight
        if remaining <= ZERO:
            break
    return TailRisk(data[index], total / tail_mass, confidence, len(data),
                    horizon_days, source, as_of)


def scenario_losses(weights: Mapping[str, Decimal],
                    scenarios: Sequence[Mapping[str, Decimal]]) -> tuple[Decimal, ...]:
    """Use whole aligned vectors, preserving joint movements; no independent shuffle."""
    if not weights:
        raise RiskInputError('empty_portfolio')
    cleaned = {key: fraction(value) for key, value in weights.items()}
    if sum(cleaned.values(), ZERO) != ONE:
        raise RiskInputError('weights_must_sum_to_one_including_cash')
    results = []
    for scenario in scenarios:
        if set(scenario) != set(cleaned):
            raise RiskInputError('scenario_assets_do_not_match')
        returns = {key: number(value) for key, value in scenario.items()}
        if any(value < -ONE for value in returns.values()):
            raise RiskInputError('unsupported_return_below_minus_one')
        results.append(-sum((cleaned[key] * returns[key] for key in cleaned), ZERO))
    return tuple(results)


def expected_credit_loss(ead: Decimal, pd: Decimal, lgd: Decimal) -> Decimal:
    """EAD*PD*LGD only for an explicitly supplied common horizon/model.

    This function never translates a rating letter to a probability. Caller must
    validate calibration, horizon, dependence assumptions and source separately.
    """
    amount = number(ead)
    if amount < ZERO:
        raise RiskInputError('negative_exposure')
    return amount * fraction(pd) * fraction(lgd)


def assess_exposures(exposures: Sequence[Exposure], *, base_currency: str,
                     now: datetime, max_age: timedelta,
                     limits: Mapping[str, Decimal]) -> dict:
    """Aggregate positions across accounts. Limits are explicit, not default advice.

    Keys: issuer:<group>, sector:<sector>, class:<class>, currency:<currency>,
    rating:<agency>|<scale>|<grade>, rating:UNVERIFIED, cash:minimum.
    All proportions are fractions of total same-base marked value.
    """
    aware(now)
    if not isinstance(base_currency, str) or not re.fullmatch(r'[A-Z]{3}', base_currency):
        raise RiskInputError('invalid_base_currency')
    if not exposures or max_age.total_seconds() <= 0:
        raise RiskInputError('exposures_and_freshness_policy_required')
    caps = {key: fraction(value) for key, value in limits.items()}
    buckets: dict[str, Decimal] = {}
    total, cash = ZERO, ZERO
    unknown = []
    for item in exposures:
        aware(item.valuation_at)
        amount = number(item.value_base)
        if amount < ZERO:
            raise RiskInputError('shorts_or_negative_equity_need_separate_model')
        if item.valuation_currency != base_currency:
            raise RiskInputError('mixed_valuation_currencies')
        if not now - max_age <= item.valuation_at <= now:
            raise RiskInputError('valuation_stale_or_future')
        if not item.instrument_id or not item.source:
            raise RiskInputError('valuation_source_required')
        total += amount
        if item.is_cash:
            cash += amount
        groups = [f'class:{item.asset_class or "UNVERIFIED"}',
                  f'currency:{item.quote_currency or "UNVERIFIED"}']
        if not item.asset_class or not item.quote_currency:
            unknown.append(item.instrument_id)
        if not item.is_cash:
            groups += [f'issuer:{item.issuer_group or "UNVERIFIED"}',
                       f'sector:{item.sector or "UNVERIFIED"}']
            if not item.issuer_group or not item.sector:
                unknown.append(item.instrument_id)
        if item.requires_rating:
            rating = (item.rating.bucket(now) if item.rating and item.rating.subject_id in
                      {item.instrument_id, item.issuer_group} else 'UNVERIFIED')
            groups.append('rating:' + rating)
            if rating == 'UNVERIFIED':
                unknown.append(item.instrument_id)
        for key in groups:
            buckets[key] = buckets.get(key, ZERO) + amount
    if total <= ZERO:
        raise RiskInputError('positive_equity_required')
    shares = {key: amount / total for key, amount in buckets.items()}
    violations = []
    for key, cap in caps.items():
        if key == 'cash:minimum':
            actual, failed = cash / total, cash / total < cap
        else:
            actual = shares.get(key, ZERO)
            failed = actual > cap
        if failed:
            violations.append({'dimension': key, 'actual': actual, 'limit': cap})
    return {'total_base': total, 'currency': base_currency, 'shares': shares,
            'cash_share': cash / total, 'violations': violations,
            'unverified_instruments': sorted(set(unknown)),
            'status': 'needs_data' if unknown else ('outside_limits' if violations else 'within_supplied_limits'),
            'guarantee_of_safety': False}


def instrument_link(url: str) -> str:
    """Validate a canonical instrument URL supplied by a trusted instrument catalog.

    Does not invent private deeplink schemes or place/pre-fill an order. Android
    must detect whether an installed app actually handles the HTTPS URL.
    """
    if len(url) > 512:
        raise RiskInputError('invalid_instrument_url')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.tbank.ru'
            or parsed.query or parsed.fragment
            or not re.fullmatch(r'/invest/(stocks|bonds|etfs|currencies)/[A-Za-z0-9@_.-]{1,80}/', parsed.path)
            or any(part in {'.', '..'} for part in parsed.path.split('/'))):
        raise RiskInputError('invalid_instrument_url')
    return url
