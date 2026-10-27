"""Compose owner-scoped system status from already-loaded persisted evidence.

Pure application service: the caller supplies the authenticated user's current
broker-bound snapshot and strategy. This module never opens a DB or calls a
broker. Acceptance declarations are deliberately separate from data freshness.
"""
from __future__ import annotations

from datetime import datetime

try:
    from . import application_hierarchy, market_schedule, public_sources
    from .source_observability import clock, lane_inventory, mapping, news_inventory, provenance_inventory
except ImportError:
    import application_hierarchy
    import market_schedule
    import public_sources
    from source_observability import clock, lane_inventory, mapping, news_inventory, provenance_inventory


PERMANENT_GAPS = (
    ("automatic_ratings_incomplete", "Автоматический проверенный охват четырёх рейтинговых агентств не завершён."),
    ("independent_cash_reconciliation_pending", "Полная независимая сверка денежных остатков ещё не подключена."),
    ("investment_planner_incomplete", "Полный планировщик с учётом пригодности и всех издержек ещё не принят."),
    ("execution_simulation_only", "Журнал исполнения проверен в симуляции; реальный брокерский исполнитель не включён."),
    ("sandbox_acceptance_pending", "Проверка исполнения и сверки в песочнице брокера ещё не завершена."),
    ("shadow_sessions_pending", "Не подтверждены 30 фактических торговых сессий теневого наблюдения."),
    ("native_and_sonar_acceptance_pending", "Полная нативная приёмка и Sonar для точных исходников остаются открытыми."),
)


def _calendar(snapshot: dict | None, now: datetime) -> dict:
    try:
        return market_schedule.polling_state(mapping(snapshot).get("calendar"),
            market_schedule.required_exchanges(snapshot), now=now)
    except (ValueError, TypeError, KeyError, AttributeError):
        return {"state": "unknown", "reason": "calendar_input_invalid",
                "regular_price_polling_allowed": False, "trade_permission": False}


def _public_sources(snapshot: dict | None, now: datetime) -> dict:
    try:
        result = public_sources.snapshot_status(snapshot, at=now)
        return {key: result.get(key) for key in ("provider", "state", "checked_at", "eligible_identifiers",
            "mapped_identifiers", "missing_identifiers", "coverage_scope", "rating_sources_fetched",
            "automatic_trade_permission")}
    except (ValueError, TypeError, KeyError, AttributeError):
        return {"state": "unavailable", "reason": "public_source_status_invalid",
                "rating_sources_fetched": False, "automatic_trade_permission": False}


def _mandate(snapshot: dict | None, strategy: dict | None) -> dict:
    config = mapping(mapping(strategy).get("config"))
    mandate = mapping(config.get("mandate"))
    accounts = mapping(snapshot).get("accounts", [])
    if not isinstance(accounts, list):
        accounts = []
    account_present = bool(mandate) and mandate.get("account_id") in {
        row.get("id") for row in accounts if isinstance(row, dict) and isinstance(row.get("id"), str)}
    return {"configured": bool(mandate), "strategy_version": mapping(strategy).get("version"),
            "selected_account_in_snapshot": account_present,
            "full_suitability_verified": False,
            "limits_saved_are_not_execution_permission": True}


def build_status(snapshot: dict | None, strategy: dict | None, *, connected: bool,
                 now: datetime | None = None) -> dict:
    if type(connected) is not bool:
        raise ValueError("readiness_connection_flag_invalid")
    now = clock(now)
    # A disconnected or changed broker context cannot inherit an old snapshot.
    snapshot = snapshot if connected and isinstance(snapshot, dict) else None
    data = mapping(snapshot)
    lanes = lane_inventory(snapshot, now=now)
    provenance = provenance_inventory(snapshot, now=now)
    mandate = _mandate(snapshot, strategy)
    blockers = [{"code": code, "message": message, "kind": "implementation_or_acceptance"}
                for code, message in PERMANENT_GAPS]
    if not connected:
        blockers.append({"code": "tinvest_not_connected", "message": "Нет действующего подключения брокера.", "kind": "connection"})
    elif snapshot is None:
        blockers.append({"code": "workspace_refresh_required", "message": "Нет снимка для текущего подключения брокера.", "kind": "data"})
    if not mandate["configured"]:
        blockers.append({"code": "mandate_not_configured", "message": "Инвестиционный профиль не задан.", "kind": "configuration"})
    elif not mandate["selected_account_in_snapshot"]:
        blockers.append({"code": "mandate_account_not_in_snapshot", "message": "Выбранный счёт не подтверждён текущим снимком.", "kind": "configuration"})
    for lane in lanes:
        if lane["state"] != "current":
            blockers.append({"code": lane["id"] + "_data_" + lane["state"],
                "message": lane["title"] + ": данные требуют проверки.", "kind": "data"})
    calendar = _calendar(snapshot, now)
    if calendar.get("state") == "unknown":
        blockers.append({"code": "calendar_not_verified", "message": "Торговое расписание не подтверждено.", "kind": "data"})
    ledger = mapping(data.get("cash_ledger"))
    return {"schema_version": 1, "evaluated_at": now.isoformat(),
            "snapshot_id": data.get("snapshot_id"), "valuation_as_of": data.get("as_of"),
            "state": "not_connected" if not connected else "awaiting_snapshot" if snapshot is None else "restricted_read_only",
            "execution_mode": "read_only", "real_orders_enabled": False,
            "paid_ai_started_by_read": False, "network_started_by_read": False,
            "lanes": lanes, "provenance": provenance, "news": news_inventory(snapshot, now=now),
            "calendar": calendar, "public_identity": _public_sources(snapshot, now), "mandate": mandate,
            "accounting": {"ledger_state": ledger.get("state", "not_collected"),
                "operation_counts": dict(mapping(ledger.get("operation_counts"))),
                "cash_reconciliation_algorithm": "available_for_complete_supplied_evidence",
                "twr_algorithm": "exact_external_flow_valuations", "xirr_algorithm": "actual_365_with_unique_root_gate",
                "live_cash_reconciled": False, "live_performance_calculated": False,
                "tax_liability_estimated": False, "missing_data_is_zero": False},
            "hierarchy": application_hierarchy.hierarchy(), "blockers": blockers,
            "complete_autonomous_portfolio": False,
            "status_read_does_not_refresh_evidence": True}
