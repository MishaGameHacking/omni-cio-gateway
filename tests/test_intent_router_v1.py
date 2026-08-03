from __future__ import annotations

import pytest

from omni_cio.orchestration.intent_router_v1 import (
    BASELINE_READ_ONLY_ACTIONS,
    IntentV1,
    RouteConfidence,
    StepKind,
    normalize_user_text,
    route_user_intent,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Проанализируй портфель", IntentV1.PORTFOLIO_ANALYSIS),
        ("проанализируй партфель", IntentV1.PORTFOLIO_ANALYSIS),
        ("Что с портфелем?", IntentV1.PORTFOLIO_ANALYSIS),
        ("УПРАВЛЯЙ ПОРТФЕЛЕМ", IntentV1.PORTFOLIO_MANAGEMENT),
        ("Сделай портфель лучше", IntentV1.PORTFOLIO_MANAGEMENT),
        ("Деверсифицируй портфель", IntentV1.PORTFOLIO_MANAGEMENT),
        ("Проверь риски и концентрацию", IntentV1.RISK_REVIEW),
        ("Есть ли риск дефолта?", IntentV1.RISK_REVIEW),
        ("Найди лучшие облигации", IntentV1.RESEARCH),
        ("Сравни кандидатов по рынку", IntentV1.RESEARCH),
        ("Проверь новости по моим компаниям", IntentV1.RESEARCH),
        ("Куда вложить свободные деньги?", IntentV1.CASH_ALLOCATION),
        ("Что купить на 100 000 рублей?", IntentV1.CASH_ALLOCATION),
        ("Распредели деньги по активам", IntentV1.CASH_ALLOCATION),
        ("Покажи план действий", IntentV1.PLAN_REVIEW),
        ("Объясни план", IntentV1.PLAN_REVIEW),
        ("Следи за новостями по портфелю", IntentV1.MONITORING),
        ("Сообщи когда появится критический риск", IntentV1.MONITORING),
        ("Проанализируй акции SBER", IntentV1.ASSET_ANALYSIS),
        ("Разбери фонд LQDT", IntentV1.ASSET_ANALYSIS),
        ("Купи SBER", IntentV1.EXECUTION_REQUEST),
        ("Продай эту позицию", IntentV1.EXECUTION_REQUEST),
        ("Исполняй план", IntentV1.EXECUTION_REQUEST),
    ],
)
def test_natural_russian_acceptance(text: str, expected: IntentV1) -> None:
    route = route_user_intent(text)

    assert route.intent == expected
    assert route.clarification_required is False
    assert route.workflow_id.endswith(".v1")


def test_portfolio_management_keeps_analysis_before_plan() -> None:
    route = route_user_intent("Управляй портфелем и скажи что делать")

    assert route.intent == IntentV1.PORTFOLIO_MANAGEMENT
    assert [step.operation_id for step in route.steps[:3]] == [
        "getPortfolioSnapshot",
        "getCashLiquiditySnapshot",
        "getPortfolioAnalytics",
    ]
    assert route.steps[-1].kind == StepKind.OWNER_GATE
    assert route.requires_owner_confirmation is True
    assert route.real_money_possible is True


def test_embedded_buy_request_becomes_plan_not_submit_permission() -> None:
    route = route_user_intent(
        "Управляй портфелем: если нужно, купи подходящие активы"
    )

    assert route.intent == IntentV1.PORTFOLIO_MANAGEMENT
    assert route.write_intent_detected is True
    assert route.requires_owner_confirmation is True
    assert all(step.operation_id != "executeRealTrade" for step in route.steps)
    assert all(step.operation_id != "prepareRealTrade" for step in route.steps)
    assert route.steps[-1].kind == StepKind.OWNER_GATE


def test_cash_allocation_is_policy_and_optimizer_aware() -> None:
    route = route_user_intent("Куда вложить 600 000 рублей?")

    assert route.intent == IntentV1.CASH_ALLOCATION
    dependencies = {
        step.required_work_package
        for step in route.steps
        if step.required_work_package is not None
    }
    assert {"WP2", "WP3", "WP4", "WP10", "WP11"} <= dependencies
    assert route.steps[-1].kind == StepKind.OWNER_GATE


def test_research_uses_future_internal_engines_not_fake_action_ids() -> None:
    route = route_user_intent(
        "Исследуй рынок и найди перспективные надежные облигации"
    )

    assert route.intent == IntentV1.RESEARCH
    assert route.steps
    assert all(step.kind == StepKind.INTERNAL for step in route.steps)
    assert all(step.operation_id is None for step in route.steps)


def test_monitoring_is_read_only_and_waits_for_wp13() -> None:
    route = route_user_intent("Постоянно проверяй риски портфеля и сообщай если что")

    assert route.intent == IntentV1.MONITORING
    assert route.requires_owner_confirmation is False
    assert all(step.read_only for step in route.steps)
    assert any(step.required_work_package == "WP13" for step in route.steps)


def test_direct_execution_request_never_contains_live_write_action() -> None:
    route = route_user_intent("Купи мне SBER на свободные деньги")

    assert route.intent == IntentV1.EXECUTION_REQUEST
    assert route.requires_owner_confirmation is True
    assert route.real_money_possible is True
    assert route.write_intent_detected is True
    assert all(step.operation_id is None for step in route.steps)
    assert any(step.kind == StepKind.OWNER_GATE for step in route.steps)
    assert any(step.required_work_package == "WP12" for step in route.steps)


def test_exact_action_has_absolute_isolation_priority() -> None:
    route = route_user_intent(
        "Вызови только getPortfolioSnapshot. Потом как-нибудь управляй портфелем."
    )

    assert route.intent == IntentV1.EXACT_ACTION
    assert route.exact_action == "getPortfolioSnapshot"
    assert route.confidence == RouteConfidence.HIGH
    assert len(route.steps) == 1
    assert route.steps[0].operation_id == "getPortfolioSnapshot"
    assert route.steps[0].read_only is True
    assert route.requires_owner_confirmation is False


def test_exact_consequential_action_keeps_owner_gate_requirement() -> None:
    route = route_user_intent("Вызови только executeRealTrade")

    assert route.intent == IntentV1.EXACT_ACTION
    assert route.exact_action == "executeRealTrade"
    assert len(route.steps) == 1
    assert route.steps[0].operation_id == "executeRealTrade"
    assert route.steps[0].read_only is False
    assert route.requires_owner_confirmation is True
    assert route.real_money_possible is True


def test_multiple_exact_actions_fail_closed_to_clarification() -> None:
    route = route_user_intent(
        "Вызови только getPortfolioSnapshot и getPortfolioAnalytics"
    )

    assert route.intent == IntentV1.EXACT_ACTION
    assert route.exact_action is None
    assert route.steps == ()
    assert route.clarification_required is True
    assert route.clarification_reason == "MULTIPLE_EXACT_ACTIONS_REQUESTED"


def test_unknown_exact_action_fails_closed() -> None:
    route = route_user_intent("Вызови только destroyEverything")

    assert route.intent == IntentV1.EXACT_ACTION
    assert route.steps == ()
    assert route.clarification_required is True
    assert route.clarification_reason == "UNKNOWN_EXACT_ACTION:destroyEverything"


def test_exact_action_respects_deployed_action_surface() -> None:
    route = route_user_intent(
        "Вызови только getRealTradingStatus",
        available_actions=BASELINE_READ_ONLY_ACTIONS,
    )

    assert route.intent == IntentV1.EXACT_ACTION
    assert route.steps == ()
    assert route.clarification_required is True
    assert route.clarification_reason == "UNKNOWN_EXACT_ACTION:getRealTradingStatus"


def test_unknown_request_is_the_only_normal_clarification_path() -> None:
    route = route_user_intent("Сделай там нормально как-нибудь")

    assert route.intent == IntentV1.UNKNOWN
    assert route.confidence == RouteConfidence.LOW
    assert route.clarification_required is True
    assert route.clarification_reason == "INTENT_NOT_CONFIDENTLY_RESOLVED"
    assert route.steps == ()


def test_empty_request_requires_clarification() -> None:
    route = route_user_intent("   ")

    assert route.intent == IntentV1.UNKNOWN
    assert route.clarification_required is True
    assert route.clarification_reason == "EMPTY_REQUEST"


def test_non_exact_routes_only_reference_baseline_read_only_actions() -> None:
    examples = (
        "Проанализируй портфель",
        "Управляй портфелем",
        "Проверь риски",
        "Куда вложить деньги",
        "Покажи план",
        "Следи за портфелем",
        "Разбери фонд LQDT",
        "Купи SBER",
    )

    for text in examples:
        route = route_user_intent(text)
        for step in route.steps:
            if step.operation_id is None:
                continue
            assert step.operation_id in BASELINE_READ_ONLY_ACTIONS
            assert step.read_only is True


def test_normalization_handles_case_punctuation_yo_and_typo() -> None:
    normalized = normalize_user_text("  ДЕВЕРСИФИЦИРУЙ, ПАРТФЕЛЬ!!! Ёлки  ")

    assert "диверсифицируй" in normalized
    assert "портфель" in normalized
    assert "елки" in normalized


def test_score_confidence_is_high_for_canonical_management_command() -> None:
    route = route_user_intent("Управляй портфелем")

    assert route.confidence == RouteConfidence.HIGH
    assert "управляй портфел" in route.matched_signals


def test_one_time_news_check_is_research_not_recurring_monitoring() -> None:
    route = route_user_intent("Проверь новости по моим компаниям")

    assert route.intent == IntentV1.RESEARCH
    assert route.requires_owner_confirmation is False


def test_monitoring_beats_research_when_recurring_signal_is_explicit() -> None:
    route = route_user_intent("Следи за новостями по моим компаниям")

    assert route.intent == IntentV1.MONITORING
    assert "следи за" in route.matched_signals
