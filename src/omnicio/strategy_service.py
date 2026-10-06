"""Bounded, owner-scoped I/O for the saved-strategy account assessment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from .broker import (
    STRATEGY_RATING_READ_LIMIT,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerService,
)
from .freshness import PORTFOLIO_MAX_AGE, describe_freshness
from .portfolio_store import PortfolioStore, SettingsVersionConflict
from .strategy import document_hash, normalize_document
from .strategy_assessment import IssuerEvidence, assess_strategy_account


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
