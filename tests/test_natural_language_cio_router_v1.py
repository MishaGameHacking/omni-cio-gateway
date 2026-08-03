from __future__ import annotations

from pathlib import Path

import pytest

from omni_cio.contracts.v1.intent_router import (
    CioIntent,
    CioWorkflow,
    ExecutionContour,
    ExecutionDirection,
    ExecutionPhase,
    RouterClarificationCode,
    RouterConfidence,
    RouterRequirement,
)
from omni_cio.router import KNOWN_ACTIONS, route_user_intent


@pytest.mark.parametrize(
    ("text", "intent", "workflow"),
    (
        (
            "Проанализируй портфель",
            CioIntent.ANALYSIS,
            CioWorkflow.PORTFOLIO_ANALYSIS,
        ),
        (
            "УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать",
            CioIntent.PORTFOLIO_MANAGEMENT,
            CioWorkflow.PORTFOLIO_MANAGEMENT,
        ),
        (
            "Распредели свободные деньги",
            CioIntent.CASH_ALLOCATION,
            CioWorkflow.CASH_ALLOCATION,
        ),
        ("Проверь риски", CioIntent.RISK, CioWorkflow.RISK_REVIEW),
        (
            "Что изменилось?",
            CioIntent.ANALYSIS,
            CioWorkflow.PORTFOLIO_ANALYSIS,
        ),
        (
            "Есть ли опасность дефолта?",
            CioIntent.RISK,
            CioWorkflow.RISK_REVIEW,
        ),
        (
            "Подготовь лучший план на текущий капитал",
            CioIntent.PORTFOLIO_MANAGEMENT,
            CioWorkflow.PORTFOLIO_MANAGEMENT,
        ),
        (
            "Проверь план ребалансировки",
            CioIntent.PLAN_REVIEW,
            CioWorkflow.PLAN_REVIEW,
        ),
        (
            "Следи за рейтингом этой облигации",
            CioIntent.MONITORING,
            CioWorkflow.MONITORING_REVIEW,
        ),
        (
            "Разбери компанию и её акции",
            CioIntent.RESEARCH,
            CioWorkflow.ASSET_RESEARCH,
        ),
    ),
)
def test_program_human_commands_route_without_action_names(
    text: str,
    intent: CioIntent,
    workflow: CioWorkflow,
) -> None:
    route = route_user_intent(text)

    assert route.primary_intent is intent
    assert route.workflow is workflow
    assert route.confidence is RouterConfidence.HIGH
    assert route.exact_actions == ()
    assert route.exact_action_scope_locked is False
    assert route.execution_authorized is False
    assert route.router_read_only is True


def test_portfolio_analysis_preserves_v861_baseline_requirements() -> None:
    route = route_user_intent("Проанализируй портфель")

    assert route.requirements == (
        RouterRequirement.PORTFOLIO_SNAPSHOT,
        RouterRequirement.CASH_LIQUIDITY,
        RouterRequirement.PORTFOLIO_ANALYTICS,
    )


def test_what_changed_adds_operations_evidence() -> None:
    route = route_user_intent("Что изменилось?")

    assert route.requirements == (
        RouterRequirement.PORTFOLIO_SNAPSHOT,
        RouterRequirement.CASH_LIQUIDITY,
        RouterRequirement.PORTFOLIO_ANALYTICS,
        RouterRequirement.OPERATIONS_HISTORY,
    )


def test_cash_allocation_requires_policy_context_without_inventing_it() -> None:
    route = route_user_intent("Что мне купить на свободные деньги?")

    assert route.primary_intent is CioIntent.CASH_ALLOCATION
    assert RouterRequirement.POLICY_CONTEXT in route.requirements
    assert route.execution_authorized is False


def test_advisory_buy_question_is_research_not_execution() -> None:
    route = route_user_intent("Стоит ли купить SBER?")

    assert route.primary_intent is CioIntent.RESEARCH
    assert route.workflow is CioWorkflow.ASSET_RESEARCH
    assert route.execution_contour is ExecutionContour.NONE
    assert route.owner_confirmation_required_for_write is False
    assert route.execution_authorized is False


def test_real_buy_request_routes_to_execution_but_never_authorizes() -> None:
    route = route_user_intent("Купи 1 лот SBER реально")

    assert route.primary_intent is CioIntent.EXECUTION
    assert route.workflow is CioWorkflow.EXECUTION_REQUEST
    assert route.execution_contour is ExecutionContour.REAL
    assert route.execution_phase is ExecutionPhase.REQUEST
    assert route.execution_direction is ExecutionDirection.BUY
    assert route.clarification_required is False
    assert route.owner_confirmation_required_for_write is True
    assert route.execution_authorized is False
    assert route.requirements == (
        RouterRequirement.REAL_TRADING_STATUS,
        RouterRequirement.INSTRUMENT_IDENTITY,
        RouterRequirement.FRESH_MARKET,
    )


def test_bare_buy_request_fails_closed_until_execution_contour_is_explicit() -> None:
    route = route_user_intent("Купи 1 лот SBER")

    assert route.primary_intent is CioIntent.EXECUTION
    assert route.execution_contour is ExecutionContour.UNSPECIFIED
    assert route.execution_direction is ExecutionDirection.BUY
    assert route.clarification_required is True
    assert (
        route.clarification_code
        is RouterClarificationCode.EXECUTION_CONTOUR_REQUIRED
    )
    assert route.execution_authorized is False


def test_real_and_sandbox_execution_ambiguity_fails_closed() -> None:
    route = route_user_intent("Купи SBER реально в Sandbox")

    assert route.primary_intent is CioIntent.EXECUTION
    assert route.execution_contour is ExecutionContour.AMBIGUOUS
    assert route.clarification_required is True
    assert (
        route.clarification_code
        is RouterClarificationCode.EXECUTION_CONTOUR_AMBIGUOUS
    )
    assert route.execution_authorized is False


def test_buy_and_sell_direction_ambiguity_fails_closed() -> None:
    route = route_user_intent("Купи и продай SBER реально")

    assert route.primary_intent is CioIntent.EXECUTION
    assert route.execution_direction is ExecutionDirection.AMBIGUOUS
    assert route.clarification_required is True
    assert (
        route.clarification_code
        is RouterClarificationCode.EXECUTION_DIRECTION_AMBIGUOUS
    )
    assert route.execution_authorized is False


def test_execution_phrase_without_direction_requires_clarification() -> None:
    route = route_user_intent("Подготовь реальную сделку по SBER")

    assert route.primary_intent is CioIntent.EXECUTION
    assert route.execution_contour is ExecutionContour.REAL
    assert route.execution_direction is ExecutionDirection.NONE
    assert (
        route.clarification_code
        is RouterClarificationCode.EXECUTION_DIRECTION_REQUIRED
    )
    assert route.execution_authorized is False


def test_real_confirmation_is_classified_but_not_server_authorized() -> None:
    route = route_user_intent("ПОДТВЕРЖДАЮ РЕАЛЬНУЮ СДЕЛКУ")

    assert route.primary_intent is CioIntent.EXECUTION
    assert route.workflow is CioWorkflow.EXECUTION_CONFIRMATION
    assert route.execution_contour is ExecutionContour.REAL
    assert route.execution_phase is ExecutionPhase.CONFIRMATION
    assert route.execution_direction is ExecutionDirection.NONE
    assert route.clarification_required is False
    assert route.owner_confirmation_required_for_write is True
    assert route.execution_authorized is False


def test_sandbox_confirmation_stays_isolated() -> None:
    route = route_user_intent("ПОДТВЕРЖДАЮ SANDBOX СДЕЛКУ")

    assert route.primary_intent is CioIntent.EXECUTION
    assert route.execution_contour is ExecutionContour.SANDBOX
    assert route.execution_phase is ExecutionPhase.CONFIRMATION
    assert route.execution_authorized is False


def test_exact_action_has_precedence_and_scope_never_expands() -> None:
    route = route_user_intent(
        "Вызови только getPortfolioSnapshot. Потом ничего больше не вызывай."
    )

    assert route.primary_intent is CioIntent.EXACT_ACTION
    assert route.workflow is CioWorkflow.EXACT_ACTION
    assert route.exact_actions == ("getPortfolioSnapshot",)
    assert route.exact_action_scope_locked is True
    assert route.requirements == ()
    assert route.execution_authorized is False


def test_multiple_explicit_actions_preserve_user_sequence() -> None:
    route = route_user_intent(
        "Сначала getPortfolioSnapshot, затем getOperationsHistory."
    )

    assert route.primary_intent is CioIntent.EXACT_ACTION
    assert route.exact_actions == (
        "getPortfolioSnapshot",
        "getOperationsHistory",
    )
    assert route.exact_action_scope_locked is True


def test_exact_execute_action_still_requires_owner_confirmation_gate() -> None:
    route = route_user_intent("Вызови только executeRealTrade")

    assert route.primary_intent is CioIntent.EXACT_ACTION
    assert route.exact_actions == ("executeRealTrade",)
    assert route.execution_contour is ExecutionContour.REAL
    assert route.execution_phase is ExecutionPhase.CONFIRMATION
    assert route.owner_confirmation_required_for_write is True
    assert route.execution_authorized is False


def test_real_status_exact_action_is_read_only() -> None:
    route = route_user_intent("getRealTradingStatus — покажи полный результат")

    assert route.primary_intent is CioIntent.EXACT_ACTION
    assert route.exact_actions == ("getRealTradingStatus",)
    assert route.execution_contour is ExecutionContour.REAL
    assert route.owner_confirmation_required_for_write is False
    assert route.execution_authorized is False


def test_action_name_mentioned_conversationally_is_not_invoked() -> None:
    route = route_user_intent("Что делает getPortfolioSnapshot?")

    assert route.primary_intent is CioIntent.UNKNOWN
    assert route.exact_actions == ()
    assert route.exact_action_scope_locked is False
    assert route.clarification_required is True
    assert route.execution_authorized is False


def test_gateway_and_connection_diagnostics_are_distinct() -> None:
    gateway = route_user_intent("Проверь шлюз")
    connection = route_user_intent("Проверь подключение к T-Invest")

    assert gateway.primary_intent is CioIntent.DIAGNOSTIC
    assert gateway.workflow is CioWorkflow.GATEWAY_DIAGNOSTIC
    assert gateway.requirements == (RouterRequirement.GATEWAY_HEALTH,)
    assert connection.primary_intent is CioIntent.DIAGNOSTIC
    assert connection.workflow is CioWorkflow.CONNECTION_DIAGNOSTIC
    assert connection.requirements == (RouterRequirement.CONNECTION,)


def test_compound_request_has_deterministic_primary_and_secondary_intent() -> None:
    route = route_user_intent("Управляй портфелем и проверь риски")

    assert route.primary_intent is CioIntent.PORTFOLIO_MANAGEMENT
    assert route.secondary_intents == (CioIntent.RISK,)


@pytest.mark.parametrize(
    ("text", "intent"),
    (
        ("ПРОВЕРЬ РИСКИ ПОРТФЁЛЯ!!!", CioIntent.RISK),
        ("Проанализируй партфель", CioIntent.ANALYSIS),
        ("Управляй партфелем", CioIntent.PORTFOLIO_MANAGEMENT),
    ),
)
def test_normalization_handles_case_yo_and_common_portfolio_typos(
    text: str,
    intent: CioIntent,
) -> None:
    route = route_user_intent(text)

    assert route.primary_intent is intent


def test_unknown_or_empty_input_requests_clarification() -> None:
    for text in ("", "   ", "Привет"):
        route = route_user_intent(text)
        assert route.primary_intent is CioIntent.UNKNOWN
        assert route.workflow is CioWorkflow.UNRESOLVED
        assert route.confidence is RouterConfidence.LOW
        assert route.clarification_required is True
        assert (
            route.clarification_code
            is RouterClarificationCode.INTENT_NOT_RECOGNIZED
        )
        assert route.execution_authorized is False


def test_router_output_does_not_store_raw_user_text() -> None:
    private_note_phrase = "Купи SBER реально, моя приватная заметка 12345"
    route = route_user_intent(private_note_phrase)

    serialized = route.model_dump_json()
    assert private_note_phrase not in serialized
    assert "приватная заметка" not in serialized


def test_known_action_registry_is_unique_and_matches_canonical_catalog() -> None:
    assert len(KNOWN_ACTIONS) == 26
    assert len(KNOWN_ACTIONS) == len(set(KNOWN_ACTIONS))

    root = Path(__file__).resolve().parents[1]
    catalog = (root / "gpt" / "ACTIONS_CATALOG.md").read_text(encoding="utf-8")
    for action in KNOWN_ACTIONS:
        assert action in catalog
