"""Bounded, owner-scoped I/O for the saved-strategy account assessment."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from time import monotonic
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from .backtest import (
    MAX_RESEARCH_ASSETS,
    MAX_RESEARCH_DAYS,
    RESEARCH_ENGINE_VERSION,
    BondValuation,
    FactorObservation,
    HistoricalCashflow,
    HistoricalSplit,
    ResearchAsset,
    ResearchBasis,
    ResearchCosts,
    history_candidate,
    research_robustness,
    run_strategy_backtest,
    split_adjusted_history,
)
from .broker import (
    STRATEGY_RATING_READ_LIMIT,
    BrokerConnectionError,
    BrokerConnectionStatus,
    BrokerNotConnected,
    BrokerService,
)
from .cbr import CBRClient, CBRUnavailable
from .freshness import PORTFOLIO_MAX_AGE, describe_freshness
from .portfolio_store import PortfolioStore, SettingsVersionConflict
from .research_store import ResearchNotFound, ResearchStore
from .strategy import RATING_LEVELS, document_hash, normalize_document
from .strategy_assessment import (
    FundConstituent,
    IssuerEvidence,
    StrategyCandidateFacts,
    StrategyFact,
    assess_strategy_account,
    rating_notch,
    select_strategy_candidates,
)
from .tbank import (
    TBankAccruedInterest,
    TBankAssetFundamental,
    TBankBondCoupon,
    TBankBondEvent,
    TBankDividend,
    TBankHistoricCandle,
    TBankTokenRejected,
    TBankUnavailable,
)

_MOSCOW = ZoneInfo("Europe/Moscow")
_RESEARCH_WORKERS = 4
_RESEARCH_DEADLINE_SECONDS = 180
_DIVIDEND_SOURCE = "https://developer.tbank.ru/invest/api/instruments-service-get-dividends"
_BOND_EVENT_SOURCE = "https://developer.tbank.ru/invest/api/instruments-service-get-bond-events"
_ACCRUAL_SOURCE = "https://developer.tbank.ru/invest/api/instruments-service-get-accrued-interests"


def _identity_time(row: Mapping[str, Any], prefix: str, now: datetime) -> datetime | None:
    verified = row.get(prefix + "_verified_at")
    effective = row.get(prefix + "_effective_at")
    if not (
        isinstance(verified, datetime)
        and verified.tzinfo is not None
        and timedelta(0) <= now - verified < timedelta(days=30)
    ):
        return None
    if not (isinstance(effective, datetime) and effective.tzinfo is not None and effective <= now):
        return None
    return verified


def _issuer_mapping(row: Mapping[str, Any], now: datetime) -> IssuerEvidence | None:
    issuer_time = _identity_time(row, "issuer", now)
    mapping_time = _identity_time(row, "mapping", now)
    if issuer_time is None or mapping_time is None:
        return None
    group_time = _identity_time(row, "group", now)
    return IssuerEvidence(
        instrument_uid=str(row.get("instrument_uid") or ""),
        issuer_id=str(row.get("issuer_id") or ""),
        group_id=str(row.get("group_id") or "") if group_time is not None else "",
        source_url=str(row.get("issuer_source_url") or ""),
        mapping_source_url=str(row.get("mapping_source_url") or ""),
        group_source_url=str(row.get("group_source_url") or ""),
        verified_at=min(issuer_time, mapping_time),
    )


def _issuer_mappings(
    context: Mapping[str, object] | None, account: str
) -> tuple[IssuerEvidence, ...]:
    if context is None or context.get("account_id") != account:
        return ()
    rows = context.get("holdings")
    if not isinstance(rows, (list, tuple)):
        return ()
    now = datetime.now(UTC)
    mappings = [_issuer_mapping(row, now) for row in rows if isinstance(row, dict)]
    return tuple(item for item in mappings if item is not None)


def current_account_assessment(
    *,
    user_id: UUID,
    expected_version: int,
    store: PortfolioStore,
    broker: BrokerService,
) -> dict[str, Any]:
    selection = store.current_strategy_draft(user_id)
    if selection is None:
        return {"status": "draft_required", "execution_enabled": False}
    if selection["version"] != expected_version:
        raise SettingsVersionConflict("settings_version_conflict")
    document = normalize_document(selection["document"])
    fingerprint = document_hash(document)
    connection = broker.status(user_id)
    if not connection.connected:
        raise BrokerNotConnected("T-Invest is not connected")
    bundle, ratings = broker.strategy_observation(user_id)
    if (bundle.account_id, bundle.environment) != (connection.account_id, connection.environment):
        raise BrokerConnectionError("strategy_account_changed")
    bond_ids = {p.uid for p in bundle.analysis.securities if p.instrument_type == "bond"}
    context = store.latest_balancing_context(user_id, candidate_limit=1)
    now = datetime.now(UTC)
    payload = assess_strategy_account(
        document,
        analysis=bundle.analysis,
        captured_at=bundle.refreshed_at,
        metadata=bundle.metadata,
        mappings=_issuer_mappings(context, bundle.account_id),
        ratings=ratings,
        now=now,
    )
    latest = store.current_strategy_draft(user_id)
    if latest is None or latest["version"] != expected_version:
        raise SettingsVersionConflict("settings_version_conflict")
    if document_hash(normalize_document(latest["document"])) != fingerprint:
        raise SettingsVersionConflict("settings_version_conflict")
    if broker.status(user_id) != connection:
        raise BrokerConnectionError("strategy_account_changed")
    return {
        **payload,
        "strategy_version": expected_version,
        "account_id": bundle.account_id,
        "environment": bundle.environment,
        "snapshot_hash": document_hash(
            {
                "account_id": bundle.account_id,
                "environment": bundle.environment,
                "captured_at": bundle.refreshed_at.isoformat(),
                "analysis": asdict(bundle.analysis),
            }
        ),
        "sources": [asdict(source) for source in bundle.sources],
        "rating_source": {
            "provider": "T-Invest BondBy / issuer ratings",
            "url": "https://developer.tbank.ru/invest/services/instruments/methods",
            "requested": len(ratings),
            "received": sum(bool(items) for items in ratings.values()),
            "total_bond_positions": len(bond_ids),
            "read_limit": STRATEGY_RATING_READ_LIMIT,
            "complete": len(ratings) == len(bond_ids) and all(ratings.values()),
        },
        "freshness": asdict(
            describe_freshness(
                bundle.refreshed_at,
                max_age=PORTFOLIO_MAX_AGE,
                now=now,
                coverage="complete" if bundle.analysis.status == "observed" else "partial",
            )
        ),
    }


def _research_catalog_rows(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for name in ("holdings", "candidates"):
        rows = context.get(name)
        if not isinstance(rows, (list, tuple)):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            uid = row.get("instrument_uid")
            if isinstance(uid, str) and uid:
                unique[uid] = {**unique.get(uid, {}), **row}
    return list(unique.values())


def _research_rows(
    context: Mapping[str, Any],
    document: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Keep held positions, then fund each mandate's required diversification capacity."""
    catalog = _research_catalog_rows(context)
    held_ids = {
        row["instrument_uid"]
        for row in context.get("holdings", [])
        if isinstance(row, dict)
        and row.get("instrument_uid")
        and row.get("instrument_type") != "currency"
    }
    if len(held_ids) > MAX_RESEARCH_ASSETS:
        raise ValueError("research_held_universe_too_large")
    chosen = {row["instrument_uid"]: row for row in catalog if row["instrument_uid"] in held_ids}
    queues = []
    for provider_kind, kind in (("share", "shares"), ("bond", "bonds"), ("etf", "funds")):
        wanted = _research_class_capacity(document, kind)
        available = [
            row
            for row in catalog
            if row.get("instrument_type") == provider_kind and row["instrument_uid"] not in chosen
        ]
        queues.append(available[:wanted])
    for index in range(MAX_RESEARCH_ASSETS):
        for queue in queues:
            if index < len(queue) and len(chosen) < MAX_RESEARCH_ASSETS:
                row = queue[index]
                chosen[row["instrument_uid"]] = row
    return list(chosen.values())


def _research_class_capacity(document: Mapping[str, Any], kind: str) -> int:
    target = Decimal(document["allocation"][kind])
    if target <= 0 or kind in document["excluded"]:
        return 0
    cap_keys = ["max_instrument_percent"]
    if kind != "funds":
        cap_keys.extend(("max_issuer_percent", "max_group_percent", "max_sector_percent"))
    caps = [
        Decimal(document["policy"][key]) for key in cap_keys if document["policy"][key] is not None
    ]
    if kind == "funds":
        caps.append(Decimal(document["rules"]["fund_wrapper_cap_percent"]))
    cap = min(caps) if caps else Decimal(0)
    minimum = int((target / cap).to_integral_value(rounding=ROUND_CEILING)) if cap > 0 else 0
    # Fifty percent headroom allows rejected rows without lowering risk ceilings.
    return min(MAX_RESEARCH_ASSETS, (minimum * 3 + 1) // 2)


def _row_candidate(row: Mapping[str, Any], now: datetime) -> StrategyCandidateFacts:
    source = "https://developer.tbank.ru/invest/services/instruments/methods"
    facts = {}
    retrieved = row.get("provider_retrieved_at")
    # Retrieval is a conservative availability bound. Do not substitute fiscal
    # period end or a maturity date for when a fact became available.
    if isinstance(retrieved, datetime) and retrieved.tzinfo is not None and retrieved <= now:
        for name in ("sector", "maturity_date", "perpetual", "floating_coupon"):
            value = row.get(name)
            if isinstance(value, (str, bool, datetime, int, Decimal)):
                facts[name] = StrategyFact(value, retrieved, source)
    mapping = _issuer_mapping(row, now)
    if mapping is not None:
        facts["issuer_id"] = StrategyFact(
            mapping.issuer_id, mapping.verified_at, mapping.source_url
        )
        if mapping.group_id:
            facts["group_id"] = StrategyFact(
                mapping.group_id, mapping.verified_at, mapping.group_source_url
            )
    lot = row.get("lot")
    return StrategyCandidateFacts(
        instrument_uid=str(row.get("instrument_uid") or ""),
        ticker=str(row.get("ticker") or ""),
        asset_class={"share": "shares", "bond": "bonds", "etf": "funds"}.get(
            str(row.get("instrument_type")), "unknown"
        ),
        lot_size=lot if type(lot) is int else 0,
        currency=str(row.get("currency") or ""),
        facts=facts,
    )


def _research_price_bars(
    row: Mapping[str, Any],
    bars: tuple[TBankHistoricCandle, ...],
    evidence: Mapping[str, Any] | None = None,
    accrued: tuple[TBankAccruedInterest, ...] = (),
) -> tuple[TBankHistoricCandle, ...]:
    if row.get("instrument_type") != "bond":
        return bars
    values = evidence.get("bond_valuations", []) if evidence else []
    if values:
        by_day = {datetime.fromisoformat(item["time"]).date(): item for item in values}
        if any(bar.time.date() not in by_day for bar in bars):
            return ()
        return tuple(_dirty_bond_bar(bar, by_day[bar.time.date()]) for bar in bars)
    if str(row.get("nominal_currency") or "").upper() != "RUB":
        return ()
    if accrued:
        by_day = {value.date.date(): value for value in accrued}
        if len(by_day) != len(accrued):
            return ()
        if all(bar.time.date() in by_day for bar in bars):
            return tuple(
                _clean_bond_bar(bar, Decimal(by_day[bar.time.date()].nominal)) for bar in bars
            )
    nominal = _unchanging_bond_nominal(row)
    if nominal is None:
        return ()
    return tuple(_clean_bond_bar(bar, nominal) for bar in bars)


def _unchanging_bond_nominal(row: Mapping[str, Any]) -> Decimal | None:
    # A changing nominal cannot be retrospectively replaced by today's nominal.
    if row.get("amortization") is not False:
        return None
    try:
        nominal = Decimal(str(row.get("nominal_value")))
    except InvalidOperation:
        return None
    return nominal if nominal.is_finite() and nominal > 0 else None


def _dirty_bond_bar(bar: TBankHistoricCandle, value: Mapping[str, Any]) -> TBankHistoricCandle:
    nominal = Decimal(value["nominal_rub"])
    opening = Decimal(value["accrued_interest_open_rub"])
    closing = Decimal(value["accrued_interest_close_rub"])
    # Intraday bounds are conservative; only exact opening/closing NKD affect fills/NAV.
    return TBankHistoricCandle(
        instrument_uid=bar.instrument_uid,
        volume_lots=bar.volume_lots,
        time=bar.time,
        is_complete=bar.is_complete,
        source=bar.source,
        open=str(Decimal(bar.open) * nominal / 100 + opening) if bar.open else None,
        close=str(Decimal(bar.close) * nominal / 100 + closing),
        high=str(Decimal(bar.high) * nominal / 100 + max(opening, closing)) if bar.high else None,
        low=str(Decimal(bar.low) * nominal / 100 + min(opening, closing)) if bar.low else None,
    )


def _clean_bond_bar(bar: TBankHistoricCandle, nominal: Decimal) -> TBankHistoricCandle:
    values = {}
    for name in ("open", "high", "low", "close"):
        raw = getattr(bar, name)
        values[name] = str(Decimal(raw) * nominal / 100) if raw is not None else None
    return TBankHistoricCandle(
        instrument_uid=bar.instrument_uid,
        volume_lots=bar.volume_lots,
        time=bar.time,
        is_complete=bar.is_complete,
        source=bar.source,
        open=values["open"],
        high=values["high"],
        low=values["low"],
        close=str(Decimal(bar.close) * nominal / 100),
    )


def _research_fundamentals(
    user_id: UUID,
    rows: list[dict[str, Any]],
    broker: BrokerService,
    now: datetime,
) -> dict[str, dict[str, StrategyFact]]:
    ids = tuple(dict.fromkeys(str(row.get("asset_uid")) for row in rows if row.get("asset_uid")))
    if not ids:
        return {}
    try:
        values = broker.candidate_fundamentals(user_id, ids)
    except TBankUnavailable:
        return {}
    observed = max(now, datetime.now(UTC))
    return {item.asset_uid: _fundamental_facts(item, observed) for item in values}


def _fundamental_facts(item: TBankAssetFundamental, now: datetime) -> dict[str, StrategyFact]:
    source = "https://developer.tbank.ru/invest/api/instruments-service-get-asset-fundamentals"
    facts = {}
    for key, raw in (
        ("debt_to_ebitda", item.total_debt_to_ebitda_mrq),
        ("free_cash_flow_ttm", item.free_cash_flow_ttm),
        ("net_income_ttm", item.net_income_ttm),
    ):
        if raw is None:
            continue
        number = Decimal(raw)
        if number.is_finite() and number != 0:
            facts[key] = StrategyFact(number, now, source)
    capitalization = item.market_capitalization
    cashflow = item.free_cash_flow_ttm
    if isinstance(capitalization, str) and isinstance(cashflow, str):
        cap, flow = Decimal(capitalization), Decimal(cashflow)
        if cap.is_finite() and flow.is_finite() and cap > 0 and flow != 0:
            facts["free_cashflow_yield_percent"] = StrategyFact(flow / cap * 100, now, source)
    payout = item.dividend_payout_ratio_fy
    if isinstance(payout, str):
        ratio = Decimal(payout)
        if ratio.is_finite() and ratio > 0:
            facts["payout_ratio_percent"] = StrategyFact(ratio, now, source)
    # The source does not document ROE's numeric scale, so its raw value
    # cannot satisfy a percentage-based profitability threshold.
    # The provider does not expose publication time in this DTO. These facts
    # may support today's screen, never selection inside an earlier backtest.
    return facts


def _user_asset_evidence(
    asset: ResearchAsset,
    evidence: Mapping[str, Any] | None,
    from_at: datetime,
    to_at: datetime,
) -> ResearchAsset:
    if not evidence:
        return asset
    facts = {
        **asset.candidate.facts,
        **{name: _research_fact(name, row) for name, row in evidence["facts"].items()},
    }
    constituents = tuple(
        FundConstituent(
            row["issuer_id"],
            row["sector"],
            row["group_id"],
            Decimal(row["weight_percent"]),
            datetime.fromisoformat(row["available_at"]),
            row["source_url"],
        )
        for row in evidence["constituents"]
    )
    coverage = evidence["coverage"]
    covered = _evidence_covers(evidence, from_at, to_at)
    supplied_cashflows = tuple(
        HistoricalCashflow(
            datetime.fromisoformat(row["entitlement_at"]),
            datetime.fromisoformat(row["paid_at"]),
            Decimal(row["amount_per_unit_rub"]),
            row["source_url"],
            cast(Any, row.get("kind", "income")),
        )
        for row in evidence["cashflows"]
    )
    cashflows = _research_cashflows(asset.observed_cashflows, supplied_cashflows, coverage)
    factors = tuple(
        FactorObservation(
            datetime.fromisoformat(row["time"]),
            datetime.fromisoformat(row["available_at"]),
            Decimal(row["growth_change"]),
            Decimal(row["inflation_change"]),
            row["source_url"],
        )
        for row in evidence.get("factors", [])
    )
    return ResearchAsset(
        candles=asset.candles,
        candidate=replace(asset.candidate, facts=facts, constituents=constituents),
        basis="verified_total_return" if covered else asset.basis,
        cashflows=cashflows if covered else (),
        lot_history_verified=covered,
        cashflow_history_verified=covered,
        verification_source=coverage["source_url"] if covered else "",
        corporate_action_dates=tuple(
            datetime.fromisoformat(when) for when in evidence["corporate_action_dates"]
        ),
        factors=factors,
        splits=tuple(
            HistoricalSplit(
                datetime.fromisoformat(row["time"]), Decimal(row["ratio"]), row["source_url"]
            )
            for row in evidence.get("splits", [])
        ),
        bond_valuations=tuple(
            BondValuation(
                datetime.fromisoformat(row["time"]),
                Decimal(row["nominal_rub"]),
                Decimal(row["accrued_interest_open_rub"]),
                Decimal(row["accrued_interest_close_rub"]),
                row["source_url"],
            )
            for row in evidence.get("bond_valuations", [])
        )
        if covered
        else (),
        observed_cashflows=cashflows,
        provider_observations=asset.provider_observations,
    )


def _research_cashflows(
    provider: tuple[HistoricalCashflow, ...],
    supplied: tuple[HistoricalCashflow, ...],
    coverage: Mapping[str, Any] | None,
) -> tuple[HistoricalCashflow, ...]:
    """A complete user interval replaces intersecting provider events, never adds versions.

    Events entirely outside that interval retain provider provenance. With no
    complete interval, dates cannot identify a correction separately from a new
    installment; only exact-date amount replacements are unambiguous. A complete
    correction interval must cover both the original and corrected event dates.
    """
    interval = None
    if coverage and coverage["cashflows_complete"]:
        interval = (
            datetime.fromisoformat(coverage["from"]),
            datetime.fromisoformat(coverage["to"]),
        )

    def replaced(row: HistoricalCashflow) -> bool:
        return (
            interval is not None
            and row.entitlement_at <= interval[1]
            and row.paid_at >= interval[0]
        )

    original = {
        (row.entitlement_at, row.paid_at, row.kind): row for row in provider if not replaced(row)
    }
    provider_kinds = {row.kind for row in original.values()}
    entitlement_keys = {(row.kind, row.entitlement_at) for row in original.values()}
    payment_keys = {(row.kind, row.paid_at) for row in original.values()}
    merged = dict(original)
    for row in supplied:
        key = (row.entitlement_at, row.paid_at, row.kind)
        shares_date = (row.kind, row.entitlement_at) in entitlement_keys or (
            row.kind,
            row.paid_at,
        ) in payment_keys
        incomplete = row.kind in provider_kinds and not replaced(row)
        if key not in original and (shares_date or incomplete):
            raise ValueError("research_cashflow_overlap_requires_complete_history")
        merged[key] = row
    return tuple(sorted(merged.values(), key=lambda row: (row.entitlement_at, row.paid_at)))


def _evidence_covers(
    evidence: Mapping[str, Any] | None, from_at: datetime, to_at: datetime
) -> bool:
    coverage = evidence.get("coverage") if evidence else None
    return bool(
        coverage
        and datetime.fromisoformat(coverage["from"]) <= from_at
        and datetime.fromisoformat(coverage["to"]) >= to_at
        and all(
            coverage[key]
            for key in ("cashflows_complete", "corporate_actions_complete", "lot_history_complete")
        )
    )


def _fund_profile_facts(
    user_id: UUID,
    asset_uid: str,
    broker: BrokerService,
    now: datetime,
) -> dict[str, StrategyFact]:
    fund = broker.candidate_fund_profile(user_id, asset_uid)
    source = "https://developer.tbank.ru/invest/api/instruments-service-get-asset-by"
    facts = {}
    if fund.total_expense_percent is not None:
        facts["expense_ratio_percent"] = StrategyFact(
            Decimal(fund.total_expense_percent), now, source
        )
    if fund.primary_index:
        facts["index_tracking"] = StrategyFact(True, now, source)
    return facts


def _trailing_dividend_facts(
    user_id: UUID,
    instrument_uid: str,
    price: Decimal,
    broker: BrokerService,
    now: datetime,
) -> dict[str, StrategyFact]:
    dividends = broker.candidate_dividends(
        user_id,
        instrument_uid,
        from_at=now - timedelta(days=366),
        to_at=now,
    )
    accepted = [
        item
        for item in dividends
        if item.dividend_type == "Regular Cash"
        and item.dividend_net.currency.upper() == "RUB"
        and item.declared_date
        and item.declared_date <= now
        and item.payment_date
        and now - timedelta(days=365) < item.payment_date <= now
    ]
    if not accepted:
        return {}
    source = "https://developer.tbank.ru/invest/api/instruments-service-get-dividends"
    annual_income = sum((Decimal(item.dividend_net.value) for item in accepted), Decimal(0))
    yield_fact = StrategyFact(annual_income / price * 100, now, source)
    return {
        "dividend_declared": StrategyFact(True, now, source),
        "dividend_yield_percent": yield_fact,
        "cashflow_yield_percent": yield_fact,
    }


def _bond_yield_facts(
    user_id: UUID,
    instrument_uid: str,
    broker: BrokerService,
    now: datetime,
) -> dict[str, StrategyFact]:
    values = broker.candidate_market_yields(user_id, (instrument_uid,))
    if not values or values[0].instrument_uid != instrument_uid:
        return {}
    observed = values[0]
    if not timedelta(0) <= now - observed.time <= timedelta(days=4):
        return {}
    return {
        "cashflow_yield_percent": StrategyFact(
            Decimal(observed.yield_percent),
            now,
            "https://developer.tbank.ru/invest/api/market-data-service-get-market-values",
        )
    }


def _current_method_facts(
    user_id: UUID,
    row: Mapping[str, Any],
    candidate: StrategyCandidateFacts,
    bars: tuple[TBankHistoricCandle, ...],
    broker: BrokerService,
    now: datetime,
    document: Mapping[str, Any],
    costs: ResearchCosts,
) -> dict[str, StrategyFact]:
    """Facts available today; provider data is never backdated to a fiscal period."""
    method = document["base_preset_id"]
    try:
        if candidate.asset_class == "funds" and method == "bogle" and row.get("asset_uid"):
            return _fund_profile_facts(user_id, str(row["asset_uid"]), broker, now)
        if method not in {"income", "dividends", "floating"} or not bars:
            return {}
        price = Decimal(bars[-1].close)
        if bars[-1].time + timedelta(days=4) < now or price <= 0:
            return {}
        if candidate.asset_class == "shares":
            facts = _trailing_dividend_facts(user_id, candidate.instrument_uid, price, broker, now)
        elif candidate.asset_class == "bonds":
            facts = _bond_yield_facts(user_id, candidate.instrument_uid, broker, now)
        else:
            return {}
    except TBankUnavailable:
        return {}
    gross_fact = facts.get("cashflow_yield_percent")
    tax = document["policy"]["securities_tax_rate_percent"]
    horizon = document["profile"]["horizon_months"]
    if gross_fact and tax is not None and horizon is not None and Decimal(horizon) > 0:
        gross = Decimal(str(gross_fact.value))
        net = gross - max(Decimal(0), gross) * Decimal(tax) / 100
        net -= (costs.commission_bps + costs.slippage_bps) * 2 / 100 * 12 / Decimal(horizon)
        facts["net_yield_percent"] = StrategyFact(net, now, gross_fact.source_url)
    return facts


def _validate_research_request(
    from_at: datetime,
    to_at: datetime,
    initial_capital_rub: Decimal,
    costs: ResearchCosts,
    now: datetime,
) -> None:
    if (
        from_at.tzinfo is None
        or to_at.tzinfo is None
        or not from_at < to_at <= now
        or to_at - from_at > timedelta(days=MAX_RESEARCH_DAYS)
        or to_at - from_at < timedelta(days=90)
    ):
        raise ValueError("research_window_invalid")
    if (
        not initial_capital_rub.is_finite()
        or not 0 < initial_capital_rub <= Decimal("1e12")
        or any(
            not value.is_finite() or not 0 <= value <= 1000
            for value in (costs.commission_bps, costs.slippage_bps)
        )
    ):
        raise ValueError("research_parameters_invalid")


def _research_rating(
    user_id: UUID,
    instrument_uid: str,
    broker: BrokerService,
    now: datetime,
) -> StrategyFact | None:
    try:
        ratings = broker.candidate_bond_ratings(user_id, instrument_uid)
    except TBankUnavailable:
        return None
    notches = [rating_notch(item, now) for item in ratings]
    if not ratings or any(notch is None for notch in notches):
        return None
    notch = max((n for n in notches if n is not None), key=RATING_LEVELS.index)
    return StrategyFact(
        notch,
        max(item.rating_date for item in ratings),
        "https://developer.tbank.ru/invest/api/instruments-service-bond-by",
    )


def _dividend_history(
    dividends: tuple[TBankDividend, ...],
    now: datetime,
) -> tuple[HistoricalCashflow, ...]:
    result = []
    for item in dividends:
        if (
            item.dividend_type not in {"Regular Cash", "Return of Capital"}
            or item.dividend_net.currency.upper() != "RUB"
            or item.last_buy_date is None
            or item.payment_date is None
            or item.declared_date is None
            or item.declared_date > item.payment_date
            or item.payment_date > now
        ):
            continue
        # Last-buy date is the provider's actual entitlement cutoff, which is
        # different from the later shareholder-register date under settlement.
        entitlement = item.last_buy_date.replace(hour=0, minute=0, second=0, microsecond=0)
        entitlement += timedelta(days=1)
        amount = Decimal(item.dividend_net.value)
        if amount > 0 and entitlement <= item.payment_date:
            result.append(
                HistoricalCashflow(
                    entitlement,
                    item.payment_date,
                    amount,
                    _DIVIDEND_SOURCE,
                    "principal" if item.dividend_type == "Return of Capital" else "income",
                )
            )
    return tuple(result)


def _bond_cashflow_history(
    coupons: tuple[TBankBondCoupon, ...],
    events: tuple[TBankBondEvent, ...],
    now: datetime,
) -> tuple[HistoricalCashflow, ...]:
    coupon_days = {item.coupon_date.date(): item for item in coupons}
    if len(coupon_days) != len(coupons):
        raise TBankUnavailable("ambiguous coupon dates")
    result = []
    for event in events:
        coupon = coupon_days.get(event.pay_date.date()) if event.pay_date else None
        cashflow = _bond_event_cashflow(event, coupon, now)
        if cashflow is not None:
            result.append(cashflow)
    return _provider_cashflows(result)


def _bond_event_cashflow(
    event: TBankBondEvent,
    coupon: TBankBondCoupon | None,
    now: datetime,
) -> HistoricalCashflow | None:
    payment = event.pay_one_bond
    if event.execution not in {"E", "ED", "ET", "ES"} or payment is None:
        return None
    paid = event.real_pay_date or (event.pay_date if event.execution == "E" else None)
    if paid is None or paid > now or payment.currency.upper() != "RUB":
        return None
    entitlement = event.fix_date
    kind = "income"
    if event.event_type == "EVENT_TYPE_CPN":
        if entitlement is None and coupon is not None:
            entitlement = coupon.fix_date
    elif event.event_type == "EVENT_TYPE_MTY" and event.operation_type in {"CA", "OA", "CM", "OM"}:
        kind = "principal"
    else:
        return None
    amount = Decimal(payment.value)
    if entitlement is None or entitlement > paid or amount <= 0:
        return None
    return HistoricalCashflow(entitlement, paid, amount, _BOND_EVENT_SOURCE, cast(Any, kind))


def _provider_cashflows(events: list[HistoricalCashflow]) -> tuple[HistoricalCashflow, ...]:
    keys = {(row.entitlement_at, row.paid_at, row.kind) for row in events}
    if len(keys) != len(events):
        raise TBankUnavailable("ambiguous provider cashflow events")
    return tuple(events)


@dataclass(frozen=True, slots=True)
class _ResearchRead:
    user_id: UUID
    broker: BrokerService
    from_at: datetime
    to_at: datetime
    now: datetime
    document: Mapping[str, Any]
    costs: ResearchCosts
    deadline: float


def _provider_history(
    request: _ResearchRead,
    row: Mapping[str, Any],
) -> tuple[tuple[HistoricalCashflow, ...], tuple[TBankAccruedInterest, ...], dict[str, Any]]:
    """Collect source histories, without claiming undocumented settlement/lot completeness."""
    uid, kind = str(row["instrument_uid"]), row.get("instrument_type")
    start = request.from_at - timedelta(days=366)
    observations: dict[str, Any] = {
        "retrieved_at": request.now.isoformat(),
        "from": start.isoformat(),
        "to": request.to_at.isoformat(),
        "missing": [],
        "facts": {},
    }
    if monotonic() >= request.deadline:
        observations["missing"].append("research_read_budget_exhausted")
        return (), (), observations
    if kind in {"share", "etf"}:
        try:
            dividends = request.broker.candidate_dividends(
                request.user_id,
                uid,
                from_at=start,
                to_at=request.to_at,
            )
            flows = _provider_cashflows(list(_dividend_history(dividends, request.now)))
        except TBankUnavailable:
            dividends, flows = (), ()
            observations["missing"].append("dividend_history_unavailable")
        observations["dividends"] = [asdict(item) for item in dividends]
        observations["missing"].extend(("historical_lot_sizes", "share_splits_and_other_actions"))
        if kind == "etf":
            observations["missing"].append("dated_fund_constituents")
        return flows, (), observations
    if kind != "bond":
        observations["missing"].append("unsupported_research_asset_class")
        return (), (), observations
    histories: dict[str, Any] = {}
    for name, operation in (
        ("coupons", request.broker.candidate_bond_coupons),
        ("bond_events", request.broker.candidate_bond_events),
        ("daily_accruals", request.broker.candidate_accrued_interests),
    ):
        if monotonic() >= request.deadline:
            histories[name] = ()
            observations["missing"].append(name + "_read_budget_exhausted")
            continue
        try:
            histories[name] = operation(request.user_id, uid, from_at=start, to_at=request.to_at)
        except TBankUnavailable:
            histories[name] = ()
            observations["missing"].append(name + "_unavailable")
        observations[name] = [asdict(item) for item in histories[name]]
    try:
        flows = _bond_cashflow_history(histories["coupons"], histories["bond_events"], request.now)
    except TBankUnavailable:
        flows = ()
        observations["missing"].append("bond_events_unavailable")
    observations["missing"].extend(("historical_lot_sizes", "bond_nkd_open_close_timing"))
    # Daily API observations supply dated nominal/NKD values. The provider does
    # not specify open/close settlement timestamps; never invent that precision.
    observations["daily_accrual_source"] = _ACCRUAL_SOURCE
    return flows, histories["daily_accruals"], observations


def _research_asset(
    request: _ResearchRead,
    row: dict[str, Any],
    fundamentals: Mapping[str, Mapping[str, StrategyFact]],
    supplied: Mapping[str, Any],
    fact_history: Mapping[str, tuple[StrategyFact, ...]],
) -> tuple[ResearchAsset, bool]:
    candidate = _row_candidate(row, request.now)
    if monotonic() >= request.deadline:
        return ResearchAsset(
            candidate,
            (),
            provider_observations={
                "missing": ["research_read_budget_exhausted"],
            },
        ), True
    facts = {**candidate.facts, **fundamentals.get(str(row.get("asset_uid")), {})}
    if candidate.asset_class == "bonds":
        rating = _research_rating(
            request.user_id, candidate.instrument_uid, request.broker, request.now
        )
        if rating is not None:
            facts["rating"] = rating
    candidate = replace(candidate, facts=facts, fact_history=fact_history)
    unavailable = False
    try:
        raw_bars = request.broker.candidate_daily_exchange_candles(
            request.user_id,
            candidate.instrument_uid,
            from_at=request.from_at,
            to_at=request.to_at,
        )
    except TBankUnavailable:
        raw_bars, unavailable = (), True
    flows, accrued, observations = _provider_history(request, row)
    supplied_asset = supplied.get(candidate.instrument_uid)
    bars = _research_price_bars(
        row,
        raw_bars,
        supplied_asset
        if _evidence_covers(supplied_asset, request.from_at, request.to_at)
        else None,
        accrued,
    )
    if monotonic() < request.deadline:
        current_facts = _current_method_facts(
            request.user_id,
            row,
            candidate,
            bars,
            request.broker,
            request.now,
            request.document,
            request.costs,
        )
        retrieved = datetime.now(UTC)
        facts.update(
            {key: replace(fact, available_at=retrieved) for key, fact in current_facts.items()}
        )
    observations["retrieved_at"] = datetime.now(UTC).isoformat()
    observations["normalized_cashflow_events"] = len(flows)
    observations["facts"] = {key: asdict(value) for key, value in facts.items()}
    candidate = replace(candidate, facts=facts)
    asset = ResearchAsset(
        candidate, bars, observed_cashflows=flows, provider_observations=observations
    )
    return _user_asset_evidence(asset, supplied_asset, request.from_at, request.to_at), unavailable


def _research_assets(
    user_id: UUID,
    rows: list[dict[str, Any]],
    broker: BrokerService,
    from_at: datetime,
    to_at: datetime,
    now: datetime,
    *,
    document: Mapping[str, Any],
    costs: ResearchCosts,
    evidence: Mapping[str, Any],
    cbr: CBRClient | None = None,
    fact_history: Mapping[str, Mapping[str, tuple[StrategyFact, ...]]] | None = None,
) -> tuple[list[ResearchAsset], list[str]]:
    deadline = monotonic() + _RESEARCH_DEADLINE_SECONDS
    fundamentals = _research_fundamentals(user_id, rows, broker, now)
    assets = []
    unavailable = []
    supplied = {row["instrument_uid"]: row for row in evidence.get("assets", [])}
    key_rates: tuple[StrategyFact, ...] = ()
    if cbr is not None and document["rules"]["yield_floor"] == "key_rate":
        rate_end = now if to_at >= now - timedelta(days=4) else to_at
        with suppress(CBRUnavailable):
            key_rates = tuple(
                StrategyFact(
                    Decimal(rate.value),
                    datetime.combine(
                        rate.effective_date, datetime.min.time(), tzinfo=_MOSCOW
                    ),
                    "https://www.cbr.ru/hd_base/KeyRate/",
                )
                for rate in cbr.key_rate_history(
                    from_at.astimezone(_MOSCOW).date(),
                    rate_end.astimezone(_MOSCOW).date(),
                )
            )
    request = _ResearchRead(user_id, broker, from_at, to_at, now, document, costs, deadline)
    with ThreadPoolExecutor(max_workers=_RESEARCH_WORKERS) as reads:
        pending = []
        for row in rows:
            history = dict((fact_history or {}).get(row["instrument_uid"], {}))
            if key_rates:
                history["key_rate_percent"] = key_rates
            pending.append(
                reads.submit(_research_asset, request, row, fundamentals, supplied, history)
            )
        for future in pending:
            asset, failed = future.result()
            assets.append(asset)
            if failed:
                unavailable.append(asset.candidate.instrument_uid)
    return assets, unavailable


@contextmanager
def _research_attempt(
    store: ResearchStore | None,
    user_id: UUID,
    request_id: UUID | None,
    input_hash: str,
) -> Iterator[dict[str, Any] | None]:
    if store is None or request_id is None:
        yield None
        return
    record = store.begin_request(user_id, request_id, input_hash)
    if not record.get("created"):
        if record["status"] == "completed":
            saved = store.run(user_id, record["run_id"])
            yield {
                **saved["result"],
                "archive": {
                    "id": str(saved["id"]),
                    "created_at": saved["created_at"],
                    "data_hash": saved["data_hash"],
                    "replay_available": True,
                },
            }
        else:
            yield {**record, "request_id": str(request_id), "execution_enabled": False}
        return
    try:
        yield None
    except (
        BrokerConnectionError,
        TBankUnavailable,
        TBankTokenRejected,
        ValueError,
    ) as exc:
        code = "research_failed"
        if str(exc) == "research_cashflow_overlap_requires_complete_history":
            code = str(exc)
        with suppress(ResearchNotFound):
            store.fail_request(user_id, request_id, code)
        raise


def _research_fact(name: str, raw: Mapping[str, Any]) -> StrategyFact:
    value = raw["value"]
    if name == "maturity_date":
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    elif name not in {"issuer_id", "group_id", "sector", "rating"} and type(value) is not bool:
        value = Decimal(str(value))
    return StrategyFact(value, datetime.fromisoformat(str(raw["available_at"])), raw["source_url"])


@dataclass(frozen=True, slots=True)
class _ResearchContext:
    """Validated inputs and identity to recheck after the bounded provider reads."""

    user_id: UUID
    expected_version: int
    request_id: UUID | None
    document: Mapping[str, Any]
    connection: BrokerConnectionStatus
    catalog: Mapping[str, Any]
    rows: list[dict[str, Any]]
    evidence: Mapping[str, Any]
    from_at: datetime
    to_at: datetime
    initial_capital_rub: Decimal
    costs: ResearchCosts
    observed_at: datetime


def strategy_research(
    *,
    user_id: UUID,
    expected_version: int,
    store: PortfolioStore,
    broker: BrokerService,
    from_at: datetime,
    to_at: datetime,
    commission_bps: Decimal,
    slippage_bps: Decimal,
    initial_capital_rub: Decimal,
    research_store: ResearchStore | None = None,
    cbr: CBRClient | None = None,
    request_id: UUID | None = None,
) -> dict[str, Any]:
    """At most 100 assets, four paced readers and 180 seconds of provider work.

    Browser input specifies only the research window and explicit hypothetical
    costs/capital. The authenticated connection and durable catalog choose assets.
    A connection/draft change at any point prevents release of the collected data.
    """
    now = datetime.now(UTC)
    costs = ResearchCosts(commission_bps, slippage_bps)
    _validate_research_request(from_at, to_at, initial_capital_rub, costs, now)
    selection = store.current_strategy_draft(user_id)
    if selection is None:
        return {"status": "draft_required", "execution_enabled": False}
    if selection["version"] != expected_version:
        raise SettingsVersionConflict("settings_version_conflict")
    document = normalize_document(selection["document"])
    connection = broker.status(user_id)
    if not connection.connected:
        raise BrokerNotConnected("T-Invest is not connected")
    context = store.latest_balancing_context(user_id, candidate_limit=100)
    if context is None:
        return {
            "status": "snapshot_required",
            "execution_enabled": False,
            "missing_requirements": ["account_instrument_catalog"],
        }
    if context.get("account_id") != connection.account_id:
        raise BrokerConnectionError("strategy_account_changed")
    rows = _research_rows(context, document)
    evidence = (
        research_store.evidence(user_id)
        if research_store is not None
        else {
            "version": 0,
            "document": {"assets": []},
            "received_at": None,
        }
    )
    request_hash = document_hash(
        {
            "engine_version": RESEARCH_ENGINE_VERSION,
            "strategy": document,
            "strategy_version": expected_version,
            "account_id": connection.account_id,
            "environment": connection.environment,
            "connection_verified_at": str(connection.verified_at),
            "evidence_version": evidence["version"],
            "from": from_at.isoformat(),
            "to": to_at.isoformat(),
            "commission_bps": str(commission_bps),
            "slippage_bps": str(slippage_bps),
            "initial_capital_rub": str(initial_capital_rub),
        }
    )
    with _research_attempt(research_store, user_id, request_id, request_hash) as previous:
        if previous is not None:
            return previous
        run = _ResearchContext(
            user_id,
            expected_version,
            request_id,
            document,
            connection,
            context,
            rows,
            evidence,
            from_at,
            to_at,
            initial_capital_rub,
            costs,
            now,
        )
        return _collect_research_result(run, store, broker, research_store, cbr)


def _collect_research_result(
    run: _ResearchContext,
    store: PortfolioStore,
    broker: BrokerService,
    research_store: ResearchStore | None,
    cbr: CBRClient | None,
) -> dict[str, Any]:
    user_id, expected_version = run.user_id, run.expected_version
    document, connection, evidence = run.document, run.connection, run.evidence
    from_at, to_at, now = run.from_at, run.to_at, run.observed_at
    costs, initial_capital_rub, request_id = run.costs, run.initial_capital_rub, run.request_id
    if not connection.account_id or not connection.environment or not connection.verified_at:
        raise BrokerConnectionError("strategy_account_changed")
    history_raw = (
        research_store.observed_facts(
            user_id,
            account_id=connection.account_id,
            environment=connection.environment,
        )
        if research_store is not None
        else {}
    )
    history = {
        uid: {
            key: tuple(_research_fact(key, value) for value in values)
            for key, values in facts.items()
        }
        for uid, facts in history_raw.items()
    }
    assets, unavailable = _research_assets(
        user_id,
        run.rows,
        broker,
        from_at,
        to_at,
        now,
        document=document,
        costs=costs,
        evidence=evidence["document"],
        cbr=cbr,
        fact_history=history,
    )
    now = datetime.now(UTC)
    payload = run_strategy_backtest(
        document,
        assets,
        from_at=from_at,
        to_at=to_at,
        initial_capital_rub=initial_capital_rub,
        costs=costs,
        now=now,
    )
    if to_at >= now - timedelta(days=4):
        payload["current_selection"] = select_strategy_candidates(
            document,
            [
                history_candidate(
                    asset.candidate,
                    split_adjusted_history(asset.candles, asset.splits, now),
                    as_of=now,
                    factors=asset.factors,
                    cashflows=asset.observed_cashflows,
                    document=document,
                    costs=costs,
                )
                for asset in assets
            ],
            as_of=now,
        )
    latest = store.current_strategy_draft(user_id)
    if (
        latest is None
        or latest["version"] != expected_version
        or document_hash(normalize_document(latest["document"])) != document_hash(document)
    ):
        raise SettingsVersionConflict("settings_version_conflict")
    if broker.status(user_id) != connection:
        raise BrokerConnectionError("strategy_account_changed")
    diagnostics = {row["instrument_uid"]: row for row in payload["asset_diagnostics"]}
    result = {
        **payload,
        "strategy_version": expected_version,
        "account_id": connection.account_id,
        "environment": connection.environment,
        "request_id": str(request_id) if request_id is not None else None,
        "provider_unavailable_assets": unavailable,
        "input_provenance": {
            "user_supplied": bool(evidence["document"]["assets"]),
            "evidence_version": evidence["version"],
            "received_at": evidence["received_at"],
            "independently_verified": False if evidence["document"]["assets"] else None,
            "scope": "Дополнительные факты и полноту истории подтверждает пользователь; "
            "ссылка на источник не означает независимую проверку сервисом. Полная "
            "история выплат пользователя заменяет события провайдера в подтверждённом диапазоне.",
        },
        "robustness": research_robustness(
            document,
            assets,
            from_at=from_at,
            to_at=to_at,
            initial_capital_rub=initial_capital_rub,
            costs=costs,
            now=now,
        ),
        "universe": {
            "scope": "current_account_catalog",
            "assets_read": len(assets),
            "maximum_assets": MAX_RESEARCH_ASSETS,
            "historical_universe_verified": False,
            "catalog_instruments": len(_research_catalog_rows(run.catalog)),
            "held_instruments": len(run.catalog.get("holdings", [])),
            "parallel_reads": _RESEARCH_WORKERS,
            "provider_deadline_seconds": _RESEARCH_DEADLINE_SECONDS,
            "selection_policy": "held_positions_then_required_class_capacity_with_headroom",
        },
        "data_coverage": [
            {
                "instrument_uid": asset.candidate.instrument_uid,
                "automatic_cashflow_events": asset.provider_observations.get(
                    "normalized_cashflow_events", 0
                ),
                "daily_accrual_observations": len(
                    asset.provider_observations.get("daily_accruals", [])
                ),
                "historical_fact_observations": sum(
                    len(values) for values in asset.candidate.fact_history.values()
                ),
                "missing": sorted(
                    set(
                        (
                            asset.provider_observations.get("missing", [])
                            if asset.basis != "verified_total_return"
                            else []
                        )
                        + diagnostics[asset.candidate.instrument_uid]["reasons"]
                    )
                ),
                "total_return_verified": asset.basis == "verified_total_return"
                and diagnostics[asset.candidate.instrument_uid]["status"] == "observed",
            }
            for asset in assets
        ],
    }
    if research_store is not None:
        inputs = research_inputs(
            document,
            assets,
            from_at=from_at,
            to_at=to_at,
            capital=initial_capital_rub,
            costs=costs,
            observed=now,
        )
        inputs["request_id"] = str(request_id) if request_id is not None else None
        result["archive"] = research_store.save_run(
            user_id,
            result=result,
            inputs=inputs,
            account_id=connection.account_id,
            environment=connection.environment,
            connection_verified_at=connection.verified_at,
            strategy_version=expected_version,
            evidence_version=evidence["version"],
            request_id=request_id,
        )
    return result


def research_inputs(
    document: Mapping[str, Any],
    assets: list[ResearchAsset],
    *,
    from_at: datetime,
    to_at: datetime,
    capital: Decimal,
    costs: ResearchCosts,
    observed: datetime,
) -> dict[str, Any]:
    """Archive all source values, including rejected candidates, for an offline replay."""
    return {
        "schema_version": 1,
        "engine_version": RESEARCH_ENGINE_VERSION,
        "document": dict(document),
        "assets": [asdict(a) for a in assets],
        "from_at": from_at.isoformat(),
        "to_at": to_at.isoformat(),
        "initial_capital_rub": str(capital),
        "commission_bps": str(costs.commission_bps),
        "slippage_bps": str(costs.slippage_bps),
        "observed_at": observed.isoformat(),
    }


def research_assets_from_inputs(inputs: Mapping[str, Any]) -> list[ResearchAsset]:
    """Replay an owner-authorized archived document with no external I/O."""
    if inputs.get("schema_version") != 1 or inputs.get("engine_version") not in {
        "1.1.0",
        RESEARCH_ENGINE_VERSION,
    }:
        raise ValueError("research_replay_version_unsupported")
    assets = []
    for row in inputs["assets"]:
        candidate = row["candidate"]
        facts = {name: _research_fact(name, raw) for name, raw in candidate["facts"].items()}
        history = {
            key: tuple(_research_fact(key, value) for value in values)
            for key, values in candidate.get("fact_history", {}).items()
        }
        constituents = tuple(
            FundConstituent(
                part["issuer_id"],
                part["sector"],
                part["group_id"],
                Decimal(str(part["weight_percent"])),
                datetime.fromisoformat(str(part["available_at"])),
                part["source_url"],
            )
            for part in candidate["constituents"]
        )
        parsed = StrategyCandidateFacts(
            candidate["instrument_uid"],
            candidate["ticker"],
            candidate["asset_class"],
            candidate["lot_size"],
            candidate["currency"],
            facts,
            constituents,
            history,
        )
        candles = tuple(
            TBankHistoricCandle(**{**bar, "time": datetime.fromisoformat(str(bar["time"]))})
            for bar in row["candles"]
        )
        cashflows = tuple(
            HistoricalCashflow(
                datetime.fromisoformat(str(event["entitlement_at"])),
                datetime.fromisoformat(str(event["paid_at"])),
                Decimal(str(event["amount_per_unit_rub"])),
                event["source_url"],
                cast(Any, event.get("kind", "income")),
            )
            for event in row["cashflows"]
        )
        assets.append(
            ResearchAsset(
                parsed,
                candles,
                cast(ResearchBasis, row["basis"]),
                cashflows,
                tuple(datetime.fromisoformat(str(at)) for at in row["corporate_action_dates"]),
                row["lot_history_verified"],
                row["cashflow_history_verified"],
                row["verification_source"],
                tuple(
                    FactorObservation(
                        datetime.fromisoformat(str(factor["time"])),
                        datetime.fromisoformat(str(factor["available_at"])),
                        Decimal(str(factor["growth_change"])),
                        Decimal(str(factor["inflation_change"])),
                        factor["source_url"],
                    )
                    for factor in row.get("factors", [])
                ),
                tuple(
                    HistoricalSplit(
                        datetime.fromisoformat(str(split["time"])),
                        Decimal(str(split["ratio"])),
                        split["source_url"],
                    )
                    for split in row.get("splits", [])
                ),
                tuple(
                    BondValuation(
                        datetime.fromisoformat(str(value["time"])),
                        Decimal(str(value["nominal_rub"])),
                        Decimal(str(value["accrued_interest_open_rub"])),
                        Decimal(str(value["accrued_interest_close_rub"])),
                        value["source_url"],
                    )
                    for value in row.get("bond_valuations", [])
                ),
                tuple(
                    HistoricalCashflow(
                        datetime.fromisoformat(str(event["entitlement_at"])),
                        datetime.fromisoformat(str(event["paid_at"])),
                        Decimal(str(event["amount_per_unit_rub"])),
                        event["source_url"],
                        cast(Any, event.get("kind", "income")),
                    )
                    for event in row.get("observed_cashflows", [])
                ),
                row.get("provider_observations", {}),
            )
        )
    return assets


def replay_research_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Re-run exactly archived inputs without network access."""
    assets = research_assets_from_inputs(inputs)
    costs = ResearchCosts(Decimal(inputs["commission_bps"]), Decimal(inputs["slippage_bps"]))
    begin, end = datetime.fromisoformat(inputs["from_at"]), datetime.fromisoformat(inputs["to_at"])
    observed, capital = (
        datetime.fromisoformat(inputs["observed_at"]),
        Decimal(inputs["initial_capital_rub"]),
    )
    result = run_strategy_backtest(
        inputs["document"],
        assets,
        from_at=begin,
        to_at=end,
        initial_capital_rub=capital,
        costs=costs,
        now=observed,
        engine_version=inputs["engine_version"],
    )
    result["robustness"] = research_robustness(
        inputs["document"],
        assets,
        from_at=begin,
        to_at=end,
        initial_capital_rub=capital,
        costs=costs,
        now=observed,
        engine_version=inputs["engine_version"],
    )
    return result
