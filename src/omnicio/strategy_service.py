"""Bounded, owner-scoped I/O for the saved-strategy account assessment."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import UUID

from .backtest import (
    MAX_RESEARCH_ASSETS,
    MAX_RESEARCH_DAYS,
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
    BrokerNotConnected,
    BrokerService,
)
from .cbr import CBRClient, CBRUnavailable
from .freshness import PORTFOLIO_MAX_AGE, describe_freshness
from .portfolio_store import PortfolioStore, SettingsVersionConflict
from .research_store import ResearchStore
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
from .tbank import TBankHistoricCandle, TBankUnavailable


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


def _research_rows(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Bound the inspected universe, interleaving classes instead of taking only bonds."""
    catalog = _research_catalog_rows(context)
    classes = [
        [row for row in catalog if row.get("instrument_type") == kind]
        for kind in ("share", "bond", "etf")
    ]
    result: list[dict[str, Any]] = []
    for index in range(MAX_RESEARCH_ASSETS):
        for rows in classes:
            if index < len(rows) and len(result) < MAX_RESEARCH_ASSETS:
                result.append(rows[index])
    return result


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
) -> tuple[TBankHistoricCandle, ...]:
    if row.get("instrument_type") != "bond":
        return bars
    values = evidence.get("bond_valuations", []) if evidence else []
    if values:
        by_day = {datetime.fromisoformat(item["time"]).date(): item for item in values}
        if any(bar.time.date() not in by_day for bar in bars):
            return ()
        result = []
        for bar in bars:
            value = by_day[bar.time.date()]
            nominal = Decimal(value["nominal_rub"])
            opening = Decimal(value["accrued_interest_open_rub"])
            closing = Decimal(value["accrued_interest_close_rub"])
            result.append(
                replace(
                    bar,
                    open=str(Decimal(bar.open) * nominal / 100 + opening) if bar.open else None,
                    close=str(Decimal(bar.close) * nominal / 100 + closing),
                    # Conservative intraday bounds; only exact opening/closing NKD
                    # affect order fills and valuation in this daily model.
                    high=str(Decimal(bar.high) * nominal / 100 + max(opening, closing))
                    if bar.high
                    else None,
                    low=str(Decimal(bar.low) * nominal / 100 + min(opening, closing))
                    if bar.low
                    else None,
                )
            )
        return tuple(result)
    if (
        str(row.get("nominal_currency") or "").upper() != "RUB"
        or row.get("amortization") is not False
    ):
        # A changing/foreign nominal cannot be retrospectively replaced by today's nominal.
        return ()
    try:
        nominal = Decimal(str(row.get("nominal_value")))
    except InvalidOperation:
        return ()
    if not nominal.is_finite() or nominal <= 0:
        return ()
    result = []
    for bar in bars:
        values = {}
        for name in ("open", "high", "low", "close"):
            raw = getattr(bar, name)
            values[name] = str(Decimal(raw) * nominal / 100) if raw is not None else None
        result.append(
            replace(
                bar,
                open=values["open"],
                high=values["high"],
                low=values["low"],
                close=str(Decimal(bar.close) * nominal / 100),
            )
        )
    return tuple(result)


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
    source = "https://developer.tbank.ru/invest/api/instruments-service-get-asset-fundamentals"
    result = {}
    for item in values:
        facts = {}
        for key, raw in (
            ("debt_to_ebitda", item.total_debt_to_ebitda_mrq),
            ("free_cash_flow_ttm", item.free_cash_flow_ttm),
            ("net_income_ttm", item.net_income_ttm),
        ):
            if raw is not None:
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
        result[item.asset_uid] = facts
    return result


def _user_asset_evidence(
    asset: ResearchAsset,
    evidence: Mapping[str, Any] | None,
    from_at: datetime,
    to_at: datetime,
) -> ResearchAsset:
    if not evidence:
        return asset
    facts = dict(asset.candidate.facts)
    for name, row in evidence["facts"].items():
        value = row["value"]
        if name == "maturity_date":
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif name not in {"issuer_id", "group_id", "sector", "rating"} and type(value) is not bool:
            value = Decimal(value)
        facts[name] = StrategyFact(
            value, datetime.fromisoformat(row["available_at"]), row["source_url"]
        )
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
    cashflows = tuple(
        HistoricalCashflow(
            datetime.fromisoformat(row["entitlement_at"]),
            datetime.fromisoformat(row["paid_at"]),
            Decimal(row["amount_per_unit_rub"]),
            row["source_url"],
            cast(Any, row.get("kind", "income")),
        )
        for row in evidence["cashflows"]
    )
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
    )


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
) -> tuple[list[ResearchAsset], list[str]]:
    fundamentals = _research_fundamentals(user_id, rows, broker, now)
    assets = []
    unavailable = []
    ratings_read = 0
    supplied = {row["instrument_uid"]: row for row in evidence.get("assets", [])}
    key_rate = None
    if cbr is not None and document["rules"]["yield_floor"] == "key_rate":
        with suppress(CBRUnavailable):
            key_rate = cbr.latest_indicators().key_rate
    for row in rows:
        candidate = _row_candidate(row, now)
        facts = {**candidate.facts, **fundamentals.get(str(row.get("asset_uid")), {})}
        if candidate.asset_class == "bonds" and ratings_read < STRATEGY_RATING_READ_LIMIT:
            ratings_read += 1
            rating = _research_rating(user_id, candidate.instrument_uid, broker, now)
            if rating is not None:
                facts["rating"] = rating
        candidate = replace(candidate, facts=facts)
        try:
            bars = broker.candidate_daily_exchange_candles(
                user_id,
                candidate.instrument_uid,
                from_at=from_at,
                to_at=to_at,
            )
        except TBankUnavailable:
            bars = ()
            unavailable.append(candidate.instrument_uid)
        supplied_asset = supplied.get(candidate.instrument_uid)
        bars = _research_price_bars(
            row, bars, supplied_asset if _evidence_covers(supplied_asset, from_at, to_at) else None
        )
        facts.update(
            _current_method_facts(user_id, row, candidate, bars, broker, now, document, costs)
        )
        if key_rate is not None:
            facts["key_rate_percent"] = StrategyFact(
                Decimal(key_rate.value), now, "https://www.cbr.ru/hd_base/KeyRate/"
            )
        candidate = replace(candidate, facts=facts)
        assets.append(
            _user_asset_evidence(
                ResearchAsset(candidate, bars),
                supplied.get(candidate.instrument_uid),
                from_at,
                to_at,
            )
        )
    return assets, unavailable


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
) -> dict[str, Any]:
    """At most 12 assets, 8 ratings, one fundamentals batch and 12 method reads.

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
    fingerprint = document_hash(document)
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
    rows = _research_rows(context)
    evidence = (
        research_store.evidence(user_id)
        if research_store is not None
        else {
            "version": 0,
            "document": {"assets": []},
            "received_at": None,
        }
    )
    assets, unavailable = _research_assets(
        user_id,
        rows,
        broker,
        from_at,
        to_at,
        now,
        document=document,
        costs=costs,
        evidence=evidence["document"],
        cbr=cbr,
    )
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
                )
                for asset in assets
            ],
            as_of=now,
        )
    latest = store.current_strategy_draft(user_id)
    if (
        latest is None
        or latest["version"] != expected_version
        or document_hash(normalize_document(latest["document"])) != fingerprint
    ):
        raise SettingsVersionConflict("settings_version_conflict")
    if broker.status(user_id) != connection:
        raise BrokerConnectionError("strategy_account_changed")
    result = {
        **payload,
        "strategy_version": expected_version,
        "account_id": connection.account_id,
        "environment": connection.environment,
        "provider_unavailable_assets": unavailable,
        "input_provenance": {
            "user_supplied": bool(evidence["document"]["assets"]),
            "evidence_version": evidence["version"],
            "received_at": evidence["received_at"],
            "independently_verified": False if evidence["document"]["assets"] else None,
            "scope": "Дополнительные факты и полноту истории подтверждает пользователь; "
            "ссылка на источник не означает независимую проверку сервисом.",
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
        },
    }
    if research_store is not None:
        if not connection.account_id or not connection.environment or not connection.verified_at:
            raise BrokerConnectionError("strategy_account_changed")
        inputs = research_inputs(
            document,
            assets,
            from_at=from_at,
            to_at=to_at,
            capital=initial_capital_rub,
            costs=costs,
            observed=now,
        )
        result["archive"] = research_store.save_run(
            user_id,
            result=result,
            inputs=inputs,
            account_id=connection.account_id,
            environment=connection.environment,
            connection_verified_at=connection.verified_at,
            strategy_version=expected_version,
            evidence_version=evidence["version"],
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
        "engine_version": "1.1.0",
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
    if inputs.get("schema_version") != 1 or inputs.get("engine_version") != "1.1.0":
        raise ValueError("research_replay_version_unsupported")
    assets = []
    for row in inputs["assets"]:
        candidate = row["candidate"]
        facts = {}
        for name, raw in candidate["facts"].items():
            value = raw["value"]
            if name == "maturity_date":
                value = datetime.fromisoformat(str(value))
            elif (
                name not in {"issuer_id", "group_id", "sector", "rating"}
                and type(value) is not bool
            ):
                value = Decimal(str(value))
            facts[name] = StrategyFact(
                value, datetime.fromisoformat(str(raw["available_at"])), raw["source_url"]
            )
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
    )
    result["robustness"] = research_robustness(
        inputs["document"],
        assets,
        from_at=begin,
        to_at=end,
        initial_capital_rub=capital,
        costs=costs,
        now=observed,
    )
    return result
