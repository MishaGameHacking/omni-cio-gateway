"""Bounded, owner-scoped I/O for the saved-strategy account assessment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from .backtest import (
    MAX_RESEARCH_ASSETS,
    MAX_RESEARCH_DAYS,
    ResearchAsset,
    ResearchCosts,
    history_candidate,
    run_strategy_backtest,
)
from .broker import (
    STRATEGY_RATING_READ_LIMIT,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerService,
)
from .freshness import PORTFOLIO_MAX_AGE, describe_freshness
from .portfolio_store import PortfolioStore, SettingsVersionConflict
from .strategy import document_hash, normalize_document
from .strategy_assessment import (
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
) -> tuple[TBankHistoricCandle, ...]:
    if row.get("instrument_type") != "bond":
        return bars
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
                if number.is_finite():
                    facts[key] = StrategyFact(number, now, source)
        # The source does not document ROE's numeric scale, so its raw value
        # cannot satisfy a percentage-based profitability threshold.
        # The provider does not expose publication time in this DTO. These facts
        # may support today's screen, never selection inside an earlier backtest.
        result[item.asset_uid] = facts
    return result


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
) -> dict[str, Any]:
    """At most 12 candle reads, 8 rating reads and one batched fundamentals read.

    Browser input specifies only the research window and explicit hypothetical
    costs/capital. The authenticated connection and durable catalog choose assets.
    A connection/draft change at any point prevents release of the collected data.
    """
    now = datetime.now(UTC)
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
            for value in (commission_bps, slippage_bps)
        )
    ):
        raise ValueError("research_parameters_invalid")
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
    fundamentals = _research_fundamentals(user_id, rows, broker, now)
    assets = []
    unavailable = []
    ratings_read = 0
    for row in rows:
        candidate = _row_candidate(row, now)
        facts = {**candidate.facts, **fundamentals.get(str(row.get("asset_uid")), {})}
        if candidate.asset_class == "bonds" and ratings_read < STRATEGY_RATING_READ_LIMIT:
            ratings_read += 1
            try:
                ratings = broker.candidate_bond_ratings(user_id, candidate.instrument_uid)
            except TBankUnavailable:
                ratings = ()
            notches = [rating_notch(item, now) for item in ratings]
            if ratings and all(notch is not None for notch in notches):
                from .strategy import RATING_LEVELS

                notch = max((n for n in notches if n is not None), key=RATING_LEVELS.index)
                facts["rating"] = StrategyFact(
                    notch,
                    max(item.rating_date for item in ratings),
                    "https://developer.tbank.ru/invest/api/instruments-service-bond-by",
                )
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
        bars = _research_price_bars(row, bars)
        assets.append(ResearchAsset(candidate, bars))
    payload = run_strategy_backtest(
        document,
        assets,
        from_at=from_at,
        to_at=to_at,
        initial_capital_rub=initial_capital_rub,
        costs=ResearchCosts(commission_bps, slippage_bps),
        now=now,
    )
    if to_at >= now - timedelta(days=4):
        payload["current_selection"] = select_strategy_candidates(
            document,
            [history_candidate(asset.candidate, asset.candles, as_of=now) for asset in assets],
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
    return {
        **payload,
        "strategy_version": expected_version,
        "account_id": connection.account_id,
        "environment": connection.environment,
        "provider_unavailable_assets": unavailable,
        "universe": {
            "scope": "current_account_catalog",
            "assets_read": len(assets),
            "maximum_assets": MAX_RESEARCH_ASSETS,
            "historical_universe_verified": False,
        },
    }
