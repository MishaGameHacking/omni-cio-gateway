"""Exercise production screens using the explicitly synthetic debug transport.

The fixture never calls a broker/model or ships in preview. Only live emulator
accessibility frames, mutation results and actual screenshots become evidence.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import time
from chat_recovery_ui_probe import chat_counters

SYNTHETIC_LIMIT_CHANGE = 'Синтетическое изменение лимита'
SYNTHETIC_LIMIT_STATE = "notification-state-synthetic-notification"


ROUTES = ("risk", "assistant", "plans", "strategy", "notifications", "analysis", "catalogue")
CASES = tuple((route, scenario) for route in ROUTES
              for scenario in ("ready", "empty", "partial", "error", "job")
              if scenario != "job" or route in {"assistant", "plans"})
BANNER = "ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ"
ERROR = "Синтетический отказ источника. Настоящая сеть не вызывалась."
ANSWER = "СИНТЕТИЧЕСКИЙ ОТВЕТ: тестовая доля компании 70% сопоставлена с пользовательским лимитом 60%. Это проверка интерфейса, не инвестиционный совет."
PARTIAL_ANSWER = "СИНТЕТИЧЕСКИЙ ОТВЕТ: часть исходных сведений отсутствует; точный вывод не подтверждён."
UNCERTAIN = "Исход запроса к модели пока не подтверждён. Автоматического повторного запроса нет."
CONFIRM_VERSION = "Подтвердить эту версию"
RISK_SOURCE_LABEL = "Открыть синтетический источник"


def labels(node):
    return [part.strip() for value in (node.get("text", ""), node.get("content-desc", "")) for part in value.splitlines() if part.strip()]


def _business_counters(parts):
    keys = ("requests", "contract-errors", "scenario-compares")
    if any(not re.fullmatch(r"\d+", parts.get(key, "")) for key in keys):
        raise AssertionError("Invalid observed business transport counters")
    counts = {key: int(parts[key]) for key in keys}
    if counts["contract-errors"]:
        raise AssertionError("The real screen submitted an invalid fixture contract")
    if counts["scenario-compares"] > counts["requests"]:
        raise AssertionError("Scenario comparison count exceeds actual requests")
    return counts


def business_marker(tree, route, scenario):
    """Require exact fixture identity, its real request count and zero rejects."""
    if (route, scenario) not in CASES:
        raise ValueError("Unsupported business case")
    for node in tree.iter("node"):
        if node.get("package") != "ru.omnicio.app.debug" or node.get("visible-to-user") == "false":
            continue
        parts = {key: value for part in node.get("content-desc", "").split(";") if ":" in part for key, value in [part.split(":", 1)]}
        if parts.get("business-probe") != route + "/" + scenario or parts.get("transport") != "synthetic":
            continue
        counts = _business_counters(parts)
        if counts["requests"] > 0:
            return {"route": route, "scenario": scenario, "requests": counts["requests"],
                    "scenario_comparisons": counts["scenario-compares"],
                    "contract_errors": 0, "navigation": parts.get("navigation", "none"),
                    **chat_counters(parts, counts["requests"], scenario)}
    return None


def exercise_business(probe):
    from persistent_ui import FrameReader

    reader = getattr(probe.read_tree, "__self__", None)
    if not isinstance(reader, FrameReader):
        raise ValueError("Business checks require the owned persistent frame session")
    records = []
    probe.command("shell", "settings", "put", "system", "font_scale", "1.0")
    for font_scale in (1.0, 2.0):
        for route, scenario in CASES:
            records.append(_BusinessCase(probe, reader, route, scenario, font_scale).run())
    report = {"fixture": "debug-only-synthetic-transport", "actual_device_observations": True,
              "external_destination_screens_verified": False, "notification_workmanager_verified": False,
              "cases": records}
    base = Path(__file__).resolve().parents[2]
    folder = base / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(base):
        raise AssertionError("Business evidence escapes checkout")
    (folder / "business-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BUSINESS_UI_VERIFICATION=" + json.dumps(report, ensure_ascii=True, sort_keys=True), flush=True)
    return report


class _BusinessCase:
    def __init__(self, probe, reader, route, scenario, font_scale):
        self.probe, self.reader = probe, reader
        self.route, self.scenario, self.font_scale = route, scenario, font_scale
        self.checks = []
        self.draft_rotation = None
        self.impact_screenshot = None
        self.chat_recovery = None
        self.scenario_comparison = None
        self.strategy_editor = None

    def observed(self):
        return self.probe.wait_for(
            lambda: business_marker(self.probe.tree(), self.route, self.scenario),
            "Business fixture did not complete an actual request")

    def run(self):
        from profile_launch import launch_profile
        from spatial_frame_evidence import ready_spatial_metrics

        self.probe.command("shell", "settings", "put", "system", "font_scale", str(self.font_scale))
        print(f"BUSINESS_UI_CASE={self.route}/{self.scenario};font={self.font_scale}", flush=True)
        launch_profile(self.probe.command, self.probe.tree, self.probe.wait_for,
                       expected_screen="business-" + self.route, scenario=self.scenario)
        self.probe.find(BANNER)
        before = self.observed()
        scenarios = {"error": self.error, "job": self.job}
        routes = {"risk": self.risk, "strategy": self.strategy, "plans": self.plans,
                  "notifications": self.notifications, "analysis": self.analysis, "assistant": self.assistant,
                  "catalogue": self.catalogue}
        handler = scenarios.get(self.scenario, routes[self.route])
        handler()
        actual = self.observed()
        renderer = self.probe.wait_for(lambda: ready_spatial_metrics(self.probe.tree()), "Business screen did not render its genuine meshes")
        if not math.isclose(renderer.get("font-scale", 0.0), self.font_scale, rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError("The actual Compose font scale differs from the requested accessibility scenario")
        name = "business-" + self.route + "-" + self.scenario + ("-font-200" if math.isclose(self.font_scale, 2.0) else "")
        self.probe.capture(name)
        record = {"case": self.route + "/" + self.scenario, "font_scale": self.font_scale, "before": before, "after": actual,
                        "checks": self.checks, "native_input_rotation": self.draft_rotation,
                        "chat_recovery": self.chat_recovery,
                        "scenario_comparison": self.scenario_comparison,
                        "strategy_editor": self.strategy_editor,
                        "impact_screenshot": self.impact_screenshot + ".png" if self.impact_screenshot else None,
                        "renderer": renderer, "screenshot": name + ".png"}
        print("BUSINESS_UI_CASE_PASSED=" + self.route + "/" + self.scenario + ";font=" + str(self.font_scale), flush=True)
        return record

    def error(self):
        self.probe.reveal("Не удалось обновить", "workspace-content")
        self.probe.reveal(ERROR, "workspace-content")
        baseline = self.observed()["requests"]
        self.probe.tap("Повторить", "workspace-content")
        self.probe.wait_for(lambda observe=self.observed, minimum=baseline: (value if (value := observe())["requests"] > minimum else None),
                       "Retry did not issue a new synthetic transport request")
        self.probe.reveal(ERROR, "workspace-content", direction="start")
        self.checks.extend(("explicit-source-error", "retry-real-request"))

    def catalogue(self):
        from catalogue_ui_probe import exercise_catalogue
        exercise_catalogue(self)

    def job(self):
        from profile_ui_probe import matching_node

        # At font200 the independently scrollable chat history is only 237px
        # high. Its long answer can put recovery beyond ten semantic pages.
        self.probe.tap("Сохранённые задания · 1", "workspace-content", max_swipes=20)
        self.probe.tap_resource("recover-request-synthetic-request", "workspace-content")
        # Plans appends the recovered job below saved requests; Assistant inserts it above.
        direction = "end" if self.route == "plans" else "start"
        self.probe.reveal("Исход требует сверки", "workspace-content", direction=direction)
        self.probe.reveal(UNCERTAIN, "workspace-content")
        if matching_node(self.probe.tree(), "Повторить разрешённую задачу") is not None:
            raise AssertionError("Unknown paid request exposes an unsafe repeat action")
        self.checks.extend(("saved-request-recovered", "uncertain-not-repeated"))

    def risk(self):
        if self.scenario == "empty":
            self.probe.reveal("Покрытие пока не получено", "workspace-content")
            self.checks.append("missing-coverage-explicit")
        else:
            self.probe.reveal("Подтверждено " + ("1" if self.scenario == "partial" else "2") + " из 3 позиций", "workspace-content")
            self.probe.tap("Концентрация", "profile-tabs")
            self.probe.reveal("Синтетическая компания", "workspace-content")
            self.probe.reveal("Доля не получена" if self.scenario == "partial" else "Лимит превышен", "workspace-content")
            if self.scenario == "partial":
                self.probe.reveal("Сопоставление с лимитом не подтверждено", "workspace-content")
                self.probe.tap("История", "profile-tabs")
                self.probe.reveal("Синтетический рейтинг: свежесть не подтверждена", "workspace-content")
                self.probe.reveal("Новых подтверждённых данных недостаточно. Это событие не означает, что риск устранён.", "workspace-content")
                self.checks.extend(("unknown-share-not-zero", "stale-rating-not-resolved"))
            else:
                self.ready_risk()

    def strategy(self):
        if self.scenario == "empty":
            self.probe.reveal("Правила ещё не подтверждены", "workspace-content")
            self.checks.append("inactive-rules-explicit")
        else:
            self.probe.reveal("Действует версия 3", "workspace-content")
            if self.scenario == "ready":
                from strategy_editor_probe import exercise_strategy_editor
                self.strategy_editor = exercise_strategy_editor(self.probe, self.font_scale)
                self.checks.extend(("replace-whole-horizon", "empty-horizon-blocks-preview", "native-strategy-draft-rotation"))
            self.probe.tap("Рассчитать влияние", "workspace-content")
            self.probe.reveal("Влияние на текущий портфель", "workspace-content")
            if self.scenario == "partial":
                self.probe.reveal("Тест: источник части связей отсутствует; применение недоступно.", "workspace-content")
                from profile_ui_probe import button_label

                self.probe.reveal(CONFIRM_VERSION, "workspace-content")
                confirm = self.probe.wait_for(lambda: button_label(self.probe.tree(), CONFIRM_VERSION),
                                              "Strategy confirmation has no native Button")
                if confirm.get("enabled") != "false":
                    raise AssertionError("Incomplete strategy preview can be confirmed")
                self.checks.append("incomplete-preview-blocks-confirm")
            else:
                self.probe.tap(CONFIRM_VERSION, "workspace-content")
                self.probe.reveal("Действует версия 4", "workspace-content", direction="start")
                self.probe.tap("Версии", "profile-tabs")
                self.probe.reveal("Версия 2", "workspace-content")
                self.probe.tap("Проверить возврат к этой версии", "workspace-content")
                self.probe.reveal("Влияние на текущий портфель", "workspace-content")
                self.probe.tap(CONFIRM_VERSION, "workspace-content")
                self.probe.reveal("Действует версия 5", "workspace-content", direction="start")
                self.checks.extend(("preview-before-confirm", "new-confirmed-version", "rollback-creates-new-version"))

    def plans(self):
        if self.scenario == "empty":
            self.probe.reveal("Планов пока нет", "workspace-content")
            self.checks.append("empty-plans-explicit")
        else:
            self.probe.reveal("СИНТЕТИЧЕСКИЙ ПЛАН · акция", "workspace-content")
            if self.scenario == "partial":
                self.probe.reveal("Подтверждена часть количества", "workspace-content")
                self.probe.reveal("Сверено по операциям: 2 ед.", "workspace-content")
                self.select_plan_operation()
                self.probe.tap("Подтвердить связь выбранных операций", "workspace-content")
                self.probe.reveal("Сверено по операциям: 5 ед.", "workspace-content", direction="start")
                self.probe.reveal("Источник операций пока неполный. Итог исполнения не подтверждён.", "workspace-content")
                self.checks.extend(("real-partial-quantity", "bind-selected-operation", "incomplete-source-remains-explicit"))
            else:
                from native_input_evidence import append_native_text
                from plan_editor_probe import verify_plan_keyboard_viewport

                self.probe.reveal("Расчёт подготовлен", "workspace-content")
                self.probe.tap("Подготовить план", "workspace-content", direction="start")
                self.probe.find("Подготовить действие")
                self.probe.tap("Синтетическая акция", "workspace-content")
                self.probe.tap("Количество единиц инструмента", "workspace-content")
                append_native_text(self.probe, "", "5")
                verify_plan_keyboard_viewport(self.probe)
                self.probe.dismiss_keyboard()
                self.probe.tap("Проверить и сохранить расчёт", "workspace-content")
                self.probe.reveal(
                    "СИНТЕТИЧЕСКИЙ РАСЧЁТ · Покупка · Синтетическая акция", "workspace-content"
                )
                self.probe.reveal("План: 5 ед. · лот 1", "workspace-content")
                self.checks.extend(("native-quantity-input", "native-dialog-ime-insets", "new-confirmed-calculation"))

    def select_plan_operation(self):
        from profile_ui_probe import checkable_label

        # The only unbound synthetic operation has three units.
        control = self.reveal_prefix("", checkable=True, suffix=" · 3 ед.")
        operation_labels = {label for label in _control_labels(control) if label.endswith(" · 3 ед.")}
        if len(operation_labels) != 1 or control.get("checked") != "false":
            raise AssertionError("Unexpected reconciliation operation")
        operation_label = operation_labels.pop()
        # Discovery can see a clipped or still-moving switch. Use the same
        # fresh, settled native owner as ordinary labelled taps.
        self.probe.tap(operation_label, "workspace-content")
        self.probe.wait_for(lambda: (node if (node := checkable_label(self.probe.tree(), operation_label)) is not None
                                    and node.get("checked") == "true" else None),
                            "Reconciliation operation was not selected")

    def notifications(self):
        if self.scenario == "empty":
            self.probe.reveal("Новых событий пока нет", "workspace-content")
            self.checks.append("empty-events-explicit")
        else:
            self.probe.reveal(SYNTHETIC_LIMIT_CHANGE, "workspace-content")
            self.probe.reveal("Ожидает подходящего времени" if self.scenario == "partial" else "Устройство сообщило о показе", "workspace-content")
            if self.scenario == "ready":
                self.mark_notification_read()
            else:
                self.checks.append("pending-is-not-delivered")

    def mark_notification_read(self):
        from native_input_evidence import active_window_id
        from profile_scroll import visible_resource

        original_window = active_window_id(self.probe.tree())
        self.probe.tap(SYNTHETIC_LIMIT_CHANGE, "workspace-content", direction="start")
        self.probe.wait_for(lambda: active_window_id(self.probe.tree()) != original_window,
                            "Notification dialog did not become the active window")
        self.probe.tap("Отметить прочитанным", "workspace-content")
        self.probe.wait_for(lambda: active_window_id(self.probe.tree()) == original_window,
                            "Notification dialog did not close after acknowledgement")
        self.probe.reveal_resource(SYNTHETIC_LIMIT_STATE, "workspace-content")

        def acknowledged_event():
            tree = self.probe.tree()
            if active_window_id(tree) != original_window:
                return None
            node = visible_resource(tree, SYNTHETIC_LIMIT_STATE)
            return node if node is not None and "Прочитано" in labels(node) else None

        self.probe.wait_for(acknowledged_event, "The selected event did not change to read")
        self.checks.append("read-ack-same-event")

    def analysis(self):
        from analysis_ui_probe import exercise_analysis

        self.checks.extend(exercise_analysis(self.probe, self.scenario, self.observed))

    def assistant(self):
        if self.scenario == "empty":
            self.probe.reveal("С чего начнём?", "workspace-content")
            self.checks.append("no-invented-answer")
        else:
            self.probe.reveal(PARTIAL_ANSWER if self.scenario == "partial" else ANSWER, "workspace-content")
            if self.scenario == "partial":
                self.probe.reveal("Требует проверки: СИНТЕТИЧЕСКИЙ тест отсутствующего рейтинга", "workspace-content")
                self.checks.append("uncertainty-visible")
            else:
                self.ready_assistant()

    def reveal_prefix(self, prefix, *, checkable=False, suffix=""):
        for _ in range(24):
            tree = self.probe.tree()
            for node in tree.iter("node"):
                if _matches_business_control(node, prefix, checkable, suffix):
                    return node
            self.reader.scroll_list("workspace-content", "end")
            time.sleep(.15)
        raise AssertionError("Expected native business control is not visible: " + prefix)

    def ready_risk(self):
        from profile_ui_probe import checkable_label
        from profile_scroll import visible_resource

        self.probe.tap("Создать список проверок", "workspace-content")
        self.probe.reveal("Проверить: Синтетическая компания", "workspace-content", direction="start")
        control_id = "risk-check-synthetic-check-1-step-source"
        self.probe.reveal_resource(control_id, "workspace-content")

        def current_control():
            row = visible_resource(self.probe.tree(), control_id)
            return checkable_label(row, RISK_SOURCE_LABEL) if row is not None else None

        control = self.probe.wait_for(current_control,
                                      "Risk checklist has no native checkable control")
        if control.get("checkable") != "true" or control.get("checked") != "false":
            raise AssertionError("Risk checklist has no native unchecked state")
        # A scroll is asynchronous. Tap only this new record's control after
        # three stable frames, clipped to the current list viewport.
        self.probe.tap_resource(control_id, "workspace-content")
        self.probe.wait_for(lambda: (node if (node := current_control()) is not None and node.get("checked") == "true" else None),
                       "Risk checklist mutation was not confirmed")
        self.checks.extend(("concentration-threshold", "create-checklist", "confirm-reviewed-step"))
        from risk_scenario_probe import exercise_scenario_comparison
        self.scenario_comparison = exercise_scenario_comparison(self)
        self.checks.extend(("scenario-empty-input-blocked", "scenario-draft-survives-rotation",
                            "two-scenarios-one-baseline-exact-values"))

    def ready_assistant(self):
        from impact_ui_probe import exercise_impact
        from native_input_evidence import (empty_editor_focused, keyboard_visible,
                                          record_editor_restore_trace, rotate_focused_draft)
        from chat_recovery_ui_probe import exercise_chat_recovery

        self.impact_screenshot = "business-assistant-impact" + ("-font-200" if math.isclose(self.font_scale, 2.0) else "")
        self.checks.extend(exercise_impact(self.probe, self.observed, self.impact_screenshot))
        self.probe.tap("Показать синтетическую позицию", "workspace-content")
        self.probe.wait_for(lambda observe=self.observed: (value if (value := observe())["navigation"] == "instrument:synthetic-stock::" else None), "Position evidence opened a different destination")
        self.probe.tap("Показать синтетическую дату", "workspace-content")
        self.probe.wait_for(lambda observe=self.observed: (value if (value := observe())["navigation"] == "history:synthetic-history:synthetic-account:2026-10-17T10:00:00Z" else None), "History evidence lost its date/account")
        self.probe.tap_resource("assistant-question", "assistant-composer", direction="start")
        def ready_editor():
            tree = self.probe.tree()
            return empty_editor_focused(tree) and keyboard_visible(tree)

        self.probe.wait_for(ready_editor, "Assistant question is not visible and focused above the keyboard")
        self.probe.command("shell", "input", "text", "UIprobe")
        rotation_name = "business-assistant-draft-rotation" + ("-font-200" if math.isclose(self.font_scale, 2.0) else "")
        self.draft_rotation = rotate_focused_draft(self.probe, "UIprobe", rotation_name)
        record_editor_restore_trace(self.probe, include_ime_history=True)
        self.checks.extend(("unsent-draft-survives-rotation", "native-input-focus-and-caret-retained"))
        self.probe.dismiss_keyboard()
        self.chat_recovery = exercise_chat_recovery(self.probe, self.observed)
        self.checks.extend(("exact-position-and-date-destinations", "native-chat-input", "estimate-and-send-contract",
                       "lost-response-blocks-repeat", "same-request-get-recovery-without-remount"))


def _control_labels(node):
    return [label for child in node.iter("node") if child.get("visible-to-user") != "false"
            for label in labels(child)]


def _matches_business_control(node, prefix, checkable, suffix):
    return (node.get("package") == "ru.omnicio.app.debug"
            and node.get("visible-to-user") != "false"
            and (not checkable or node.get("checkable") == "true")
            and any(label.startswith(prefix) and label.endswith(suffix) for label in _control_labels(node)))
