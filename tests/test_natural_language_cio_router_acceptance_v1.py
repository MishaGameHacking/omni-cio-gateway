from __future__ import annotations

import pytest

from omni_cio.contracts.v1.intent_router import CioIntent, CioWorkflow
from omni_cio.router import route_user_intent


@pytest.mark.parametrize(
    ("text", "intent", "workflow"),
    (
        (
            "Что с портфелем?",
            CioIntent.ANALYSIS,
            CioWorkflow.PORTFOLIO_ANALYSIS,
        ),
        (
            "Сделай портфель лучше",
            CioIntent.PORTFOLIO_MANAGEMENT,
            CioWorkflow.PORTFOLIO_MANAGEMENT,
        ),
        (
            "Деверсифицируй партфель",
            CioIntent.PORTFOLIO_MANAGEMENT,
            CioWorkflow.PORTFOLIO_MANAGEMENT,
        ),
        (
            "Что купить на 100 000 рублей?",
            CioIntent.CASH_ALLOCATION,
            CioWorkflow.CASH_ALLOCATION,
        ),
        (
            "Распредели деньги по активам",
            CioIntent.CASH_ALLOCATION,
            CioWorkflow.CASH_ALLOCATION,
        ),
        (
            "Покажи план действий",
            CioIntent.PLAN_REVIEW,
            CioWorkflow.PLAN_REVIEW,
        ),
        (
            "Объясни план",
            CioIntent.PLAN_REVIEW,
            CioWorkflow.PLAN_REVIEW,
        ),
        (
            "Сообщи когда появится критический риск",
            CioIntent.MONITORING,
            CioWorkflow.MONITORING_REVIEW,
        ),
        (
            "Найди лучшие облигации",
            CioIntent.RESEARCH,
            CioWorkflow.ASSET_RESEARCH,
        ),
        (
            "Проверь новости по моим компаниям",
            CioIntent.RESEARCH,
            CioWorkflow.ASSET_RESEARCH,
        ),
        (
            "Проанализируй акции SBER",
            CioIntent.RESEARCH,
            CioWorkflow.ASSET_RESEARCH,
        ),
        (
            "Разбери фонд LQDT",
            CioIntent.RESEARCH,
            CioWorkflow.ASSET_RESEARCH,
        ),
    ),
)
def test_broad_russian_cio_acceptance(
    text: str,
    intent: CioIntent,
    workflow: CioWorkflow,
) -> None:
    route = route_user_intent(text)

    assert route.primary_intent is intent
    assert route.workflow is workflow
    assert route.execution_authorized is False
    assert route.router_read_only is True


def test_execute_plan_language_is_execution_but_still_fail_closed() -> None:
    route = route_user_intent("Исполняй план")

    assert route.primary_intent is CioIntent.EXECUTION
    assert route.clarification_required is True
    assert route.execution_authorized is False
    assert route.owner_confirmation_required_for_write is True
