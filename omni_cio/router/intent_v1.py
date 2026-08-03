from __future__ import annotations

import re
import unicodedata

from omni_cio.contracts.v1.intent_router import (
    CioIntent,
    CioWorkflow,
    ExecutionContour,
    ExecutionDirection,
    ExecutionPhase,
    IntentRouteV1,
    RouterClarificationCode,
    RouterConfidence,
    RouterRequirement,
)


KNOWN_ACTIONS: tuple[str, ...] = (
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
    "getSandboxTradingStatus",
    "openSandboxAccount",
    "fundSandboxAccount",
    "getSandboxPortfolio",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "getSandboxOrderState",
    "cancelSandboxOrder",
    "getRealTradingStatus",
    "prepareRealTrade",
    "executeRealTrade",
    "getRealOrderState",
)

_REAL_ACTIONS = frozenset(
    {
        "getRealTradingStatus",
        "prepareRealTrade",
        "executeRealTrade",
        "getRealOrderState",
    }
)
_SANDBOX_ACTIONS = frozenset(
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
_CONSEQUENTIAL_ACTIONS = frozenset(
    {
        "openSandboxAccount",
        "fundSandboxAccount",
        "executeSandboxTrade",
        "cancelSandboxOrder",
        "executeRealTrade",
    }
)
_PREPARE_ACTIONS = frozenset({"prepareSandboxTrade", "prepareRealTrade"})
_EXECUTE_ACTIONS = frozenset({"executeSandboxTrade", "executeRealTrade"})

_INTENT_PRIORITY: tuple[CioIntent, ...] = (
    CioIntent.PORTFOLIO_MANAGEMENT,
    CioIntent.CASH_ALLOCATION,
    CioIntent.PLAN_REVIEW,
    CioIntent.MONITORING,
    CioIntent.RISK,
    CioIntent.RESEARCH,
    CioIntent.ANALYSIS,
)

_ANALYSIS_MARKERS = (
    "проанализируй портфел",
    "анализ портфел",
    "проверь портфел",
    "обнови портфел",
    "покажи портфел",
    "что с портфел",
    "как мой портфел",
    "что изменилось",
    "структура портфел",
    "баланс",
    "история операций",
    "операции за",
)
_MANAGEMENT_MARKERS = (
    "управляй портфел",
    "управлять портфел",
    "скажи что делать",
    "сделай портфел лучше",
    "подготовь лучший план",
    "лучший план на текущий капитал",
    "ребалансир",
    "диверсифик",
    "перестрой портфел",
)
_CASH_MARKERS = (
    "распредели свободн",
    "распредели деньги",
    "куда вложить",
    "куда инвестировать",
    "свободные деньги",
    "свободных денег",
    "что купить на ",
)
_RISK_MARKERS = (
    "проверь риск",
    "риски",
    "риск портфел",
    "опасность дефолта",
    "дефолт",
    "просад",
    "концентрац",
)
_RESEARCH_MARKERS = (
    "исследуй",
    "изучи актив",
    "изучи компанию",
    "разбери актив",
    "разбери компанию",
    "разбери фонд",
    "что думаешь про",
    "стоит ли купить",
    "стоит ли продать",
    "проанализируй актив",
    "проанализируй компанию",
    "проанализируй акц",
    "проанализируй облигац",
    "проанализируй фонд",
    "анализ акц",
    "анализ облигац",
    "анализ фонда",
    "найди лучшие",
    "сравни кандидат",
    "проверь новост",
)
_PLAN_MARKERS = (
    "проверь план",
    "покажи план",
    "объясни план",
    "оцени план",
    "пересмотри план",
    "review план",
)
_MONITORING_MARKERS = (
    "следи за",
    "монитор",
    "уведомляй",
    "отслеживай",
    "сообщи когда",
    "сообщай если",
)
_GATEWAY_DIAGNOSTIC_MARKERS = (
    "проверь шлюз",
    "проверить шлюз",
    "gateway health",
    "gatewayhealth",
    "шлюз работает",
)
_CONNECTION_DIAGNOSTIC_MARKERS = (
    "проверь подключение",
    "проверить подключение",
    "подключение к t-invest",
    "соединение с t-invest",
    "getconnection",
)
_OPERATIONS_MARKERS = ("операц", "что изменилось")

_EXACT_ACTION_CUES = (
    "вызови",
    "вызвать",
    "сначала",
    "затем",
    "потом",
    "только action",
    "only action",
    "call only",
)
_TYPO_REPLACEMENTS = (
    ("партфел", "портфел"),
    ("деверсифик", "диверсифик"),
    ("диферсифик", "диверсифик"),
)

_BUY_IMPERATIVE = re.compile(r"\b(?:купи|покупай|приобрети|возьми)\b")
_SELL_IMPERATIVE = re.compile(r"\b(?:продай|продавай)\b")
_EXECUTION_TERMS = (
    "соверши сделку",
    "исполнить сделку",
    "исполни сделку",
    "исполнить заявку",
    "исполни заявку",
    "отправь заявку",
    "исполняй план",
    "исполни план",
    "подготовь реальную сделку",
    "подготовь sandbox сделку",
    "подготовь сделку в песочнице",
)


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"[^\w\s./:-]+", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    for typo, replacement in _TYPO_REPLACEMENTS:
        value = value.replace(typo, replacement)
    return value


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _detect_exact_actions(raw_text: str, normalized_text: str) -> tuple[str, ...]:
    found: list[tuple[int, str]] = []
    for action in KNOWN_ACTIONS:
        match = re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(action)}(?![A-Za-z0-9_])",
            raw_text,
            flags=re.IGNORECASE,
        )
        if match is not None:
            found.append((match.start(), action))
    if not found:
        return ()

    starts_with_action = any(not raw_text[:position].strip() for position, _ in found)
    has_invocation_cue = _contains_any(normalized_text, _EXACT_ACTION_CUES)
    if not starts_with_action and not has_invocation_cue:
        return ()

    found.sort(key=lambda row: row[0])
    return tuple(action for _, action in found)


def _exact_action_route(actions: tuple[str, ...]) -> IntentRouteV1:
    has_real = any(action in _REAL_ACTIONS for action in actions)
    has_sandbox = any(action in _SANDBOX_ACTIONS for action in actions)
    if has_real and has_sandbox:
        contour = ExecutionContour.AMBIGUOUS
    elif has_real:
        contour = ExecutionContour.REAL
    elif has_sandbox:
        contour = ExecutionContour.SANDBOX
    else:
        contour = ExecutionContour.NONE

    if any(action in _EXECUTE_ACTIONS for action in actions):
        phase = ExecutionPhase.CONFIRMATION
    elif any(action in _PREPARE_ACTIONS for action in actions):
        phase = ExecutionPhase.REQUEST
    else:
        phase = ExecutionPhase.NONE

    return IntentRouteV1(
        primary_intent=CioIntent.EXACT_ACTION,
        workflow=CioWorkflow.EXACT_ACTION,
        confidence=RouterConfidence.HIGH,
        exact_actions=actions,
        exact_action_scope_locked=True,
        execution_contour=contour,
        execution_phase=phase,
        owner_confirmation_required_for_write=any(
            action in _CONSEQUENTIAL_ACTIONS for action in actions
        ),
    )


def _execution_contour(text: str) -> ExecutionContour:
    real = bool(re.search(r"\bреальн\w*\b|\bнастоящ\w*\b", text))
    sandbox = "sandbox" in text or "песочниц" in text or "виртуальн" in text
    if real and sandbox:
        return ExecutionContour.AMBIGUOUS
    if real:
        return ExecutionContour.REAL
    if sandbox:
        return ExecutionContour.SANDBOX
    return ExecutionContour.UNSPECIFIED


def _execution_direction(text: str, *, allow_nouns: bool) -> ExecutionDirection:
    buy = _BUY_IMPERATIVE.search(text) is not None
    sell = _SELL_IMPERATIVE.search(text) is not None
    if allow_nouns:
        buy = buy or "покупк" in text
        sell = sell or "продаж" in text
    if buy and sell:
        return ExecutionDirection.AMBIGUOUS
    if buy:
        return ExecutionDirection.BUY
    if sell:
        return ExecutionDirection.SELL
    return ExecutionDirection.NONE


def _confirmation_contour(text: str) -> ExecutionContour | None:
    if "подтверждаю" not in text:
        return None
    has_trade_subject = any(
        marker in text for marker in ("сделк", "заявк", "proposal", "операц")
    )
    if not has_trade_subject:
        return None
    contour = _execution_contour(text)
    if contour is ExecutionContour.UNSPECIFIED:
        return None
    return contour


def _clarification_for_execution(
    *,
    contour: ExecutionContour,
    direction: ExecutionDirection,
    phase: ExecutionPhase,
) -> RouterClarificationCode | None:
    if contour is ExecutionContour.AMBIGUOUS:
        return RouterClarificationCode.EXECUTION_CONTOUR_AMBIGUOUS
    if contour is ExecutionContour.UNSPECIFIED:
        return RouterClarificationCode.EXECUTION_CONTOUR_REQUIRED
    if phase is ExecutionPhase.CONFIRMATION:
        return None
    if direction is ExecutionDirection.AMBIGUOUS:
        return RouterClarificationCode.EXECUTION_DIRECTION_AMBIGUOUS
    if direction is ExecutionDirection.NONE:
        return RouterClarificationCode.EXECUTION_DIRECTION_REQUIRED
    return None


def _execution_requirements(contour: ExecutionContour) -> tuple[RouterRequirement, ...]:
    base = (RouterRequirement.INSTRUMENT_IDENTITY, RouterRequirement.FRESH_MARKET)
    if contour is ExecutionContour.REAL:
        return (RouterRequirement.REAL_TRADING_STATUS, *base)
    if contour is ExecutionContour.SANDBOX:
        return (RouterRequirement.SANDBOX_TRADING_STATUS, *base)
    return base


def _execution_route(text: str) -> IntentRouteV1 | None:
    confirmation_contour = _confirmation_contour(text)
    if confirmation_contour is not None:
        phase = ExecutionPhase.CONFIRMATION
        contour = confirmation_contour
        direction = ExecutionDirection.NONE
    else:
        buy_imperative = _BUY_IMPERATIVE.search(text) is not None
        sell_imperative = _SELL_IMPERATIVE.search(text) is not None
        execution_term = _contains_any(text, _EXECUTION_TERMS)
        if not (buy_imperative or sell_imperative or execution_term):
            return None
        phase = ExecutionPhase.REQUEST
        contour = _execution_contour(text)
        direction = _execution_direction(text, allow_nouns=execution_term)

    clarification = _clarification_for_execution(
        contour=contour,
        direction=direction,
        phase=phase,
    )
    return IntentRouteV1(
        primary_intent=CioIntent.EXECUTION,
        workflow=(
            CioWorkflow.EXECUTION_CONFIRMATION
            if phase is ExecutionPhase.CONFIRMATION
            else CioWorkflow.EXECUTION_REQUEST
        ),
        confidence=(
            RouterConfidence.HIGH if clarification is None else RouterConfidence.MEDIUM
        ),
        requirements=_execution_requirements(contour),
        clarification_required=clarification is not None,
        clarification_code=clarification,
        execution_contour=contour,
        execution_phase=phase,
        execution_direction=direction,
        owner_confirmation_required_for_write=True,
    )


def _diagnostic_route(text: str) -> IntentRouteV1 | None:
    if _contains_any(text, _GATEWAY_DIAGNOSTIC_MARKERS):
        return IntentRouteV1(
            primary_intent=CioIntent.DIAGNOSTIC,
            workflow=CioWorkflow.GATEWAY_DIAGNOSTIC,
            confidence=RouterConfidence.HIGH,
            requirements=(RouterRequirement.GATEWAY_HEALTH,),
        )
    if _contains_any(text, _CONNECTION_DIAGNOSTIC_MARKERS):
        return IntentRouteV1(
            primary_intent=CioIntent.DIAGNOSTIC,
            workflow=CioWorkflow.CONNECTION_DIAGNOSTIC,
            confidence=RouterConfidence.HIGH,
            requirements=(RouterRequirement.CONNECTION,),
        )
    return None


def _detected_intents(text: str) -> tuple[CioIntent, ...]:
    detected: list[CioIntent] = []
    checks = (
        (CioIntent.PORTFOLIO_MANAGEMENT, _MANAGEMENT_MARKERS),
        (CioIntent.CASH_ALLOCATION, _CASH_MARKERS),
        (CioIntent.PLAN_REVIEW, _PLAN_MARKERS),
        (CioIntent.MONITORING, _MONITORING_MARKERS),
        (CioIntent.RISK, _RISK_MARKERS),
        (CioIntent.RESEARCH, _RESEARCH_MARKERS),
        (CioIntent.ANALYSIS, _ANALYSIS_MARKERS),
    )
    for intent, markers in checks:
        if _contains_any(text, markers):
            detected.append(intent)
    return tuple(detected)


def _requirements_for(intent: CioIntent, text: str) -> tuple[RouterRequirement, ...]:
    if intent is CioIntent.ANALYSIS:
        base: tuple[RouterRequirement, ...] = (
            RouterRequirement.PORTFOLIO_SNAPSHOT,
            RouterRequirement.CASH_LIQUIDITY,
            RouterRequirement.PORTFOLIO_ANALYTICS,
        )
        if _contains_any(text, _OPERATIONS_MARKERS):
            return (*base, RouterRequirement.OPERATIONS_HISTORY)
        return base
    if intent is CioIntent.PORTFOLIO_MANAGEMENT:
        return (
            RouterRequirement.PORTFOLIO_SNAPSHOT,
            RouterRequirement.CASH_LIQUIDITY,
            RouterRequirement.PORTFOLIO_ANALYTICS,
            RouterRequirement.POLICY_CONTEXT,
        )
    if intent is CioIntent.CASH_ALLOCATION:
        return (
            RouterRequirement.PORTFOLIO_SNAPSHOT,
            RouterRequirement.CASH_LIQUIDITY,
            RouterRequirement.PORTFOLIO_ANALYTICS,
            RouterRequirement.POLICY_CONTEXT,
        )
    if intent is CioIntent.RISK:
        return (
            RouterRequirement.PORTFOLIO_SNAPSHOT,
            RouterRequirement.PORTFOLIO_ANALYTICS,
        )
    if intent is CioIntent.RESEARCH:
        return (
            RouterRequirement.INSTRUMENT_IDENTITY,
            RouterRequirement.FRESH_MARKET,
        )
    if intent is CioIntent.PLAN_REVIEW:
        return (RouterRequirement.FINAL_DECISION_REVIEW,)
    if intent is CioIntent.MONITORING:
        return (RouterRequirement.PORTFOLIO_SNAPSHOT,)
    return ()


def _workflow_for(intent: CioIntent) -> CioWorkflow:
    mapping = {
        CioIntent.ANALYSIS: CioWorkflow.PORTFOLIO_ANALYSIS,
        CioIntent.PORTFOLIO_MANAGEMENT: CioWorkflow.PORTFOLIO_MANAGEMENT,
        CioIntent.RISK: CioWorkflow.RISK_REVIEW,
        CioIntent.RESEARCH: CioWorkflow.ASSET_RESEARCH,
        CioIntent.CASH_ALLOCATION: CioWorkflow.CASH_ALLOCATION,
        CioIntent.PLAN_REVIEW: CioWorkflow.PLAN_REVIEW,
        CioIntent.MONITORING: CioWorkflow.MONITORING_REVIEW,
    }
    return mapping[intent]


def route_user_intent(user_text: str) -> IntentRouteV1:
    """Classify a user request without performing I/O or authorizing execution."""

    raw = str(user_text or "")
    normalized = _normalize(raw)
    exact_actions = _detect_exact_actions(raw, normalized)
    if exact_actions:
        return _exact_action_route(exact_actions)

    if not normalized:
        return IntentRouteV1(
            primary_intent=CioIntent.UNKNOWN,
            workflow=CioWorkflow.UNRESOLVED,
            confidence=RouterConfidence.LOW,
            clarification_required=True,
            clarification_code=RouterClarificationCode.INTENT_NOT_RECOGNIZED,
        )

    execution = _execution_route(normalized)
    if execution is not None:
        return execution

    diagnostic = _diagnostic_route(normalized)
    if diagnostic is not None:
        return diagnostic

    detected = _detected_intents(normalized)
    if not detected:
        return IntentRouteV1(
            primary_intent=CioIntent.UNKNOWN,
            workflow=CioWorkflow.UNRESOLVED,
            confidence=RouterConfidence.LOW,
            clarification_required=True,
            clarification_code=RouterClarificationCode.INTENT_NOT_RECOGNIZED,
        )

    primary = next(intent for intent in _INTENT_PRIORITY if intent in detected)
    secondary = tuple(
        intent
        for intent in _INTENT_PRIORITY
        if intent in detected and intent is not primary
    )
    return IntentRouteV1(
        primary_intent=primary,
        secondary_intents=secondary,
        workflow=_workflow_for(primary),
        confidence=RouterConfidence.HIGH,
        requirements=_requirements_for(primary, normalized),
    )
