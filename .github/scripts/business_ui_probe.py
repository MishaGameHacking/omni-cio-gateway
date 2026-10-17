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

ROUTES = ("risk", "assistant", "plans", "strategy", "notifications", "analysis")
CASES = tuple((route, scenario) for route in ROUTES
              for scenario in ("ready", "empty", "partial", "error", "job")
              if scenario != "job" or route in {"assistant", "plans"})
BANNER = "ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ"
ERROR = "Синтетический отказ источника. Настоящая сеть не вызывалась."
ANSWER = "СИНТЕТИЧЕСКИЙ ОТВЕТ: тестовая доля компании 70% сопоставлена с пользовательским лимитом 60%. Это проверка интерфейса, не инвестиционный совет."
PARTIAL_ANSWER = "СИНТЕТИЧЕСКИЙ ОТВЕТ: часть исходных сведений отсутствует; точный вывод не подтверждён."
UNCERTAIN = "Исход запроса к модели пока не подтверждён. Автоматического повторного запроса нет."
CONFIRM_VERSION = "Подтвердить эту версию"


def labels(node):
    return [part.strip() for value in (node.get("text", ""), node.get("content-desc", "")) for part in value.splitlines() if part.strip()]


def business_marker(tree, route, scenario):
    """Require exact fixture identity, its real request count and zero rejects."""
    if (route, scenario) not in CASES:
        raise ValueError("Unsupported business case")
    for node in tree.iter("node"):
        if node.get("package") != "ru.omnicio.app.debug" or node.get("visible-to-user") == "false":
            continue
        parts = dict(part.split(":", 1) for part in node.get("content-desc", "").split(";") if ":" in part)
        if parts.get("business-probe") != route + "/" + scenario or parts.get("transport") != "synthetic":
            continue
        if not re.fullmatch(r"\d+", parts.get("requests", "")) or not re.fullmatch(r"\d+", parts.get("contract-errors", "")):
            raise AssertionError("Invalid observed business transport counters")
        if int(parts["contract-errors"]):
            raise AssertionError("The real screen submitted an invalid fixture contract")
        if int(parts["requests"]) > 0:
            return {"route": route, "scenario": scenario, "requests": int(parts["requests"]),
                    "contract_errors": 0, "navigation": parts.get("navigation", "none"),
                    **chat_counters(parts, int(parts["requests"]), scenario)}
    return None


def exercise_business(probe):
    from persistent_ui import FrameReader
    from profile_launch import launch_profile
    from profile_ui_probe import matching_node
    from spatial_frame_evidence import ready_spatial_metrics
    from native_input_evidence import rotate_focused_draft
    from analysis_ui_probe import exercise_analysis
    from impact_ui_probe import exercise_impact
    from chat_recovery_ui_probe import exercise_chat_recovery

    reader = getattr(probe.read_tree, "__self__", None)
    if not isinstance(reader, FrameReader):
        raise ValueError("Business checks require the owned persistent frame session")
    records = []
    probe.command("shell", "settings", "put", "system", "font_scale", "1.0")

    def reveal_prefix(prefix, *, checkable=False, suffix=""):
        for _ in range(24):
            tree = probe.tree()
            for node in tree.iter("node"):
                if node.get("package") == "ru.omnicio.app.debug" and node.get("visible-to-user") != "false" \
                        and (not checkable or node.get("checkable") == "true") \
                        and any(label.startswith(prefix) and label.endswith(suffix) for label in labels(node)):
                    return node
            reader.scroll_list("workspace-content", "end")
            time.sleep(.15)
        raise AssertionError("Expected native business control is not visible: " + prefix)

    for font_scale, (route, scenario) in ((scale, case) for scale in (1.0, 2.0) for case in CASES):
        probe.command("shell", "settings", "put", "system", "font_scale", str(font_scale))
        print(f"BUSINESS_UI_CASE={route}/{scenario};font={font_scale}", flush=True)
        launch_profile(probe.command, probe.tree, probe.wait_for, expected_screen="business-" + route, scenario=scenario)
        probe.find(BANNER)

        def observed(route=route, scenario=scenario):
            return probe.wait_for(lambda: business_marker(probe.tree(), route, scenario), "Business fixture did not complete an actual request")

        before = observed()
        checks = []
        draft_rotation = None
        impact_screenshot = None
        chat_recovery = None
        if scenario == "error":
            probe.reveal("Не удалось обновить", "workspace-content")
            probe.reveal(ERROR, "workspace-content")
            baseline = observed()["requests"]
            probe.tap("Повторить", "workspace-content")
            probe.wait_for(lambda observe=observed, minimum=baseline: (value if (value := observe())["requests"] > minimum else None),
                           "Retry did not issue a new synthetic transport request")
            probe.reveal(ERROR, "workspace-content")
            checks.extend(("explicit-source-error", "retry-real-request"))
        elif scenario == "job":
            probe.tap("Сохранённые задания · 1", "workspace-content")
            probe.tap_resource("recover-request-synthetic-request", "workspace-content")
            probe.reveal("Исход требует сверки", "workspace-content", direction="start")
            probe.reveal(UNCERTAIN, "workspace-content")
            if matching_node(probe.tree(), "Повторить разрешённую задачу") is not None:
                raise AssertionError("Unknown paid request exposes an unsafe repeat action")
            checks.extend(("saved-request-recovered", "uncertain-not-repeated"))
        elif route == "risk":
            if scenario == "empty":
                probe.reveal("Покрытие пока не получено", "workspace-content")
                checks.append("missing-coverage-explicit")
            else:
                probe.reveal("Подтверждено " + ("1" if scenario == "partial" else "2") + " из 3 позиций", "workspace-content")
                probe.tap("Концентрация", "profile-tabs")
                probe.reveal("Синтетическая компания", "workspace-content")
                probe.reveal("Доля не получена" if scenario == "partial" else "Лимит превышен", "workspace-content")
                if scenario == "partial":
                    probe.reveal("Сопоставление с лимитом не подтверждено", "workspace-content")
                    probe.tap("История", "profile-tabs")
                    probe.reveal("Синтетический рейтинг: свежесть не подтверждена", "workspace-content")
                    probe.reveal("Новых подтверждённых данных недостаточно. Это событие не означает, что риск устранён.", "workspace-content")
                    checks.extend(("unknown-share-not-zero", "stale-rating-not-resolved"))
                else:
                    probe.tap("Создать список проверок", "workspace-content")
                    probe.reveal("Проверить: Синтетическая компания", "workspace-content", direction="start")
                    control = probe.reveal("Открыть синтетический источник", "workspace-content")
                    if control.get("checkable") != "true" or control.get("checked") != "false":
                        raise AssertionError("Risk checklist has no native unchecked state")
                    probe.tap_node(control)
                    probe.wait_for(lambda: (node if (node := matching_node(probe.tree(), "Открыть синтетический источник")) is not None and node.get("checked") == "true" else None),
                                   "Risk checklist mutation was not confirmed")
                    checks.extend(("concentration-threshold", "create-checklist", "confirm-reviewed-step"))
        elif route == "strategy":
            if scenario == "empty":
                probe.reveal("Правила ещё не подтверждены", "workspace-content")
                checks.append("inactive-rules-explicit")
            else:
                probe.reveal("Действует версия 3", "workspace-content")
                probe.tap("Рассчитать влияние", "workspace-content")
                probe.reveal("Влияние на текущий портфель", "workspace-content")
                if scenario == "partial":
                    probe.reveal("Тест: источник части связей отсутствует; применение недоступно.", "workspace-content")
                    confirm = probe.reveal(CONFIRM_VERSION, "workspace-content")
                    if confirm.get("enabled") != "false":
                        raise AssertionError("Incomplete strategy preview can be confirmed")
                    checks.append("incomplete-preview-blocks-confirm")
                else:
                    probe.tap(CONFIRM_VERSION, "workspace-content")
                    probe.reveal("Действует версия 4", "workspace-content", direction="start")
                    probe.tap("Версии", "profile-tabs")
                    probe.reveal("Версия 2", "workspace-content")
                    probe.tap("Проверить возврат к этой версии", "workspace-content")
                    probe.reveal("Влияние на текущий портфель", "workspace-content")
                    probe.tap(CONFIRM_VERSION, "workspace-content")
                    probe.reveal("Действует версия 5", "workspace-content", direction="start")
                    checks.extend(("preview-before-confirm", "new-confirmed-version", "rollback-creates-new-version"))
        elif route == "plans":
            if scenario == "empty":
                probe.reveal("Планов пока нет", "workspace-content")
                checks.append("empty-plans-explicit")
            else:
                probe.reveal("СИНТЕТИЧЕСКИЙ ПЛАН · акция", "workspace-content")
                if scenario == "partial":
                    probe.reveal("Подтверждена часть количества", "workspace-content")
                    probe.reveal("Сверено по операциям: 2 ед.", "workspace-content")
                    # The only unbound synthetic operation has three units.
                    control = reveal_prefix("", checkable=True, suffix=" · 3 ед.")
                    if not any("3 ед." in label for label in labels(control)):
                        raise AssertionError("Unexpected reconciliation operation")
                    probe.tap_node(control)
                    probe.tap("Подтвердить связь выбранных операций", "workspace-content")
                    probe.reveal("Сверено по операциям: 5 ед.", "workspace-content", direction="start")
                    probe.reveal("Источник операций пока неполный. Итог исполнения не подтверждён.", "workspace-content")
                    checks.extend(("real-partial-quantity", "bind-selected-operation", "incomplete-source-remains-explicit"))
                else:
                    probe.reveal("Расчёт подготовлен", "workspace-content")
                    probe.tap("Подготовить план", "workspace-content", direction="start")
                    probe.tap("Синтетическая акция", "workspace-content")
                    probe.tap("Количество единиц инструмента", "workspace-content")
                    probe.command("shell", "input", "text", "5")
                    probe.command("shell", "input", "keyevent", "BACK")
                    probe.tap("Проверить и сохранить расчёт", "workspace-content")
                    probe.reveal("СИНТЕТИЧЕСКИЙ РАСЧЁТ", "workspace-content")
                    probe.reveal("План: 5 ед. · лот 1", "workspace-content")
                    checks.extend(("native-quantity-input", "new-confirmed-calculation"))
        elif route == "notifications":
            if scenario == "empty":
                probe.reveal("Новых событий пока нет", "workspace-content")
                checks.append("empty-events-explicit")
            else:
                probe.reveal("Синтетическое изменение лимита", "workspace-content")
                probe.reveal("Ожидает подходящего времени" if scenario == "partial" else "Устройство сообщило о показе", "workspace-content")
                if scenario == "ready":
                    probe.tap("Синтетическое изменение лимита", "workspace-content")
                    probe.tap("Отметить прочитанным", "workspace-content")
                    node = probe.reveal("Синтетическое изменение лимита", "workspace-content")
                    if "Прочитано" not in labels(node):
                        raise AssertionError("The selected event did not change to read")
                    checks.append("read-ack-same-event")
                else:
                    checks.append("pending-is-not-delivered")
        elif route == "analysis":
            checks.extend(exercise_analysis(probe, scenario, observed))
        elif route == "assistant":
            if scenario == "empty":
                probe.reveal("С чего начнём?", "workspace-content")
                checks.append("no-invented-answer")
            else:
                probe.reveal(PARTIAL_ANSWER if scenario == "partial" else ANSWER, "workspace-content")
                if scenario == "partial":
                    probe.reveal("Требует проверки: СИНТЕТИЧЕСКИЙ тест отсутствующего рейтинга", "workspace-content")
                    checks.append("uncertainty-visible")
                else:
                    impact_screenshot = "business-assistant-impact" + ("-font-200" if math.isclose(font_scale, 2.0) else "")
                    checks.extend(exercise_impact(probe, observed, impact_screenshot))
                    probe.tap("Показать синтетическую позицию", "workspace-content")
                    probe.wait_for(lambda observe=observed: (value if (value := observe())["navigation"] == "instrument:synthetic-stock::" else None), "Position evidence opened a different destination")
                    probe.tap("Показать синтетическую дату", "workspace-content")
                    probe.wait_for(lambda observe=observed: (value if (value := observe())["navigation"] == "history:synthetic-history:synthetic-account:2026-10-17T10:00:00Z" else None), "History evidence lost its date/account")
                    probe.tap_visible("Ваш вопрос")
                    probe.command("shell", "input", "text", "UIprobe")
                    rotation_name = "business-assistant-draft-rotation" + ("-font-200" if math.isclose(font_scale, 2.0) else "")
                    draft_rotation = rotate_focused_draft(probe, "UIprobe", rotation_name)
                    checks.extend(("unsent-draft-survives-rotation", "native-input-focus-and-caret-retained"))
                    probe.command("shell", "input", "keyevent", "BACK")
                    chat_recovery = exercise_chat_recovery(probe, observed)
                    checks.extend(("exact-position-and-date-destinations", "native-chat-input", "estimate-and-send-contract",
                                   "lost-response-blocks-repeat", "same-request-get-recovery-without-remount"))
        actual = observed()
        renderer = probe.wait_for(lambda: ready_spatial_metrics(probe.tree()), "Business screen did not render its genuine meshes")
        if not math.isclose(renderer.get("font-scale", 0.0), font_scale, rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError("The actual Compose font scale differs from the requested accessibility scenario")
        name = "business-" + route + "-" + scenario + ("-font-200" if math.isclose(font_scale, 2.0) else "")
        probe.capture(name)
        records.append({"case": route + "/" + scenario, "font_scale": font_scale, "before": before, "after": actual,
                        "checks": checks, "native_input_rotation": draft_rotation,
                        "chat_recovery": chat_recovery,
                        "impact_screenshot": impact_screenshot + ".png" if impact_screenshot else None,
                        "renderer": renderer, "screenshot": name + ".png"})
        print("BUSINESS_UI_CASE_PASSED=" + route + "/" + scenario + ";font=" + str(font_scale), flush=True)

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
