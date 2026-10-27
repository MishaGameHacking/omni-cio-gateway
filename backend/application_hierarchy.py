"""Executable N00-N11 dependency map over the existing modular application.

This is a component inventory, not a claim that every planned feature passed
acceptance. Paths are references, never dynamically imported or executed.
No new services, database server or automatic trade toggle is created here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re


@dataclass(frozen=True)
class Component:
    identifier: str
    title: str
    responsibility: str
    dependencies: tuple[str, ...]
    source_paths: tuple[str, ...]
    implementation: str
    outstanding: tuple[str, ...]


COMPONENTS = (
    Component("N00", "Основа и среда", "Идентичность, миграции, авторизация, проверки и доставка", (),
        ("backend/app.py", "backend/volume_state.py"), "partial",
        ("native_android_matrix", "exact_head_sonar", "physical_phone_verification")),
    Component("N01", "Инвестиционный профиль", "Версионированная стратегия и её ограничения", ("N00",),
        ("backend/portfolio_mandate.py", "backend/volume_state.py"), "partial",
        ("full_loss_capacity_application", "turnover_and_reinvestment_integration")),
    Component("N02", "Сбор и расписание", "Независимые события, календарь, очередь и восстановление", ("N00",),
        ("backend/background_dispatch.py", "backend/event_monitor.py", "backend/market_schedule.py"), "partial",
        ("instrument_halt_pretrade_gate", "long_running_observation")),
    Component("N03", "Источники и доказательства", "Происхождение, идентичность, версии и свежесть", ("N00", "N02"),
        ("backend/public_sources.py", "backend/research_store.py", "backend/source_observability.py"), "partial",
        ("automatic_four_agency_rating_coverage", "verified_financial_statement_adapters")),
    Component("N04", "Денежный учёт", "Журнал операций и арифметика сверки и доходности", ("N00", "N01"),
        ("backend/operations_ledger.py", "backend/portfolio_accounting.py"), "partial",
        ("independent_live_cash_reconciliation", "live_twr_xirr_inputs", "tax_and_settlement_accounting")),
    Component("N05", "Досье и риск", "Проверяемые признаки риска и сценарии", ("N03", "N04"),
        ("backend/portfolio_risk.py", "backend/portfolio_scenarios.py", "backend/credit_evidence.py"), "partial",
        ("sector_specific_dossiers", "validated_early_warning", "probability_calibration")),
    Component("N06", "ИИ и бюджет", "Ограничение затрат и обоснования на проверенных фактах", ("N03",),
        ("backend/ai_budget.py", "backend/ai_guarded_client.py", "backend/analysis_engine.py"), "partial",
        ("route_evaluation_dataset", "rules_vs_model_comparison", "end_to_end_quality_acceptance")),
    Component("N07", "Планировщик", "Целые лоты, резерв, издержки и альтернатива не менять", ("N01", "N04", "N05"),
        ("backend/allocation_plan.py", "backend/volume_plans.py", "backend/volume_purchases.py"), "partial",
        ("complete_joint_optimizer", "all_cost_and_suitability_constraints")),
    Component("N08", "Исполнение без реальных денег", "Симулятор, журнал, резервы и восстановление", ("N02", "N04", "N07"),
        ("backend/paper_execution.py", "tools/run_paper_execution.py"), "simulation_only",
        ("sandbox_adapter_and_reconciliation", "full_execution_fault_matrix", "live_broker_executor")),
    Component("N09", "Интерфейс и наблюдаемость", "Согласованные состояния системы и объяснения", ("N01", "N05", "N07", "N08"),
        ("backend/workspace_readiness.py", "backend/volume_workspace.py", "app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceData.kt"), "partial",
        ("native_readiness_surface", "full_keyboard_free_and_accessibility_acceptance")),
    Component("N10", "Теневые испытания", "История, нагрузки и воспроизводимое восстановление", ("N03", "N04", "N05", "N06", "N07", "N08", "N09"),
        ("tools/run_paper_execution.py",), "not_accepted",
        ("thirty_actual_shadow_trading_sessions", "rare_failure_replay", "load_and_restore_acceptance")),
    Component("N11", "Полный выпуск", "Совместимый APK и сервер с полными свидетельствами", ("N00", "N01", "N02", "N03", "N04", "N05", "N06", "N07", "N08", "N09", "N10"),
        ("app/build.gradle.kts",), "not_accepted",
        ("all_stage_acceptance", "signed_apk_matrix", "exact_release_channel_bytes")),
)


def dependency_order(components: tuple[Component, ...] = COMPONENTS) -> tuple[str, ...]:
    if not isinstance(components, tuple) or len(components) > 100:
        raise ValueError("component_registry_invalid")
    indexed = {}
    for node in components:
        if not isinstance(node, Component) or re.fullmatch(r"N[0-9]{2}", node.identifier) is None:
            raise ValueError("component_identity_invalid")
        if node.identifier in indexed:
            raise ValueError("component_identity_duplicate")
        if len(set(node.dependencies)) != len(node.dependencies):
            raise ValueError("component_dependency_duplicate")
        indexed[node.identifier] = node
    complete, pending, order = set(), set(indexed), []
    for node in components:
        if any(key not in indexed for key in node.dependencies):
            raise ValueError("component_dependency_unknown")
    while pending:
        ready = sorted(key for key in pending if set(indexed[key].dependencies) <= complete)
        if not ready:
            raise ValueError("component_dependency_cycle")
        order.extend(ready)
        complete.update(ready)
        pending.difference_update(ready)
    return tuple(order)


def hierarchy() -> dict:
    indexed = {node.identifier: node for node in COMPONENTS}
    nodes = []
    for identifier in dependency_order():
        row = asdict(indexed[identifier])
        row.update(acceptance_complete=False, completion_percentage=None,
                   code_presence_is_acceptance=False)
        nodes.append(row)
    return {"schema_version": 1, "architecture": "existing_modular_backend_and_android_client",
            "components": nodes, "all_stages_complete": False,
            "execution_mode": "read_only", "real_orders_enabled": False,
            "new_database_server_required": False}
