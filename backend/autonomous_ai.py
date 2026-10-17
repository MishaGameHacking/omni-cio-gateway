"""Autonomous, rules-first portfolio monitoring and insight feed.

This module deliberately separates deterministic data collection/risk checks from
paid model calls.  The scheduler stores verified T-Invest snapshots, derives
material changes, applies per-user budgets and only then asks ``analysis_engine``
for an explanation.  When AI credentials are unavailable, deterministic safety
cards continue to work and no paid request is attempted.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Mapping

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from . import app as backend
    from .ai_policy import (
        AnalysisBudget,
        AnalysisDecision,
        AnalysisReason,
        AnalysisSignals,
        AnalysisTier,
        decide_analysis,
    )
    from .analysis_engine import AnalysisEvidence, AnalysisReport, analyze_if_needed
    from .timeweb_ai import TimewebAIConfig, TimewebAIConfigurationError, TimewebAIError
    from .tinvest_portfolio import get_tinvest_portfolio
except ImportError:  # pragma: no cover - uvicorn top-level import compatibility
    import app as backend  # type: ignore[no-redef]
    from ai_policy import (  # type: ignore[no-redef]
        AnalysisBudget,
        AnalysisDecision,
        AnalysisReason,
        AnalysisSignals,
        AnalysisTier,
        decide_analysis,
    )
    from analysis_engine import AnalysisEvidence, AnalysisReport, analyze_if_needed  # type: ignore[no-redef]
    from timeweb_ai import TimewebAIConfig, TimewebAIConfigurationError, TimewebAIError  # type: ignore[no-redef]
    from tinvest_portfolio import get_tinvest_portfolio  # type: ignore[no-redef]

try:
    from .ai_budget import MoneyLedger, BudgetDenied
    from .ai_jobs import AnalysisQueue, CURRENT_JOB, drain, assert_current_owner_in
    from .ai_guarded_client import GuardedAIClient, GuardError
except ImportError:  # uvicorn top-level import compatibility
    from ai_budget import MoneyLedger, BudgetDenied
    from ai_jobs import AnalysisQueue, CURRENT_JOB, drain, assert_current_owner_in
    from ai_guarded_client import GuardedAIClient, GuardError

try:
    from .monitoring_access import (
        assert_monitoring_access, assert_monitoring_access_in, monitoring_connection,
    )
except ImportError:
    from monitoring_access import (
        assert_monitoring_access, assert_monitoring_access_in, monitoring_connection,
    )

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])
MOSCOW = timezone(timedelta(hours=3), name="Europe/Moscow")

SCHEDULER_INTERVAL_SECONDS = max(
    60,
    int(os.getenv("ANALYSIS_SCHEDULER_INTERVAL_SECONDS", "300")),
)
SCHEDULER_ENABLED = os.getenv("ANALYSIS_SCHEDULER_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
}
FAST_DAILY_LIMIT = max(0, int(os.getenv("ANALYSIS_FAST_DAILY_LIMIT", "4")))
STANDARD_DAILY_LIMIT = max(0, int(os.getenv("ANALYSIS_STANDARD_DAILY_LIMIT", "3")))
PREMIUM_DAILY_LIMIT = max(0, int(os.getenv("ANALYSIS_PREMIUM_DAILY_LIMIT", "1")))
MAX_FEED_LIMIT = 100

_scheduler_task: asyncio.Task[None] | None = None
_scheduler_owner = f"pid-{os.getpid()}-{uuid.uuid4().hex[:8]}"


class ProfileUpdate(BaseModel):
    risk_level: str = Field(pattern="^(conservative|moderate|aggressive)$")
    horizon: str = Field(pattern="^(short|medium|long)$")
    allowed_markets: list[str] = Field(default_factory=lambda: ["RU"], min_length=1, max_length=12)
    max_position_percent: float = Field(default=25.0, ge=5.0, le=60.0)
    min_cash_percent: float = Field(default=5.0, ge=0.0, le=50.0)
    notify_critical: bool = True
    notify_briefs: bool = True


class RefreshRequest(BaseModel):
    reason: str = Field(default="manual", max_length=40)


TARGET_ALLOCATIONS: dict[str, dict[str, float]] = {
    "conservative": {
        "Облигации": 50.0,
        "Фонды": 25.0,
        "Акции": 20.0,
        "Валюта и деньги": 5.0,
    },
    "moderate": {
        "Акции": 40.0,
        "Облигации": 30.0,
        "Фонды": 25.0,
        "Валюта и деньги": 5.0,
    },
    "aggressive": {
        "Акции": 60.0,
        "Фонды": 25.0,
        "Облигации": 10.0,
        "Валюта и деньги": 5.0,
    },
}


def init_autonomous_db() -> None:
    with closing(backend.connect()) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS analysis_profiles (
                user_id INTEGER PRIMARY KEY,
                risk_level TEXT NOT NULL DEFAULT 'moderate',
                horizon TEXT NOT NULL DEFAULT 'medium',
                allowed_markets_json TEXT NOT NULL DEFAULT '["RU"]',
                max_position_percent REAL NOT NULL DEFAULT 25,
                min_cash_percent REAL NOT NULL DEFAULT 5,
                notify_critical INTEGER NOT NULL DEFAULT 1,
                notify_briefs INTEGER NOT NULL DEFAULT 1,
                configured INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                digest TEXT NOT NULL,
                material_digest TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_user_time
                ON portfolio_snapshots(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS analysis_runs (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                tier TEXT NOT NULL,
                digest TEXT NOT NULL,
                state TEXT NOT NULL,
                model TEXT,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                error_code TEXT,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_analysis_runs_user_time
                ON analysis_runs(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS insight_cards (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                actions_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                uncertainties_json TEXT NOT NULL,
                valid_until TEXT,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_insight_cards_user_time
                ON insight_cards(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS analysis_budget_usage (
                user_id INTEGER NOT NULL,
                day_key TEXT NOT NULL,
                fast_calls INTEGER NOT NULL DEFAULT 0,
                standard_calls INTEGER NOT NULL DEFAULT 0,
                premium_calls INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(user_id, day_key)
            );

            CREATE TABLE IF NOT EXISTS market_facts (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                subject_id TEXT,
                fact_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                as_of TEXT NOT NULL,
                expires_at TEXT,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_market_facts_subject
                ON market_facts(subject_id, as_of DESC);

            CREATE TABLE IF NOT EXISTS scheduler_leases (
                name TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            );
            """
        )
        db.commit()
    AnalysisQueue(backend.connect).initialize()
    MoneyLedger(backend.connect).initialize()
    try:
        from .volume import initialize as initialize_workspace
    except ImportError:
        from volume import initialize as initialize_workspace
    initialize_workspace()


def _profile_from_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {
            "risk_level": "moderate",
            "horizon": "medium",
            "allowed_markets": ["RU"],
            "max_position_percent": 25.0,
            "min_cash_percent": 5.0,
            "notify_critical": True,
            "notify_briefs": True,
            "configured": False,
        }
    try:
        markets = json.loads(row["allowed_markets_json"])
    except (TypeError, ValueError):
        markets = ["RU"]
    return {
        "risk_level": row["risk_level"],
        "horizon": row["horizon"],
        "allowed_markets": markets if isinstance(markets, list) else ["RU"],
        "max_position_percent": float(row["max_position_percent"]),
        "min_cash_percent": float(row["min_cash_percent"]),
        "notify_critical": bool(row["notify_critical"]),
        "notify_briefs": bool(row["notify_briefs"]),
        "configured": bool(row["configured"]),
    }


def get_profile(user_id: int) -> dict[str, Any]:
    with closing(backend.connect()) as db:
        row = db.execute(
            "SELECT * FROM analysis_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return _profile_from_row(row)


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _decimal_value(payload: Any) -> float:
    if not isinstance(payload, dict):
        return 0.0
    try:
        return float(payload.get("units", 0)) + float(payload.get("nano", 0)) / 1_000_000_000
    except (TypeError, ValueError):
        return 0.0


def _money_value(payload: Any) -> float:
    if not isinstance(payload, dict):
        return 0.0
    return _decimal_value(payload.get("value"))


def _snapshot_features(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    positions: list[dict[str, Any]] = []
    cash: list[dict[str, Any]] = []
    for account in snapshot.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        for position in account.get("positions") or []:
            if not isinstance(position, dict):
                continue
            item = {
                "id": str(position.get("id") or ""),
                "ticker": position.get("ticker"),
                "quantity": round(_decimal_value(position.get("quantity")), 8),
            }
            if item["id"].startswith("cash:"):
                cash.append(item)
            else:
                positions.append(item)
    allocations = []
    for allocation in snapshot.get("allocations") or []:
        if isinstance(allocation, dict):
            allocations.append(
                {
                    "title": str(allocation.get("title") or ""),
                    "share": round(_decimal_value(allocation.get("sharePercent")), 1),
                }
            )
    return {
        "positions": sorted(positions, key=lambda item: item["id"]),
        "cash": sorted(cash, key=lambda item: item["id"]),
        "allocations": sorted(allocations, key=lambda item: item["title"]),
        "total_bucket": round(_money_value(snapshot.get("totalValue")) / 100.0) * 100,
        "verified_risk_fingerprint": snapshot.get("_volume_risk_fingerprint"),
        "verified_news_fingerprint": snapshot.get("_volume_news_fingerprint"),
    }


def _latest_snapshot(user_id: int) -> tuple[dict[str, Any] | None, sqlite3.Row | None]:
    with closing(backend.connect()) as db:
        row = db.execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if row is None:
        return None, None
    try:
        payload = json.loads(row["snapshot_json"])
    except (TypeError, ValueError):
        payload = None
    return payload if isinstance(payload, dict) else None, row


def _save_snapshot(user_id: int, snapshot: Mapping[str, Any]) -> tuple[str, str]:
    canonical = _canonical(snapshot)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    material = hashlib.sha256(
        _canonical(_snapshot_features(snapshot)).encode("utf-8")
    ).hexdigest()
    with closing(backend.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        assert_current_owner_in(db)
        assert_monitoring_access_in(db)
        db.execute(
            """
            INSERT INTO portfolio_snapshots(
                user_id, digest, material_digest, snapshot_json, status, created_at
            ) VALUES (?, ?, ?, ?, 'ready', ?)
            """,
            (user_id, digest, material, canonical, int(time.time())),
        )
        db.execute(
            """
            DELETE FROM portfolio_snapshots
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM portfolio_snapshots
                WHERE user_id = ? ORDER BY created_at DESC LIMIT 60
            )
            """,
            (user_id, user_id),
        )
        db.commit()
    return digest, material


def _analysis_day(now: datetime) -> str:
    return now.astimezone(MOSCOW).date().isoformat()


def _budget(user_id: int, now: datetime) -> AnalysisBudget:
    day_key = _analysis_day(now)
    with closing(backend.connect()) as db:
        row = db.execute(
            "SELECT * FROM analysis_budget_usage WHERE user_id = ? AND day_key = ?",
            (user_id, day_key),
        ).fetchone()
    return AnalysisBudget(
        fast_calls_left=max(0, FAST_DAILY_LIMIT - int(row["fast_calls"] if row else 0)),
        standard_calls_left=max(0, STANDARD_DAILY_LIMIT - int(row["standard_calls"] if row else 0)),
        premium_calls_left=max(0, PREMIUM_DAILY_LIMIT - int(row["premium_calls"] if row else 0)),
    )


def _reserve_budget(user_id: int, now: datetime, tier: AnalysisTier) -> bool:
    """Reserve an attempt atomically before the network call, even if it later fails."""
    limits = {
        AnalysisTier.FAST: ("fast_calls", FAST_DAILY_LIMIT),
        AnalysisTier.STANDARD: ("standard_calls", STANDARD_DAILY_LIMIT),
        AnalysisTier.PREMIUM: ("premium_calls", PREMIUM_DAILY_LIMIT),
    }
    if tier not in limits:
        return False
    column, limit = limits[tier]
    day_key = _analysis_day(now)
    with closing(backend.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT OR IGNORE INTO analysis_budget_usage(user_id, day_key) VALUES (?, ?)",
            (user_id, day_key),
        )
        # column comes only from the fixed whitelist above, never from a request.
        cursor = db.execute(
            f"UPDATE analysis_budget_usage SET {column} = {column} + 1 "
            f"WHERE user_id = ? AND day_key = ? AND {column} < ?",
            (user_id, day_key, limit),
        )
        reserved = cursor.rowcount == 1
        db.commit()
    return reserved


def _last_analysis(user_id: int) -> sqlite3.Row | None:
    with closing(backend.connect()) as db:
        return db.execute(
            "SELECT * FROM analysis_runs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()


def _has_reason_today(user_id: int, reason: AnalysisReason, now: datetime) -> bool:
    local = now.astimezone(MOSCOW)
    start_local = datetime.combine(local.date(), datetime.min.time(), tzinfo=MOSCOW)
    start = int(start_local.timestamp())
    with closing(backend.connect()) as db:
        row = db.execute(
            """
            SELECT 1 FROM analysis_runs
            WHERE user_id = ? AND reason = ? AND created_at >= ? LIMIT 1
            """,
            (user_id, reason.value, start),
        ).fetchone()
    return row is not None


def _schedule_flags(user_id: int, now: datetime, notify_briefs: bool) -> tuple[bool, bool]:
    if not notify_briefs:
        return False, False
    try:
        from .volume_notifications import due_flags
    except ImportError:
        from volume_notifications import due_flags
    def already_run(slot, local):
        reason = AnalysisReason.MORNING_BRIEF if slot == "morning" else AnalysisReason.EVENING_BRIEF
        start = int(local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        with closing(backend.connect()) as db:
            return db.execute("SELECT 1 FROM analysis_runs WHERE user_id=? AND reason=? AND created_at>=? LIMIT 1", (user_id, reason.value, start)).fetchone() is not None
    return due_flags(user_id, now, already_run)


def _allocation_map(snapshot: Mapping[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for allocation in snapshot.get("allocations") or []:
        if isinstance(allocation, dict):
            result[str(allocation.get("title") or "")] = _decimal_value(
                allocation.get("sharePercent")
            )
    return result


def _critical_risk(snapshot: Mapping[str, Any], profile: Mapping[str, Any]) -> tuple[bool, str | None]:
    total_money = snapshot.get("totalValue") or {}
    total = _money_value(total_money)
    currency = str(total_money.get("currency") or "").upper()
    values: dict[str, float] = {}
    titles: dict[str, str] = {}
    for account in snapshot.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        for position in account.get("positions") or []:
            if not isinstance(position, dict):
                continue
            identifier = str(position.get("id") or "")
            money = position.get("currentValue") or {}
            if not identifier or identifier.startswith("cash:") or not isinstance(money, dict):
                continue
            # Never add unlike currencies or treat a whole asset class as one issuer.
            if str(money.get("currency") or "").upper() != currency:
                continue
            values[identifier] = values.get(identifier, 0.0) + abs(_money_value(money))
            titles[identifier] = str(position.get("title") or position.get("ticker") or identifier)
    if total > 0 and values:
        identifier, value = max(values.items(), key=lambda item: item[1])
        share = value / total * 100.0
        threshold = min(80.0, float(profile["max_position_percent"]) + 15.0)
        if share >= threshold:
            return True, f"Высокая концентрация позиции: {titles[identifier]} — {share:.1f}%"
    yield_percent = _decimal_value(snapshot.get("expectedYieldPercent"))
    if yield_percent <= -25.0:
        return True, f"Отрицательный результат портфеля по данным API: {yield_percent:.1f}%"
    return False, None


def _signals(
    *,
    user_id: int,
    snapshot: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    previous_row: sqlite3.Row | None,
    material_digest: str,
    profile: Mapping[str, Any],
    now: datetime,
    force: bool,
) -> tuple[AnalysisSignals, str | None]:
    morning, evening = _schedule_flags(user_id, now, bool(profile["notify_briefs"]))
    previous_material = str(previous_row["material_digest"]) if previous_row else None
    # A refresh requests fresh data, never fabricates a portfolio transaction.
    material_changed = previous_material is not None and previous_material != material_digest

    current_features = _snapshot_features(snapshot)
    previous_features = _snapshot_features(previous) if previous else None
    portfolio_changed = bool(
        previous_features
        and previous_features.get("positions") != current_features.get("positions")
    )
    cash_changed = bool(
        previous_features
        and previous_features.get("cash") != current_features.get("cash")
    )
    critical, risk_message = _critical_risk(snapshot, profile)
    if snapshot.get("_volume_critical_risk"):
        critical, risk_message = True, snapshot.get("_volume_risk_message")
    last = _last_analysis(user_id)
    minutes_since = None
    if last is not None:
        minutes_since = max(0, int((now.timestamp() - int(last["created_at"])) / 60))
    recent_same_risk = (
        last is not None
        and last["reason"] == AnalysisReason.RISK_EVENT.value
        and minutes_since is not None
        and minutes_since < 360
        and not material_changed
    )
    return (
        AnalysisSignals(
            morning_due=morning,
            evening_due=evening,
            portfolio_changed=portfolio_changed,
            cash_changed=cash_changed,
            critical_risk=(critical and bool(profile["notify_critical"]) and not recent_same_risk),
            market_regime_changed=False,
            data_recovered=previous_row is not None and previous_row["status"] != "ready",
            digest_changed=material_changed,
            minutes_since_last_analysis=minutes_since,
        ),
        risk_message,
    )


def _context(
    snapshot: Mapping[str, Any],
    profile: Mapping[str, Any],
    now: datetime,
    risk_message: str | None,
) -> dict[str, Any]:
    as_of = now.astimezone(UTC).isoformat()
    source_id = f"tinvest:portfolio:{int(now.timestamp())}"
    credit_sources = list({ref["id"]: {**ref, "as_of": ref["observed_at"], "fresh": datetime.fromisoformat(ref["expires_at"]) > now}
                           for item in snapshot.get("_volume_verified_credit", []) for ref in item.get("sources", [])}.values())
    return {
        "portfolio": snapshot,
        "profile": dict(profile),
        "computed": {
            "allocation_percent": _allocation_map(snapshot),
            "risk_message": risk_message,
        },
        "sources": [
            {
                "id": source_id,
                "provider": "T-Invest API",
                "as_of": as_of,
                "fresh": True,
            }
        ] + credit_sources,
    }


def _fallback_report(
    decision: AnalysisDecision,
    snapshot: Mapping[str, Any],
    profile: Mapping[str, Any],
    now: datetime,
    risk_message: str | None,
) -> AnalysisReport | None:
    if not decision.notify_user:
        return None
    allocations = _allocation_map(snapshot)
    total = _money_value(snapshot.get("totalValue"))
    currency = str((snapshot.get("totalValue") or {}).get("currency") or "RUB")
    top = max(allocations.items(), key=lambda item: item[1]) if allocations else None
    as_of = now.astimezone(UTC).isoformat()
    evidence_fact = f"Стоимость портфеля: {total:,.2f} {currency}".replace(",", " ")

    if decision.reason is AnalysisReason.RISK_EVENT:
        title = "Нужна проверка риска портфеля"
        summary = risk_message or "Алгоритмический контроль обнаружил превышение порога риска."
        severity = "critical"
        actions = (
            "Проверьте подтверждённые лимиты и первичные источники риска в досье.",
            "Не принимайте решение только по одному предупреждению — проверьте актуальность данных.",
        )
    elif decision.reason is AnalysisReason.PORTFOLIO_CHANGED:
        title = "Состав портфеля изменился"
        summary = "Analyst AI зафиксировал покупку, продажу или изменение количества активов и пересчитал структуру."
        severity = "watch"
        actions = ("Проверьте новую концентрацию и валютное распределение.",)
    elif decision.reason is AnalysisReason.CASH_CHANGED:
        title = "Изменился свободный денежный остаток"
        summary = "Система обновила данные о денежных позициях и подготовила структуру для следующего анализа."
        severity = "info"
        actions = ("Откройте «Что купить», чтобы увидеть только алгоритмически допустимые направления.",)
    elif decision.reason is AnalysisReason.EVENING_BRIEF:
        title = "Вечерний контроль портфеля завершён"
        summary = "Портфель и основные ограничения риска проверены по актуальному снимку T-Invest."
        severity = "info"
        actions = ("Сравните результат с утренним состоянием перед следующей торговой сессией.",)
    else:
        title = "Утренний контроль портфеля завершён"
        summary = "Analyst AI обновил портфель и проверил структуру до начала активных решений."
        severity = "info"
        actions = ("Учитывайте горизонт и профиль риска перед изменением состава портфеля.",)

    if top is not None:
        evidence_fact += f"; крупнейший класс — {top[0]} ({top[1]:.1f}%)"
    evidence = [AnalysisEvidence(fact=evidence_fact, source_id=f"tinvest:portfolio:{int(now.timestamp())}", as_of=as_of)]
    for item in snapshot.get("_volume_verified_credit", []):
        for row in item.get("data", {}).get("items", []):
            evidence.append(AnalysisEvidence(fact=f"{row['agency']}: {row['grade']}; объект {row['subject_kind']}; прогноз {row['outlook']}",
                source_id=row["source"]["id"], as_of=row["source"]["checked_at"]))
    return AnalysisReport(
        severity=severity,
        headline=title,
        summary=summary,
        actions=actions,
        evidence=tuple(evidence),
        uncertainties=(
            "Расширенный модельный комментарий недоступен; показан детерминированный вывод алгоритмов.",
        ),
        valid_until=None,
    )


def _record_run(
    *,
    user_id: int,
    decision: AnalysisDecision,
    digest: str,
    state: str,
    model: str | None,
    usage: Any,
    error_code: str | None,
    now: datetime,
) -> str:
    run_id = str(uuid.uuid4())
    with closing(backend.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        assert_current_owner_in(db)
        assert_monitoring_access_in(db)
        db.execute(
            """
            INSERT INTO analysis_runs(
                id, user_id, reason, tier, digest, state, model,
                prompt_tokens, completion_tokens, total_tokens, error_code, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                user_id,
                decision.reason.value,
                decision.tier.value,
                digest,
                state,
                model,
                int(getattr(usage, "prompt_tokens", 0) or 0),
                int(getattr(usage, "completion_tokens", 0) or 0),
                int(getattr(usage, "total_tokens", 0) or 0),
                error_code,
                int(now.timestamp()),
            ),
        )
        db.commit()
    return run_id


def _insert_card(
    *,
    user_id: int,
    report: AnalysisReport,
    decision: AnalysisDecision,
    now: datetime,
    source_id: str,
) -> str:
    card_id = str(uuid.uuid4())
    kind = "risk" if report.severity in {"warning", "critical"} else (
        "brief" if decision.reason in {AnalysisReason.MORNING_BRIEF, AnalysisReason.EVENING_BRIEF} else "portfolio"
    )
    evidence = [asdict(item) for item in report.evidence]
    if not evidence:
        evidence = [
            {
                "fact": "Вывод рассчитан алгоритмами Analyst AI по снимку портфеля.",
                "source_id": source_id,
                "as_of": now.astimezone(UTC).isoformat(),
            }
        ]
    with closing(backend.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        assert_current_owner_in(db)
        assert_monitoring_access_in(db)
        db.execute(
            """
            INSERT INTO insight_cards(
                id, user_id, kind, severity, title, summary, actions_json,
                evidence_json, uncertainties_json, valid_until, is_read, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                card_id,
                user_id,
                kind,
                report.severity,
                report.headline,
                report.summary,
                json.dumps(list(report.actions), ensure_ascii=False),
                json.dumps(evidence, ensure_ascii=False),
                json.dumps(list(report.uncertainties), ensure_ascii=False),
                report.valid_until,
                int(now.timestamp()),
            ),
        )
        db.execute(
            """
            DELETE FROM insight_cards
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM insight_cards
                WHERE user_id = ? ORDER BY created_at DESC LIMIT 200
            )
            """,
            (user_id, user_id),
        )
        try:
            from .volume_notifications import enqueue_in
            from .volume_analysis import capture_in
        except ImportError:
            from volume_notifications import enqueue_in
            from volume_analysis import capture_in
        enqueue_in(db, user_id, kind=kind, title=report.headline, body=report.summary,
                   source_card_id=card_id, at=int(now.timestamp()))
        capture_in(db, user_id, card_id)
        db.commit()
    return card_id


def run_user_analysis(
    user_id: int,
    *,
    force: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    init_autonomous_db()
    current_time = now or datetime.now(UTC)
    with closing(backend.connect()) as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="analysis_user_not_found")
    if user["tinvest_token_encrypted"] is None:
        raise HTTPException(status_code=409, detail="tinvest_not_connected")

    with monitoring_connection(user_id, user["tinvest_token_encrypted"]):
        return _run_connected_analysis(user_id, user, current_time, force)


def _run_connected_analysis(
    user_id: int, user: sqlite3.Row, current_time: datetime, force: bool,
) -> dict[str, Any]:
    # Android readiness gates interactive API access, never server monitoring.
    assert_monitoring_access(backend.connect)
    previous, previous_row = _latest_snapshot(user_id)
    try:
        snapshot = get_tinvest_portfolio(currency="RUB", user=user)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Autonomous portfolio collection failed for user %s", user_id)
        raise HTTPException(status_code=503, detail="analysis_portfolio_unavailable") from None

    assert_monitoring_access(backend.connect)
    current_job = CURRENT_JOB.get()
    if current_job:
        AnalysisQueue(backend.connect).assert_owner(*current_job)
    # Archive the already fetched RUB valuation even when no LLM analysis is needed.
    try:
        from .portfolio_details import record_history
    except ImportError:
        from portfolio_details import record_history
    record_history(user_id, snapshot.get("accounts", []), current_time.astimezone(UTC).isoformat())
    try:
        from .volume_monitor import ingest, record_check, trigger_evidence
    except ImportError:
        from volume_monitor import ingest, record_check, trigger_evidence
    workspace_observation = ingest(user, snapshot, current_time)
    snapshot = {**snapshot, "_volume_risk_fingerprint": workspace_observation["risk_fingerprint"],
                "_volume_news_fingerprint": workspace_observation["news_fingerprint"],
                "_volume_critical_risk": workspace_observation["critical_risk"],
                "_volume_risk_message": workspace_observation["risk_message"],
                "_volume_verified_credit": workspace_observation["credit_evidence"],
                "_volume_credit_coverage": workspace_observation["credit_coverage"]}
    digest, material_digest = _save_snapshot(user_id, snapshot)
    profile = get_profile(user_id)
    signals, risk_message = _signals(
        user_id=user_id,
        snapshot=snapshot,
        previous=previous,
        previous_row=previous_row,
        material_digest=material_digest,
        profile=profile,
        now=current_time,
        force=force,
    )
    budget = _budget(user_id, current_time)
    decision = decide_analysis(signals, budget)
    trigger = trigger_evidence(user, snapshot, previous, previous_row, workspace_observation, signals, current_time)
    if decision.tier is AnalysisTier.NONE and signals.critical_risk:
        # Safety messages do not depend on a paid-model quota.
        decision = AnalysisDecision(AnalysisTier.NONE, AnalysisReason.RISK_EVENT, True, 0)
    elif decision.tier is AnalysisTier.NONE:
        record_check(user_id, current_time, status="skipped", reason=decision.reason.value, tier=decision.tier.value, trigger=trigger)
        return {
            "state": "skipped",
            "reason": decision.reason.value,
            "tier": decision.tier.value,
            "card_id": None,
        }

    record_check(user_id, current_time, status="analysis_required", reason=decision.reason.value, tier=decision.tier.value, trigger=trigger)
    context = _context(snapshot, profile, current_time, risk_message)
    source_id = context["sources"][0]["id"]
    report: AnalysisReport | None = None
    model = None
    usage = None
    state = "fallback"
    error_code = None
    try:
        if decision.tier is AnalysisTier.NONE:
            raise TimewebAIConfigurationError("analysis_budget_exhausted")
        # Missing credentials are free; uncertain network failures are not retried
        # for free. Reservation is never rolled back after a model attempt.
        assert_monitoring_access(backend.connect)
        guarded_client = GuardedAIClient(user_id, backend.connect)
        guarded_client.check_ready(decision.tier)
        if not _reserve_budget(user_id, current_time, decision.tier):
            raise TimewebAIConfigurationError("analysis_budget_exhausted")
        result = analyze_if_needed(
            signals=signals,
            budget=budget,
            context=context,
            client=guarded_client,
        )
        decision = result.decision
        report = result.report
        model = result.model
        usage = result.usage
        state = "completed"
    except (TimewebAIError, GuardError, BudgetDenied) as exc:
        error_code = getattr(exc, "code", str(exc))
        report = _fallback_report(decision, snapshot, profile, current_time, risk_message)
    except Exception as exc:
        logger.exception("AI analysis failed safely for user %s", user_id)
        error_code = type(exc).__name__
        report = _fallback_report(decision, snapshot, profile, current_time, risk_message)

    if current_job:
        AnalysisQueue(backend.connect).assert_owner(*current_job)
    assert_monitoring_access(backend.connect)
    run_id = _record_run(
        user_id=user_id,
        decision=decision,
        digest=digest,
        state=state,
        model=model,
        usage=usage,
        error_code=error_code,
        now=current_time,
    )
    card_id = None
    if report is not None and decision.notify_user:
        card_id = _insert_card(
            user_id=user_id,
            report=report,
            decision=decision,
            now=current_time,
            source_id=source_id,
        )
    record_check(user_id, current_time, status=state, reason=decision.reason.value, tier=decision.tier.value,
                 card_id=card_id, run_id=run_id, error_code=error_code, trigger=trigger)
    return {
        "state": state,
        "reason": decision.reason.value,
        "tier": decision.tier.value,
        "model": model,
        "card_id": card_id,
        "error_code": error_code,
    }


def _acquire_lease(name: str, ttl_seconds: int) -> bool:
    now = int(time.time())
    expires = now + ttl_seconds
    with closing(backend.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT owner, expires_at FROM scheduler_leases WHERE name = ?",
            (name,),
        ).fetchone()
        if row is not None and int(row["expires_at"]) > now and row["owner"] != _scheduler_owner:
            db.rollback()
            return False
        db.execute(
            """
            INSERT INTO scheduler_leases(name, owner, expires_at) VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET owner = excluded.owner, expires_at = excluded.expires_at
            """,
            (name, _scheduler_owner, expires),
        )
        db.commit()
    return True


def run_scheduler_cycle() -> dict[str, int]:
    init_autonomous_db()
    queue = AnalysisQueue(backend.connect)
    with closing(backend.connect()) as db:
        users = db.execute("SELECT id FROM users WHERE tinvest_token_encrypted IS NOT NULL ORDER BY id").fetchall()
    for user in users:
        queue.enqueue(int(user['id']))
    try:
        from .volume_jobs import drain as drain_workspace
    except ImportError:
        from volume_jobs import drain as drain_workspace
    drain_workspace(limit=5)
    return drain(queue, run_user_analysis)


async def _scheduler_loop() -> None:
    await asyncio.sleep(10)
    while True:
        try:
            await asyncio.to_thread(run_scheduler_cycle)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Autonomous analysis scheduler cycle failed")
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)


def start_scheduler() -> asyncio.Task[None] | None:
    global _scheduler_task
    init_autonomous_db()
    if not SCHEDULER_ENABLED:
        return None
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop(), name="analyst-ai-scheduler")
    return _scheduler_task


async def stop_scheduler(task: asyncio.Task[None] | None = None) -> None:
    global _scheduler_task
    target = task or _scheduler_task
    if target is None:
        return
    target.cancel()
    try:
        # wait() observes the child's cancellation without swallowing cancellation
        # of the caller (for example, a server shutdown deadline).
        await asyncio.wait({target})
        if not target.cancelled():
            target.result()
    finally:
        if target is _scheduler_task and target.done():
            _scheduler_task = None


def _card_payload(row: sqlite3.Row) -> dict[str, Any]:
    def load(key: str) -> Any:
        try:
            return json.loads(row[key])
        except (TypeError, ValueError):
            return []

    return {
        "id": row["id"],
        "kind": row["kind"],
        "severity": row["severity"],
        "title": row["title"],
        "summary": row["summary"],
        "actions": load("actions_json"),
        "evidence": load("evidence_json"),
        "uncertainties": load("uncertainties_json"),
        "valid_until": row["valid_until"],
        "is_read": bool(row["is_read"]),
        "created_at": datetime.fromtimestamp(int(row["created_at"]), UTC).isoformat(),
    }


@router.get("/profile")
def read_profile(user: sqlite3.Row = Depends(backend.current_user)) -> dict[str, Any]:
    return get_profile(int(user["id"]))


@router.put("/profile", responses={409: {"description": "Confirmed strategy rules require a fresh preview and explicit confirmation."}})
def update_profile(
    payload: ProfileUpdate,
    user: sqlite3.Row = Depends(backend.current_user),
) -> dict[str, Any]:
    try:
        from .volume_state import active_strategy
    except ImportError:
        from volume_state import active_strategy
    active = active_strategy(int(user["id"]))
    if active is not None:
        current = get_profile(int(user["id"]))
        if any(getattr(payload, key) != current[key] for key in
               ("risk_level", "horizon", "max_position_percent", "min_cash_percent")) or sorted(payload.allowed_markets) != sorted(current["allowed_markets"]):
            raise HTTPException(status_code=409, detail="strategy_preview_confirmation_required")
    markets = []
    for raw in payload.allowed_markets:
        value = raw.strip().upper()
        if value and value not in markets:
            markets.append(value[:12])
    if not markets:
        raise HTTPException(status_code=400, detail="analysis_markets_empty")
    now = int(time.time())
    with closing(backend.connect()) as db:
        db.execute(
            """
            INSERT INTO analysis_profiles(
                user_id, risk_level, horizon, allowed_markets_json,
                max_position_percent, min_cash_percent, notify_critical,
                notify_briefs, configured, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                risk_level = excluded.risk_level,
                horizon = excluded.horizon,
                allowed_markets_json = excluded.allowed_markets_json,
                max_position_percent = excluded.max_position_percent,
                min_cash_percent = excluded.min_cash_percent,
                notify_critical = excluded.notify_critical,
                notify_briefs = excluded.notify_briefs,
                configured = 1,
                updated_at = excluded.updated_at
            """,
            (
                int(user["id"]),
                payload.risk_level,
                payload.horizon,
                json.dumps(markets, ensure_ascii=False),
                payload.max_position_percent,
                payload.min_cash_percent,
                int(payload.notify_critical),
                int(payload.notify_briefs),
                now,
            ),
        )
        try:
            from .volume_notifications import sync_legacy_preferences_in
        except ImportError:
            from volume_notifications import sync_legacy_preferences_in
        sync_legacy_preferences_in(db, int(user["id"]), critical=payload.notify_critical, briefs=payload.notify_briefs, now=now)
        db.commit()
    return get_profile(int(user["id"]))


@router.get("/feed")
def feed(
    limit: int = Query(default=40, ge=1, le=MAX_FEED_LIMIT),
    user: sqlite3.Row = Depends(backend.current_user),
) -> dict[str, Any]:
    with closing(backend.connect()) as db:
        rows = db.execute(
            "SELECT * FROM insight_cards WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (int(user["id"]), limit),
        ).fetchall()
        unread = db.execute(
            "SELECT COUNT(*) AS count FROM insight_cards WHERE user_id = ? AND is_read = 0",
            (int(user["id"]),),
        ).fetchone()
    return {
        "unread_count": int(unread["count"] if unread else 0),
        "cards": [_card_payload(row) for row in rows],
    }


@router.get("/pulse")
def pulse(
    limit: int = Query(default=30, ge=1, le=MAX_FEED_LIMIT),
    user: sqlite3.Row = Depends(backend.current_user),
) -> dict[str, Any]:
    with closing(backend.connect()) as db:
        rows = db.execute(
            """
            SELECT * FROM insight_cards
            WHERE user_id = ? AND kind IN ('risk', 'brief', 'portfolio')
            ORDER BY created_at DESC LIMIT ?
            """,
            (int(user["id"]), limit),
        ).fetchall()
    return {"cards": [_card_payload(row) for row in rows]}


@router.post("/cards/{card_id}/read")
def mark_card_read(
    card_id: str,
    user: sqlite3.Row = Depends(backend.current_user),
) -> dict[str, bool]:
    with closing(backend.connect()) as db:
        cursor = db.execute(
            "UPDATE insight_cards SET is_read = 1 WHERE id = ? AND user_id = ?",
            (card_id, int(user["id"])),
        )
        changed = cursor.rowcount
        db.commit()
    if changed == 0:
        raise HTTPException(status_code=404, detail="analysis_card_not_found")
    return {"read": True}


@router.post("/refresh", status_code=202)
def refresh(
    _: RefreshRequest,
    user: sqlite3.Row = Depends(backend.current_user),
) -> dict[str, Any]:
    if not SCHEDULER_ENABLED:
        raise HTTPException(status_code=503, detail="analysis_scheduler_disabled")
    if user['tinvest_token_encrypted'] is None:
        raise HTTPException(status_code=409, detail="tinvest_not_connected")
    queue = AnalysisQueue(backend.connect)
    queue.initialize()
    return {**queue.enqueue(int(user['id'])), 'reason': 'queued_recheck',
            'tier': 'none', 'card_id': None, 'model': None, 'error_code': None}


def monitoring_status(user: sqlite3.Row, queue_status: Mapping[str, Any]) -> dict[str, Any]:
    """Report observed collection freshness, not a promise of portfolio safety."""
    user_id = int(user["id"])
    with closing(backend.connect()) as db:
        last = db.execute(
            "SELECT MAX(created_at) FROM portfolio_snapshots WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    now = int(time.time())
    last_at = int(last) if last is not None and int(last) <= now else None
    if user["tinvest_token_encrypted"] is None:
        state = "not_connected"
    elif not SCHEDULER_ENABLED:
        state = "disabled"
    elif queue_status.get("state") in {"failed", "uncertain"}:
        state = "check_failed"
    elif last_at is None:
        state = "waiting"
    elif now - last_at > max(120, 2 * SCHEDULER_INTERVAL_SECONDS):
        state = "delayed"
    else:
        state = "current"
    return {
        "state": state,
        "last_snapshot_at": (
            datetime.fromtimestamp(last_at, UTC).isoformat() if last_at is not None else None
        ),
        "independent_of_android_session": True,
    }


@router.get("/status")
def status(user: sqlite3.Row = Depends(backend.current_user)) -> dict[str, Any]:
    user_id = int(user["id"])
    with closing(backend.connect()) as db:
        last = db.execute(
            "SELECT * FROM analysis_runs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        unread = db.execute(
            "SELECT COUNT(*) AS count FROM insight_cards WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()
    init_autonomous_db()
    readiness = []
    guarded = GuardedAIClient(user_id, backend.connect)
    for tier in (AnalysisTier.FAST, AnalysisTier.STANDARD, AnalysisTier.PREMIUM):
        try:
            guarded.check_ready(tier)
            readiness.append({'tier': tier.value, 'ready': True, 'reason': None})
        except (GuardError, BudgetDenied) as error:
            readiness.append({'tier': tier.value, 'ready': False, 'reason': str(error)})
    ai_configured = all(item['ready'] for item in readiness)
    queue_status = AnalysisQueue(backend.connect).user_status(user_id)
    return {
        "scheduler_enabled": SCHEDULER_ENABLED,
        "ai_configured": ai_configured,
        "route_readiness": readiness,
        "queue": queue_status,
        "monitoring": monitoring_status(user, queue_status),
        "spending": MoneyLedger(backend.connect).user_summary(user_id),
        "configuration_is_not_live_inference_proof": True,
        "deterministic_monitoring": True,
        "unread_count": int(unread["count"] if unread else 0),
        "profile_configured": bool(get_profile(user_id)["configured"]),
        "last_run": None if last is None else {
            "state": last["state"],
            "reason": last["reason"],
            "tier": last["tier"],
            "model": last["model"],
            "error_code": last["error_code"],
            "created_at": datetime.fromtimestamp(int(last["created_at"]), UTC).isoformat(),
        },
    }


@router.get("/ideas")
def ideas(user: sqlite3.Row = Depends(backend.current_user)) -> dict[str, Any]:
    user_id = int(user["id"])
    profile = get_profile(user_id)
    snapshot, _ = _latest_snapshot(user_id)
    if snapshot is None:
        return {
            "state": "portfolio_required",
            "message": "Сначала обновите портфель T-Invest.",
            "ideas": [],
        }
    if not profile["configured"]:
        return {
            "state": "profile_required",
            "message": "Заполните профиль риска, чтобы система рассчитала допустимые направления.",
            "ideas": [],
        }

    current = _allocation_map(snapshot)
    target = TARGET_ALLOCATIONS[profile["risk_level"]]
    cash_share = current.get("Валюта и деньги", 0.0)
    investable = max(0.0, cash_share - float(profile["min_cash_percent"]))
    if investable < 1.0:
        return {
            "state": "no_excess_cash",
            "message": "Свободные деньги не превышают установленный резерв.",
            "cash_share_percent": cash_share,
            "ideas": [],
        }

    gaps = []
    for asset_class, target_share in target.items():
        if asset_class == "Валюта и деньги":
            continue
        current_share = current.get(asset_class, 0.0)
        gap = max(0.0, target_share - current_share)
        if gap >= 1.0:
            gaps.append(
                {
                    "asset_class": asset_class,
                    "current_percent": round(current_share, 1),
                    "target_percent": round(target_share, 1),
                    "gap_percent": round(gap, 1),
                    "suggested_max_percent": round(min(gap, investable), 1),
                    "explanation": "Алгоритмическое направление для восстановления целевой диверсификации; конкретный инструмент ещё должен пройти проверку источников, ликвидности и ограничений.",
                }
            )
    gaps.sort(key=lambda item: item["gap_percent"], reverse=True)
    remaining = math.floor(investable * 10.0) / 10.0
    bounded_gaps = []
    for idea in gaps[:4]:
        suggested = min(float(idea["gap_percent"]), remaining)
        suggested = math.floor(suggested * 10.0) / 10.0
        if suggested <= 0:
            continue
        idea["suggested_max_percent"] = suggested
        bounded_gaps.append(idea)
        remaining = max(0.0, remaining - suggested)
    gaps = bounded_gaps
    return {
        "state": "ready" if gaps else "balanced",
        "message": "Показаны классы активов, а не торговые команды и не обещание доходности.",
        "cash_share_percent": round(cash_share, 1),
        "reserve_percent": float(profile["min_cash_percent"]),
        "ideas": gaps[:4],
    }
