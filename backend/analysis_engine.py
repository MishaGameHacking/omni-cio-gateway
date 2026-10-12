"""Rules-first investment analysis orchestration.

Only structured, already-verified facts reach the model. The deterministic gate
in :mod:`ai_policy` decides whether a call is justified and which cost tier may
be used. This module intentionally exposes no free-form user prompt endpoint.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

try:
    from .ai_policy import (
        AnalysisBudget,
        AnalysisDecision,
        AnalysisReason,
        AnalysisSignals,
        AnalysisTier,
        decide_analysis,
    )
    from .timeweb_ai import TimewebAIClient, TimewebAIUsage
except ImportError:  # pragma: no cover - uvicorn top-level import compatibility
    from ai_policy import (  # type: ignore[no-redef]
        AnalysisBudget,
        AnalysisDecision,
        AnalysisReason,
        AnalysisSignals,
        AnalysisTier,
        decide_analysis,
    )
    from timeweb_ai import TimewebAIClient, TimewebAIUsage  # type: ignore[no-redef]

MAX_CONTEXT_BYTES = 96_000
MAX_HEADLINE_CHARS = 140
MAX_SUMMARY_CHARS = 2_000
MAX_ACTIONS = 5
MAX_EVIDENCE = 12
MAX_UNCERTAINTIES = 6
ALLOWED_SEVERITIES = {"info", "watch", "warning", "critical"}

SYSTEM_PROMPT = """Ты — серверный аналитический компонент Analyst AI, а не чат.
Работай только с фактами из переданного JSON. Не придумывай котировки, события,
доходности, причины движения цены или свойства активов. Не обещай доходность и
не выдавай торговое действие за обязательное. Если данных недостаточно, явно
укажи это в uncertainties. Сначала оцени влияние на конкретный портфель, затем
предложи не более пяти проверяемых действий или наблюдений.

Верни только один JSON-объект без Markdown строго по схеме:
{
  "severity": "info|watch|warning|critical",
  "headline": "короткий заголовок",
  "summary": "краткое объяснение на русском",
  "actions": ["действие или наблюдение"],
  "evidence": [
    {"fact": "проверяемый факт", "source_id": "id источника", "as_of": "время"}
  ],
  "uncertainties": ["что неизвестно или требует перепроверки"],
  "valid_until": "ISO-8601 или null"
}
"""


class AnalysisValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AnalysisEvidence:
    fact: str
    source_id: str
    as_of: str


@dataclass(frozen=True)
class AnalysisReport:
    severity: str
    headline: str
    summary: str
    actions: tuple[str, ...]
    evidence: tuple[AnalysisEvidence, ...]
    uncertainties: tuple[str, ...]
    valid_until: str | None


@dataclass(frozen=True)
class AnalysisRunResult:
    decision: AnalysisDecision
    input_digest: str
    report: AnalysisReport | None
    model: str | None
    usage: TimewebAIUsage | None


def analyze_if_needed(
    *,
    signals: AnalysisSignals,
    budget: AnalysisBudget,
    context: Mapping[str, Any],
    client: TimewebAIClient | None = None,
) -> AnalysisRunResult:
    """Run the cheapest justified model, or return without spending tokens."""
    canonical_context = _canonical_context(context)
    digest = hashlib.sha256(canonical_context.encode("utf-8")).hexdigest()
    decision = decide_analysis(signals, budget)
    if decision.tier is AnalysisTier.NONE:
        return AnalysisRunResult(
            decision=decision,
            input_digest=digest,
            report=None,
            model=None,
            usage=None,
        )

    gateway = client or TimewebAIClient()
    request_payload = {
        "analysis_reason": decision.reason.value,
        "notify_user": decision.notify_user,
        "context": json.loads(canonical_context),
    }
    result = gateway.complete_json(
        tier=decision.tier,
        max_output_tokens=decision.max_output_tokens,
        messages=(
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    request_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            },
        ),
    )
    report = _validate_report(result.data)
    if decision.reason is AnalysisReason.RISK_EVENT and report.severity not in {
        "warning",
        "critical",
    }:
        report = AnalysisReport(
            severity="critical" if signals.critical_risk else "warning",
            headline=report.headline,
            summary=report.summary,
            actions=report.actions,
            evidence=report.evidence,
            uncertainties=report.uncertainties,
            valid_until=report.valid_until,
        )

    return AnalysisRunResult(
        decision=decision,
        input_digest=digest,
        report=report,
        model=result.model,
        usage=result.usage,
    )


def _canonical_context(context: Mapping[str, Any]) -> str:
    try:
        serialized = json.dumps(
            dict(context),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AnalysisValidationError("analysis_context_not_json_serializable") from exc
    if len(serialized.encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise AnalysisValidationError("analysis_context_too_large")
    return serialized


def _validate_report(payload: Mapping[str, Any]) -> AnalysisReport:
    severity = _required_text(payload, "severity", max_chars=16).lower()
    if severity not in ALLOWED_SEVERITIES:
        raise AnalysisValidationError("analysis_invalid_severity")

    headline = _required_text(payload, "headline", max_chars=MAX_HEADLINE_CHARS)
    summary = _required_text(payload, "summary", max_chars=MAX_SUMMARY_CHARS)
    actions = _string_list(
        payload.get("actions"),
        field="actions",
        max_items=MAX_ACTIONS,
        max_chars=500,
    )
    uncertainties = _string_list(
        payload.get("uncertainties"),
        field="uncertainties",
        max_items=MAX_UNCERTAINTIES,
        max_chars=500,
    )
    evidence = _evidence_list(payload.get("evidence"))

    valid_until_raw = payload.get("valid_until")
    if valid_until_raw is None:
        valid_until = None
    elif isinstance(valid_until_raw, str):
        valid_until = valid_until_raw.strip() or None
        if valid_until is not None and len(valid_until) > 64:
            raise AnalysisValidationError("analysis_valid_until_too_long")
    else:
        raise AnalysisValidationError("analysis_invalid_valid_until")

    return AnalysisReport(
        severity=severity,
        headline=headline,
        summary=summary,
        actions=actions,
        evidence=evidence,
        uncertainties=uncertainties,
        valid_until=valid_until,
    )


def _required_text(
    payload: Mapping[str, Any],
    key: str,
    *,
    max_chars: int,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AnalysisValidationError(f"analysis_missing_{key}")
    normalized = value.strip()
    if len(normalized) > max_chars:
        raise AnalysisValidationError(f"analysis_{key}_too_long")
    return normalized


def _string_list(
    value: Any,
    *,
    field: str,
    max_items: int,
    max_chars: int,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise AnalysisValidationError(f"analysis_invalid_{field}")
    if len(value) > max_items:
        raise AnalysisValidationError(f"analysis_too_many_{field}")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AnalysisValidationError(f"analysis_invalid_{field}_item")
        text = item.strip()
        if len(text) > max_chars:
            raise AnalysisValidationError(f"analysis_{field}_item_too_long")
        normalized.append(text)
    return tuple(normalized)


def _evidence_list(value: Any) -> tuple[AnalysisEvidence, ...]:
    if not isinstance(value, list):
        raise AnalysisValidationError("analysis_invalid_evidence")
    if len(value) > MAX_EVIDENCE:
        raise AnalysisValidationError("analysis_too_many_evidence_items")
    items: list[AnalysisEvidence] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise AnalysisValidationError("analysis_invalid_evidence_item")
        items.append(
            AnalysisEvidence(
                fact=_required_text(raw, "fact", max_chars=500),
                source_id=_required_text(raw, "source_id", max_chars=160),
                as_of=_required_text(raw, "as_of", max_chars=64),
            )
        )
    return tuple(items)
