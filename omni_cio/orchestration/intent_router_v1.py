from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Final


class IntentV1(StrEnum):
    EXACT_ACTION = "exact_action"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    PORTFOLIO_MANAGEMENT = "portfolio_management"
    RISK_REVIEW = "risk_review"
    RESEARCH = "research"
    CASH_ALLOCATION = "cash_allocation"
    PLAN_REVIEW = "plan_review"
    EXECUTION_REQUEST = "execution_request"
    MONITORING = "monitoring"
    ASSET_ANALYSIS = "asset_analysis"
    UNKNOWN = "unknown"


class RouteConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class StepKind(StrEnum):
    ACTION = "action"
    INTERNAL = "internal"
    OWNER_GATE = "owner_gate"


@dataclass(frozen=True, slots=True)
class WorkflowStepV1:
    step_id: str
    kind: StepKind
    operation_id: str | None = None
    required_work_package: str | None = None
    read_only: bool = True


@dataclass(frozen=True, slots=True)
class IntentRouteV1:
    schema_version: str
    intent: IntentV1
    workflow_id: str
    normalized_text: str
    confidence: RouteConfidence
    matched_signals: tuple[str, ...]
    steps: tuple[WorkflowStepV1, ...]
    exact_action: str | None
    clarification_required: bool
    clarification_reason: str | None
    requires_owner_confirmation: bool
    real_money_possible: bool
    write_intent_detected: bool


SCHEMA_VERSION: Final = "intent-route.v1"

BASELINE_READ_ONLY_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "gatewayHealth",
        "getConnection",
        "getPortfolioSnapshot",
        "getEnrichedPortfolioSnapshot",
        "findInstrument",
        "getOperationsHistory",
        "getMarketSnapshot",
        "getPortfolioMarketSnapshot",
        "getPortfolioAnalytics",
        "getCashLiquiditySnapshot",
        "getPurchaseCapacityPreview",
        "getOperationsAnalytics",
        "getBrokerReportReconciliation",
        "getFinalDecisionReview",
    }
)

SANDBOX_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "getSandboxTradingStatus",
        "openSandboxAccount",
        "fundSandboxAccount",
        "getSandboxPortfolio",
        "prepareSandboxTrade",
        "executeSandboxTrade",
        "getSandboxOrderState",
        "cancelSandboxOrder",
    }
)

REAL_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "getRealTradingStatus",
        "prepareRealTrade",
        "executeRealTrade",
        "getRealOrderState",
    }
)

SUPPORTED_ACTIONS: Final[frozenset[str]] = (
    BASELINE_READ_ONLY_ACTIONS | SANDBOX_ACTIONS | REAL_ACTIONS
)

CONSEQUENTIAL_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "openSandboxAccount",
        "fundSandboxAccount",
        "executeSandboxTrade",
        "cancelSandboxOrder",
        "executeRealTrade",
    }
)

_WRITE_PATTERNS: Final[tuple[str, ...]] = (
    "купи",
    "купить",
    "покупай",
    "продай",
    "продать",
    "продавай",
    "исполни",
    "исполняй",
    "выполни сделку",
    "соверши сделку",
    "подтверждаю реальную сделку",
    "подтверждаю сделку",
)

_TYPO_REPLACEMENTS: Final[tuple[tuple[str, str], ...]] = (
    ("партфел", "портфел"),
    ("партфел", "портфел"),
    ("деверсифик", "диверсифик"),
    ("диферсифик", "диверсифик"),
    ("анализируй партфель", "анализируй портфель"),
    ("управляй партфел", "управляй портфел"),
)

_INTENT_SIGNALS: Final[dict[IntentV1, tuple[tuple[str, int], ...]]] = {
    IntentV1.PORTFOLIO_MANAGEMENT: (
        ("управляй портфел", 9),
        ("управляй моими деньг", 9),
        ("управление портфел", 7),
        ("ребаланс", 7),
        ("диверсифик", 6),
        ("распредели портфел", 7),
        ("что делать с портфел", 6),
        ("сделай портфель лучше", 6),
    ),
    IntentV1.PORTFOLIO_ANALYSIS: (
        ("проанализируй портфел", 8),
        ("анализ портфел", 7),
        ("состояние портфел", 6),
        ("что с портфел", 5),
        ("как мой портфел", 5),
        ("проверь портфел", 5),
    ),
    IntentV1.RISK_REVIEW: (
        ("риск", 4),
        ("дефолт", 5),
        ("банкрот", 5),
        ("просад", 4),
        ("концентрац", 4),
        ("опасн", 4),
        ("кредитн", 3),
        ("надежност", 3),
    ),
    IntentV1.RESEARCH: (
        ("исследуй", 5),
        ("изучи", 4),
        ("сравни", 4),
        ("найди", 3),
        ("новост", 3),
        ("рейтинг", 4),
        ("кандидат", 4),
        ("рынок", 2),
        ("лучшие облигац", 5),
        ("лучшие акци", 5),
        ("перспективн", 3),
    ),
    IntentV1.CASH_ALLOCATION: (
        ("куда вложить", 8),
        ("куда инвестировать", 8),
        ("распредели деньги", 8),
        ("распредели свободн", 7),
        ("свободные деньги", 5),
        ("свободных денег", 5),
        ("что купить на", 7),
        ("есть деньги", 4),
        ("есть рублей", 4),
        ("есть рубл", 4),
        ("пополн", 2),
    ),
    IntentV1.PLAN_REVIEW: (
        ("покажи план", 8),
        ("объясни план", 8),
        ("проверь план", 8),
        ("пересмотри план", 8),
        ("что собираешься сделать", 7),
        ("план действий", 5),
    ),
    IntentV1.MONITORING: (
        ("следи за", 8),
        ("монитор", 8),
        ("наблюдай", 7),
        ("сообщай если", 8),
        ("сообщи когда", 8),
        ("каждый день", 5),
        ("каждое утро", 5),
        ("регулярно", 5),
        ("постоянно провер", 6),
    ),
    IntentV1.ASSET_ANALYSIS: (
        ("проанализируй акц", 7),
        ("проанализируй облигац", 7),
        ("проанализируй фонд", 7),
        ("анализ акц", 6),
        ("анализ облигац", 6),
        ("анализ фонда", 6),
        ("что думаешь о", 5),
        ("разбери фонд", 7),
        ("разбери компанию", 7),
    ),
}

_EXECUTION_SIGNALS: Final[tuple[tuple[str, int], ...]] = tuple(
    (pattern, 10) for pattern in _WRITE_PATTERNS
)

_INTENT_PRIORITY: Final[tuple[IntentV1, ...]] = (
    IntentV1.EXECUTION_REQUEST,
    IntentV1.PORTFOLIO_MANAGEMENT,
    IntentV1.CASH_ALLOCATION,
    IntentV1.RISK_REVIEW,
    IntentV1.MONITORING,
    IntentV1.PLAN_REVIEW,
    IntentV1.RESEARCH,
    IntentV1.PORTFOLIO_ANALYSIS,
    IntentV1.ASSET_ANALYSIS,
)


def normalize_user_text(text: str) -> str:
    normalized = text.casefold().replace("ё", "е")
    normalized = re.sub(r"[^\w\s.-]+", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for typo, replacement in _TYPO_REPLACEMENTS:
        normalized = normalized.replace(typo, replacement)
    return normalized


def _action_lookup(
    available_actions: frozenset[str],
) -> dict[str, str]:
    return {action.casefold(): action for action in available_actions}


def _extract_exact_action(
    *,
    raw_text: str,
    normalized_text: str,
    available_actions: frozenset[str],
) -> tuple[bool, str | None, str | None]:
    exact_marker = any(
        marker in normalized_text
        for marker in (
            "вызови только",
            "вызвать только",
            "только action",
            "only action",
            "call only",
        )
    )
    if not exact_marker:
        return False, None, None

    lookup = _action_lookup(available_actions)
    raw_folded = raw_text.casefold()
    matches = tuple(
        sorted(
            {
                canonical
                for folded, canonical in lookup.items()
                if folded in raw_folded
            }
        )
    )
    if len(matches) == 1:
        return True, matches[0], None
    if len(matches) > 1:
        return True, None, "MULTIPLE_EXACT_ACTIONS_REQUESTED"

    probable = re.search(
        r"(?:вызови|вызвать|call)\s+только\s+([a-zA-Z][a-zA-Z0-9_]*)",
        raw_text,
        flags=re.IGNORECASE,
    )
    if probable:
        return True, None, f"UNKNOWN_EXACT_ACTION:{probable.group(1)}"
    return True, None, "EXACT_ACTION_NOT_IDENTIFIED"


def _contains_write_intent(normalized_text: str) -> bool:
    return any(pattern in normalized_text for pattern in _WRITE_PATTERNS)


def _score_signals(
    normalized_text: str,
) -> tuple[dict[IntentV1, int], dict[IntentV1, tuple[str, ...]]]:
    scores: dict[IntentV1, int] = {}
    signals: dict[IntentV1, tuple[str, ...]] = {}
    for intent, patterns in _INTENT_SIGNALS.items():
        matched = tuple(pattern for pattern, _ in patterns if pattern in normalized_text)
        scores[intent] = sum(
            weight for pattern, weight in patterns if pattern in normalized_text
        )
        signals[intent] = matched

    execution_matched = tuple(
        pattern for pattern, _ in _EXECUTION_SIGNALS if pattern in normalized_text
    )
    scores[IntentV1.EXECUTION_REQUEST] = sum(
        weight
        for pattern, weight in _EXECUTION_SIGNALS
        if pattern in normalized_text
    )
    signals[IntentV1.EXECUTION_REQUEST] = execution_matched
    return scores, signals


def _choose_intent(scores: dict[IntentV1, int]) -> IntentV1:
    highest = max(scores.values(), default=0)
    if highest <= 0:
        return IntentV1.UNKNOWN
    tied = {intent for intent, score in scores.items() if score == highest}
    for intent in _INTENT_PRIORITY:
        if intent in tied:
            return intent
    return IntentV1.UNKNOWN


def _confidence(score: int) -> RouteConfidence:
    if score >= 8:
        return RouteConfidence.HIGH
    if score >= 4:
        return RouteConfidence.MEDIUM
    return RouteConfidence.LOW


def _action(step_id: str, operation_id: str) -> WorkflowStepV1:
    return WorkflowStepV1(
        step_id=step_id,
        kind=StepKind.ACTION,
        operation_id=operation_id,
        read_only=True,
    )


def _internal(
    step_id: str,
    *,
    required_work_package: str | None = None,
) -> WorkflowStepV1:
    return WorkflowStepV1(
        step_id=step_id,
        kind=StepKind.INTERNAL,
        required_work_package=required_work_package,
        read_only=True,
    )


def _owner_gate(step_id: str) -> WorkflowStepV1:
    return WorkflowStepV1(
        step_id=step_id,
        kind=StepKind.OWNER_GATE,
        read_only=True,
    )


def _workflow_for(intent: IntentV1) -> tuple[str, tuple[WorkflowStepV1, ...]]:
    workflows: dict[IntentV1, tuple[str, tuple[WorkflowStepV1, ...]]] = {
        IntentV1.PORTFOLIO_ANALYSIS: (
            "portfolio_analysis.v1",
            (
                _action("portfolio", "getPortfolioSnapshot"),
                _action("cash", "getCashLiquiditySnapshot"),
                _action("analytics", "getPortfolioAnalytics"),
                _internal("explain_portfolio"),
            ),
        ),
        IntentV1.PORTFOLIO_MANAGEMENT: (
            "portfolio_management.v1",
            (
                _action("portfolio", "getPortfolioSnapshot"),
                _action("cash", "getCashLiquiditySnapshot"),
                _action("analytics", "getPortfolioAnalytics"),
                _internal("identify_structural_gaps"),
                _internal("compare_action_to_no_action"),
                _internal("build_portfolio_plan", required_work_package="WP11"),
                _owner_gate("owner_reviews_plan"),
            ),
        ),
        IntentV1.RISK_REVIEW: (
            "risk_review.v1",
            (
                _action("portfolio", "getPortfolioSnapshot"),
                _action("analytics", "getPortfolioAnalytics"),
                _action("market", "getPortfolioMarketSnapshot"),
                _internal("portfolio_risk_engine", required_work_package="WP8"),
                _internal("explain_risk"),
            ),
        ),
        IntentV1.RESEARCH: (
            "research.v1",
            (
                _internal("resolve_research_scope"),
                _internal("market_universe", required_work_package="WP3"),
                _internal("candidate_funnel", required_work_package="WP4"),
                _internal("evidence_research", required_work_package="WP5"),
                _internal("compare_candidates"),
            ),
        ),
        IntentV1.CASH_ALLOCATION: (
            "cash_allocation.v1",
            (
                _action("portfolio", "getPortfolioSnapshot"),
                _action("cash", "getCashLiquiditySnapshot"),
                _action("analytics", "getPortfolioAnalytics"),
                _internal("load_investment_policy", required_work_package="WP2"),
                _internal("market_universe", required_work_package="WP3"),
                _internal("candidate_funnel", required_work_package="WP4"),
                _internal("portfolio_optimizer", required_work_package="WP10"),
                _internal("build_portfolio_plan", required_work_package="WP11"),
                _owner_gate("owner_reviews_plan"),
            ),
        ),
        IntentV1.PLAN_REVIEW: (
            "plan_review.v1",
            (
                _action("decision_review", "getFinalDecisionReview"),
                _internal("load_portfolio_plan", required_work_package="WP11"),
                _internal("explain_plan"),
            ),
        ),
        IntentV1.EXECUTION_REQUEST: (
            "execution_request.v1",
            (
                _internal("resolve_or_build_safe_plan", required_work_package="WP11"),
                _internal("refresh_execution_preflight", required_work_package="WP12"),
                _owner_gate("exact_owner_confirmation"),
                _internal("execute_confirmed_plan_only", required_work_package="WP12"),
                _internal("broker_reconciliation", required_work_package="WP12"),
            ),
        ),
        IntentV1.MONITORING: (
            "monitoring.v1",
            (
                _action("portfolio", "getPortfolioSnapshot"),
                _action("analytics", "getPortfolioAnalytics"),
                _internal("watchtower_read_only", required_work_package="WP13"),
                _internal("notify_material_change_only", required_work_package="WP13"),
            ),
        ),
        IntentV1.ASSET_ANALYSIS: (
            "asset_analysis.v1",
            (
                _action("resolve_instrument", "findInstrument"),
                _action("market", "getMarketSnapshot"),
                _internal("evidence_research", required_work_package="WP5"),
                _internal("explain_asset"),
            ),
        ),
        IntentV1.UNKNOWN: ("clarification.v1", ()),
    }
    return workflows[intent]


def route_user_intent(
    text: str,
    *,
    available_actions: frozenset[str] = SUPPORTED_ACTIONS,
) -> IntentRouteV1:
    if not text or not text.strip():
        return IntentRouteV1(
            schema_version=SCHEMA_VERSION,
            intent=IntentV1.UNKNOWN,
            workflow_id="clarification.v1",
            normalized_text="",
            confidence=RouteConfidence.LOW,
            matched_signals=(),
            steps=(),
            exact_action=None,
            clarification_required=True,
            clarification_reason="EMPTY_REQUEST",
            requires_owner_confirmation=False,
            real_money_possible=False,
            write_intent_detected=False,
        )

    normalized = normalize_user_text(text)
    exact_requested, exact_action, exact_error = _extract_exact_action(
        raw_text=text,
        normalized_text=normalized,
        available_actions=available_actions,
    )
    if exact_requested:
        if exact_action is None:
            return IntentRouteV1(
                schema_version=SCHEMA_VERSION,
                intent=IntentV1.EXACT_ACTION,
                workflow_id="exact_action.v1",
                normalized_text=normalized,
                confidence=RouteConfidence.HIGH,
                matched_signals=("exact_action_marker",),
                steps=(),
                exact_action=None,
                clarification_required=True,
                clarification_reason=exact_error,
                requires_owner_confirmation=False,
                real_money_possible=False,
                write_intent_detected=False,
            )

        consequential = exact_action in CONSEQUENTIAL_ACTIONS
        real_money = exact_action == "executeRealTrade"
        return IntentRouteV1(
            schema_version=SCHEMA_VERSION,
            intent=IntentV1.EXACT_ACTION,
            workflow_id="exact_action.v1",
            normalized_text=normalized,
            confidence=RouteConfidence.HIGH,
            matched_signals=("exact_action_marker", exact_action),
            steps=(
                WorkflowStepV1(
                    step_id="exact_action",
                    kind=StepKind.ACTION,
                    operation_id=exact_action,
                    read_only=not consequential,
                ),
            ),
            exact_action=exact_action,
            clarification_required=False,
            clarification_reason=None,
            requires_owner_confirmation=consequential,
            real_money_possible=real_money,
            write_intent_detected=consequential,
        )

    scores, signals = _score_signals(normalized)
    write_intent = _contains_write_intent(normalized)

    # A write request embedded inside a broader portfolio request is interpreted as
    # a request to build a safe plan, not as permission to submit broker mutations.
    management_score = scores.get(IntentV1.PORTFOLIO_MANAGEMENT, 0)
    cash_score = scores.get(IntentV1.CASH_ALLOCATION, 0)
    execution_score = scores.get(IntentV1.EXECUTION_REQUEST, 0)
    if write_intent and max(management_score, cash_score) >= 6:
        intent = (
            IntentV1.PORTFOLIO_MANAGEMENT
            if management_score >= cash_score
            else IntentV1.CASH_ALLOCATION
        )
        score = max(management_score, cash_score, execution_score)
        matched = tuple(
            dict.fromkeys(
                signals[intent] + signals[IntentV1.EXECUTION_REQUEST]
            )
        )
    else:
        intent = _choose_intent(scores)
        score = scores.get(intent, 0)
        matched = signals.get(intent, ())

    workflow_id, steps = _workflow_for(intent)
    if intent == IntentV1.UNKNOWN:
        return IntentRouteV1(
            schema_version=SCHEMA_VERSION,
            intent=intent,
            workflow_id=workflow_id,
            normalized_text=normalized,
            confidence=RouteConfidence.LOW,
            matched_signals=(),
            steps=steps,
            exact_action=None,
            clarification_required=True,
            clarification_reason="INTENT_NOT_CONFIDENTLY_RESOLVED",
            requires_owner_confirmation=False,
            real_money_possible=False,
            write_intent_detected=write_intent,
        )

    requires_confirmation = write_intent or intent in {
        IntentV1.PORTFOLIO_MANAGEMENT,
        IntentV1.CASH_ALLOCATION,
        IntentV1.EXECUTION_REQUEST,
    }
    real_money_possible = intent in {
        IntentV1.PORTFOLIO_MANAGEMENT,
        IntentV1.CASH_ALLOCATION,
        IntentV1.EXECUTION_REQUEST,
    }
    return IntentRouteV1(
        schema_version=SCHEMA_VERSION,
        intent=intent,
        workflow_id=workflow_id,
        normalized_text=normalized,
        confidence=_confidence(score),
        matched_signals=matched,
        steps=steps,
        exact_action=None,
        clarification_required=False,
        clarification_reason=None,
        requires_owner_confirmation=requires_confirmation,
        real_money_possible=real_money_possible,
        write_intent_detected=write_intent,
    )
