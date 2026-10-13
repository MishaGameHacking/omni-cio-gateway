"""Deterministic, source-required portfolio research; no orders and no LLMs.

Inputs must be produced by reviewed market-data adapters. This is NOT a live
news/rating collector and a scenario frequency is NOT a bankruptcy guarantee.
All returns are joint, aligned, same-horizon simple total returns in one base
currency. No IID-default assumption or cross-agency rating conversion is made.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
import math
import random
import re
from typing import Mapping, Sequence


class ResearchDataError(ValueError):
    pass


def number(value: object) -> float:
    if isinstance(value, bool):
        raise ResearchDataError('boolean_is_not_a_number')
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ResearchDataError('invalid_number') from None
    if not math.isfinite(result):
        raise ResearchDataError('nonfinite_number')
    return result


def money(value: object) -> Decimal:
    result = Decimal(str(number(value)))
    # For production money prefer string/Decimal inputs, never float aggregation.
    if isinstance(value, (str, Decimal, int)) and not isinstance(value, bool):
        result = Decimal(value)
    if not result.is_finite() or abs(result) > Decimal('1e18'):
        raise ResearchDataError('invalid_money')
    return result


@dataclass(frozen=True)
class Evidence:
    source_id: str
    as_of: datetime
    valid_until: datetime

    def check(self, now: datetime) -> None:
        if not self.source_id or len(self.source_id) > 200:
            raise ResearchDataError('missing_source')
        if any(t.tzinfo is None or t.utcoffset() is None for t in (now, self.as_of, self.valid_until)):
            raise ResearchDataError('timestamp_timezone_missing')
        if not self.as_of <= now <= self.valid_until or self.valid_until <= self.as_of:
            raise ResearchDataError('stale_or_future_evidence')


@dataclass(frozen=True)
class CreditEstimate:
    agency: str
    scale: str
    grade: str
    horizon_days: int
    default_probability: float
    recovery_fraction: float
    calibration_id: str
    evidence: Evidence
    withdrawn: bool = False

    def expected_loss(self, exposure: Decimal, horizon_days: int, now: datetime) -> Decimal:
        self.evidence.check(now)
        if self.withdrawn or not all((self.agency, self.scale, self.grade, self.calibration_id)):
            raise ResearchDataError('rating_or_calibration_unavailable')
        if type(self.horizon_days) is not int or self.horizon_days != horizon_days or horizon_days <= 0:
            raise ResearchDataError('credit_horizon_mismatch')
        probability, recovery = number(self.default_probability), number(self.recovery_fraction)
        if not 0 <= probability <= 1 or not 0 <= recovery <= 1 or exposure < 0:
            raise ResearchDataError('invalid_credit_estimate')
        return exposure * Decimal(str(probability)) * (1 - Decimal(str(recovery)))

    @property
    def bucket(self) -> str:
        # National AAA and global AAA, or two agencies, are never silently merged.
        return f'{self.agency}|{self.scale}|{self.grade}'


@dataclass(frozen=True)
class Asset:
    uid: str
    ticker: str
    isin: str | None
    name: str
    issuer: str
    sector: str
    asset_class: str
    currency: str
    price_per_unit: Decimal
    lot_size: int
    units: int
    blocked_units: int
    buy_available: bool
    sell_available: bool
    qualified_only: bool
    evidence: Evidence
    credit: CreditEstimate | None = None

    def check(self, base_currency: str, now: datetime) -> None:
        self.evidence.check(now)
        if not all((self.uid, self.ticker, self.name, self.issuer, self.sector)):
            raise ResearchDataError('instrument_metadata_missing')
        if self.currency != base_currency:
            raise ResearchDataError('base_currency_valuation_required')
        if self.asset_class not in {'share', 'bond'}:
            raise ResearchDataError('lookthrough_or_instrument_valuation_not_supported')
        if any(type(n) is not int for n in (self.lot_size, self.units, self.blocked_units)):
            raise ResearchDataError('nonintegral_lot_or_units')
        if self.lot_size <= 0 or self.units < 0 or not 0 <= self.blocked_units <= self.units or money(self.price_per_unit) <= 0:
            raise ResearchDataError('invalid_position')

    @property
    def value(self) -> Decimal:
        return money(self.price_per_unit) * self.units

    @property
    def rating_bucket(self) -> str:
        return self.credit.bucket if self.credit and not self.credit.withdrawn else 'UNRATED'


def official_instrument_url(asset_class: str, ticker: str) -> str | None:
    path = {'share': 'stocks', 'bond': 'bonds', 'etf': 'etfs'}.get(asset_class)
    if not path or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,39}', ticker) or '..' in ticker:
        return None
    return f'https://www.tbank.ru/invest/{path}/{ticker}/'


def exposure_groups(assets: Sequence[Asset], cash: Decimal, base_currency: str, now: datetime) -> dict:
    if money(cash) < 0 or len({a.uid for a in assets}) != len(assets):
        raise ResearchDataError('negative_cash_or_duplicate_asset')
    for asset in assets:
        asset.check(base_currency, now)
    cash = money(cash)
    total = cash + sum((a.value for a in assets), Decimal(0))
    if total <= 0:
        raise ResearchDataError('empty_capital')
    result = {}
    for dimension in ('issuer', 'sector', 'asset_class', 'currency', 'rating_bucket'):
        groups: dict[str, Decimal] = {}
        for asset in assets:
            key = getattr(asset, dimension)
            if dimension == 'rating_bucket' and asset.credit:
                try:
                    asset.credit.evidence.check(now)
                except ResearchDataError:
                    key = 'UNRATED'
            groups[key] = groups.get(key, Decimal(0)) + asset.value
        # Credit buckets below are total-portfolio proportions, not a claim that
        # equity has the same recovery or pricing risk as an issuer's bonds.
        result[dimension] = {key: value / total for key, value in groups.items() if value}
    return {'total': total, 'cash_fraction': cash / total, 'groups': result}


def expected_shortfall(losses: Sequence[float], confidence: float = 0.95) -> dict:
    values = sorted((number(x) for x in losses), reverse=True)
    confidence = number(confidence)
    if not values or not 0 < confidence < 1:
        raise ResearchDataError('invalid_tail_sample')
    exact_mass = len(values) * (Decimal(1) - Decimal(str(confidence)))
    mass = float(exact_mass)
    whole = int(exact_mass.to_integral_value(rounding=ROUND_FLOOR))
    fraction = float(exact_mass - whole)
    tail = math.fsum(values[:whole]) + (values[whole] * fraction if fraction > 0 else 0.0)
    quantile_index = len(values) - int((len(values) * Decimal(str(confidence))).to_integral_value(rounding=ROUND_CEILING))
    quantile = values[quantile_index]
    return {'var': quantile, 'expected_shortfall': tail / mass, 'confidence': confidence,
            'sample_count': len(values), 'tail_observations': mass,
            'warning': 'Мало наблюдений для оценки редких потерь.' if mass < 20 else None}


def portfolio_scenarios(weights: Sequence[float], rows: Sequence[Sequence[float]]) -> list[float]:
    w = [number(x) for x in weights]
    if not w or any(x < 0 for x in w) or math.fsum(w) > 1 + 1e-12 or not rows:
        raise ResearchDataError('invalid_long_only_weights')
    returns = []
    for row in rows:
        if len(row) != len(w):
            raise ResearchDataError('unaligned_scenario')
        r = [number(x) for x in row]
        if any(x < -1 for x in r):
            raise ResearchDataError('invalid_simple_return')
        returns.append(math.fsum(x * y for x, y in zip(w, r)))
    return returns


def wilson_interval(events: int, trials: int) -> tuple[float, float]:
    if type(events) is not int or type(trials) is not int or not 0 <= events <= trials or trials <= 0:
        raise ResearchDataError('invalid_event_count')
    z = 1.959963984540054
    p = events / trials
    denominator = 1 + z*z/trials
    center = (p + z*z/(2*trials)) / denominator
    radius = z * math.sqrt(p*(1-p)/trials + z*z/(4*trials*trials)) / denominator
    return (0. if events == 0 else max(0., center-radius),
            1. if events == trials else min(1., center+radius))


def bootstrap_capital_floor(weights: Sequence[float], rows: Sequence[Sequence[float]], *,
                            floor_fraction: float, horizon_steps: int, block_size: int,
                            paths: int, seed: int, evidence: Evidence, now: datetime) -> dict:
    """Joint moving-block bootstrap; buy-and-hold weights drift, no free rebalance.

    The interval describes simulation sampling error conditional on the dataset
    and model, NOT uncertainty about every possible future or true bankruptcy PD.
    """
    evidence.check(now)
    portfolio_scenarios(weights, rows)
    weights = [number(x) for x in weights]
    rows = [[number(x) for x in row] for row in rows]
    if not 0 <= number(floor_fraction) < 1 or not 2 <= len(rows):
        raise ResearchDataError('invalid_capital_floor')
    if any(type(x) is not int for x in (paths, horizon_steps, block_size, seed)):
        raise ResearchDataError('invalid_simulation_counts')
    if not 1 <= block_size <= len(rows) or not 1 <= horizon_steps <= 756 or not 100 <= paths <= 10_000:
        raise ResearchDataError('simulation_limits_exceeded')
    if paths * horizon_steps * len(weights) > 5_000_000:
        raise ResearchDataError('simulation_cpu_budget_exceeded')
    rng = random.Random(seed)  # Reproducible research simulation, not security randomness.
    breaches = 0
    cash = max(0., 1 - math.fsum(weights))
    for _ in range(paths):
        values = list(weights)
        remaining = horizon_steps
        breached = False
        while remaining > 0 and not breached:
            start = rng.randrange(len(rows) - block_size + 1)
            for row in rows[start:start + min(block_size, remaining)]:
                values = [v * (1 + number(r)) for v, r in zip(values, row)]
                remaining -= 1
                capital = number(cash + math.fsum(values))
                if capital <= floor_fraction:
                    breaches += 1
                    breached = True
                    break
    low, high = wilson_interval(breaches, paths)
    return {'scenario_breach_frequency': breaches / paths, 'sampling_interval_95': [low, high],
            'paths': paths, 'horizon_steps': horizon_steps, 'block_size': block_size,
            'seed': seed, 'source_id': evidence.source_id, 'guaranteed_safety': False,
            'explanation': 'Это доля смоделированных сценариев, где капитал опустился ниже выбранного порога. Будущее может оказаться хуже; ноль таких сценариев не означает нулевой риск.'}


def statement_metrics(*, debt, cash, ebitda, ebit, interest, operating_cashflow,
                      net_income, financial_sector: bool, evidence: Evidence, now: datetime) -> dict:
    evidence.check(now)
    data = [None if v is None else money(v) for v in (debt, cash, ebitda, ebit, interest, operating_cashflow, net_income)]
    d, c, e, operating, i, ocf, income = data
    warnings = []
    if financial_sector:
        return {'net_debt_to_ebitda': None, 'interest_coverage': None, 'cashflow_to_profit': None,
                'warnings': ['Для банков и других финансовых компаний нужна отдельная модель нормативов капитала и ликвидности.'],
                'source_id': evidence.source_id}
    leverage = (d-c)/e if d is not None and c is not None and e is not None and e > 0 else None
    coverage = operating/i if operating is not None and i is not None and i > 0 else None
    conversion = ocf/income if ocf is not None and income is not None and income > 0 else None
    if e is not None and e <= 0: warnings.append('Операционная прибыль до части расходов неположительная: обычная оценка долговой нагрузки здесь неприменима.')
    if ocf is not None and ocf < 0: warnings.append('Основная деятельность расходует деньги. Нужно проверить причины и запас средств.')
    if any(v is None for v in data): warnings.append('В отчётности не хватает показателей. Пропуски не заменены нулями.')
    return {'net_debt_to_ebitda': leverage, 'interest_coverage': coverage, 'cashflow_to_profit': conversion,
            'warnings': warnings, 'source_id': evidence.source_id}


def reduction_plan(assets: Sequence[Asset], cash: Decimal, *, base_currency: str,
                   issuer_cap: Decimal, minimum_trade_value: Decimal, fee_rate: Decimal,
                   now: datetime) -> dict:
    """Conservative lot-aware issuer-risk reductions, not a global optimizer.

    All company securities aggregate. No shorts, locked-unit sales, spending of
    unsettled proceeds, automatic orders, or artificial buys to fill a quota.
    Unknown tax liabilities mean the user must check broker figures before sale.
    """
    issuer_cap, fee_rate = money(issuer_cap), money(fee_rate)
    if not 0 < issuer_cap < 1 or not 0 <= fee_rate < 1 or money(minimum_trade_value) < 0:
        raise ResearchDataError('invalid_rebalance_limits')
    exposures = exposure_groups(assets, money(cash), base_currency, now)
    total = exposures['total']
    actions, warnings = [], []
    for issuer, share in exposures['groups']['issuer'].items():
        if share <= issuer_cap:
            continue
        remaining = total * (share - issuer_cap)
        for asset in sorted((a for a in assets if a.issuer == issuer), key=lambda a: a.uid):
            if not asset.sell_available:
                continue
            price = money(asset.price_per_unit)
            available_lots = (asset.units - asset.blocked_units) // asset.lot_size
            needed = int((remaining / (price * asset.lot_size * (1 - issuer_cap * fee_rate))).to_integral_value(rounding=ROUND_FLOOR))
            lots = min(available_lots, max(0, needed))
            gross = price * lots * asset.lot_size
            if lots == 0 or gross < minimum_trade_value:
                continue
            fees = gross * fee_rate
            remaining -= gross * (1 - issuer_cap * fee_rate)
            actions.append({'action': 'consider_reducing', 'instrument_uid': asset.uid,
                            'ticker': asset.ticker, 'isin': asset.isin, 'name': asset.name,
                            'lots': lots, 'units': lots * asset.lot_size, 'estimated_gross': str(gross),
                            'estimated_fee': str(fees), 'currency': base_currency,
                            'url': official_instrument_url(asset.asset_class, asset.ticker),
                            'source_ids': [asset.evidence.source_id],
                            'explanation': f'На компанию {issuer} приходится {share*100:.1f}% портфеля при вашем ограничении {issuer_cap*100:.1f}%. Можно рассмотреть уменьшение позиции на {lots} лот(а). Это снизит зависимость от одной компании, но продажа может зафиксировать убыток и вызвать налог.',
                            'requires_user_confirmation_in_broker': True})
        if remaining > 0:
            warnings.append(f'Лимит компании {issuer} не достигнут полностью: шаг лота, блокировка или доступность продажи мешают точному выравниванию.')
    return {'actions': actions, 'warnings': warnings, 'automatic_trading': False,
            'buy_selection_ready': False, 'note': 'Подбор покупок требует проверенных цен, отчётности, рейтингов, сценариев и ограничений пользователя; этот модуль не подставляет отсутствующие данные.'}


@dataclass(frozen=True)
class BuyLimits:
    min_cash_fraction: Decimal
    max_issuer_fraction: Decimal
    max_sector_fraction: Decimal
    max_rating_fraction: Mapping[str, Decimal]
    max_class_fraction: Mapping[str, Decimal]
    max_default_probability: float
    max_trade_fraction: Decimal
    max_daily_liquidity_fraction: Decimal
    horizon_days: int

    def check(self) -> None:
        bounds = (self.min_cash_fraction, self.max_issuer_fraction, self.max_sector_fraction,
                  self.max_trade_fraction, self.max_daily_liquidity_fraction,
                  *self.max_rating_fraction.values(), *self.max_class_fraction.values())
        if any(not 0 <= money(x) <= 1 for x in bounds) or not 0 <= number(self.max_default_probability) <= 1:
            raise ResearchDataError('invalid_buy_limits')
        if type(self.horizon_days) is not int or self.horizon_days <= 0:
            raise ResearchDataError('invalid_horizon')


def preview_one_lot_buy(candidate: Asset, positions: Sequence[Asset], cash: Decimal, *,
                        base_currency: str, limits: BuyLimits, fee_rate: Decimal,
                        daily_traded_value: Decimal, liquidity_evidence: Evidence,
                        fundamentals_evidence: Evidence, now: datetime) -> dict:
    """Bounded candidate eligibility, not an assertion that a security is 'best'.

    Rating/calibration, issuer metadata, fundamentals and liquidity must have
    been reviewed upstream. This API will not scrape or invent those inputs.
    Existing positions must be consolidated, including all accounts.
    """
    limits.check()
    candidate.check(base_currency, now)
    liquidity_evidence.check(now)
    fundamentals_evidence.check(now)
    fee_rate, daily = money(fee_rate), money(daily_traded_value)
    if not 0 <= fee_rate < 1 or daily <= 0:
        raise ResearchDataError('invalid_fee_or_liquidity')
    exposure = exposure_groups(positions, money(cash), base_currency, now)
    if any(p.uid == candidate.uid for p in positions):
        raise ResearchDataError('increment_existing_position_requires_separate_plan')
    reasons = []
    if not candidate.buy_available or candidate.qualified_only or candidate.blocked_units:
        reasons.append('Покупка недоступна либо требует дополнительных прав.')
    if candidate.units:
        raise ResearchDataError('new_candidate_must_have_zero_units')
    if candidate.credit is None:
        reasons.append('Нет проверенного кредитного рейтинга и оценки риска на ваш срок.')
    else:
        candidate.credit.expected_loss(Decimal(1), limits.horizon_days, now)
        if candidate.credit.default_probability > limits.max_default_probability:
            reasons.append('Кредитный риск выше заданного вами ограничения.')
    cash = money(cash)
    gross = money(candidate.price_per_unit) * candidate.lot_size
    fee = gross * fee_rate
    total_after = exposure['total'] - fee
    cash_after = cash - gross - fee
    if total_after <= 0 or cash_after < 0:
        reasons.append('На один лот с комиссией не хватает свободных денег.')
    else:
        if cash_after / total_after < limits.min_cash_fraction:
            reasons.append('Покупка затронет ваш денежный резерв.')
        if gross / total_after > limits.max_trade_fraction:
            reasons.append('Даже один лот слишком велик относительно вашего капитала.')
        for dim, key, cap in (
            ('issuer', candidate.issuer, limits.max_issuer_fraction),
            ('sector', candidate.sector, limits.max_sector_fraction),
            ('asset_class', candidate.asset_class, limits.max_class_fraction.get(candidate.asset_class, Decimal(0))),
            ('rating_bucket', candidate.rating_bucket, limits.max_rating_fraction.get(candidate.rating_bucket, Decimal(0))),
        ):
            previous = exposure['groups'][dim].get(key, Decimal(0)) * exposure['total']
            if (previous + gross) / total_after > money(cap):
                reasons.append({'issuer': 'На эту компанию уже приходится слишком большая доля.',
                                'sector': 'Покупка усилит зависимость от одной отрасли.',
                                'asset_class': 'Превышается лимит этого класса активов.',
                                'rating_bucket': 'Превышается лимит бумаг с таким рейтингом.'}[dim])
    if gross > daily * limits.max_daily_liquidity_fraction:
        reasons.append('Размер покупки слишком велик относительно обычного объёма торгов.')
    return {'eligible': not reasons, 'reasons': reasons, 'ticker': candidate.ticker, 'isin': candidate.isin,
            'instrument_uid': candidate.uid, 'estimated_cost': str(gross+fee), 'currency': base_currency,
            'url': official_instrument_url(candidate.asset_class, candidate.ticker),
            'source_ids': [candidate.evidence.source_id, liquidity_evidence.source_id, fundamentals_evidence.source_id]
                          + ([candidate.credit.evidence.source_id] if candidate.credit else []),
            'explanation': 'Один лот проходит указанные ограничения. Это ещё не сравнение со всеми альтернативами и не поручение на покупку.' if not reasons else 'Покупка пока не предлагается: ' + ' '.join(reasons)}
