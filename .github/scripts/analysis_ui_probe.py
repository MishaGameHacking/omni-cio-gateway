"""Actual native timeline interactions; synthetic data stays in the debug APK."""
from __future__ import annotations

import time

CLOSE = "Закрыть"
CHECK_TITLE = "Сохранённая проверка"
COMPOSITION_REASON = "Причина: Изменился состав портфеля"
SOURCE = "СИНТЕТИЧЕСКИЙ источник проверки"
RUN = "Запустить проверку портфеля"


def observed_money_label(node, amount):
    """Accept only the expected native value, allowing Unicode grouping spaces."""
    if node.get("package") != "ru.omnicio.app.debug" or node.get("visible-to-user") == "false":
        return False
    expected = "Оценка:" + amount + "RUB"
    for value in (node.get("text", ""), node.get("content-desc", "")):
        if any(label.translate(str.maketrans("", "", " \u00a0\u202f")) == expected
               for label in value.splitlines()):
            return True
    return False


def _reveal_money(probe, amount):
    reader = probe.read_tree.__self__
    for _ in range(24):
        if any(observed_money_label(node, amount) for node in probe.tree().iter("node")):
            return
        reader.scroll_list("workspace-content", "end")
        time.sleep(.15)
    raise AssertionError("Saved analysis value is not visible in its original RUB unit: " + amount)


def _more_requests(probe, observed, baseline):
    return probe.wait_for(lambda: (value if (value := observed())["requests"] > baseline else None),
                          "Timeline did not load the selected saved resource")


def _navigation(probe, observed, destination):
    probe.wait_for(lambda: (value if (value := observed())["navigation"] == destination else None),
                   "Timeline evidence opened a different report, instrument or account")


def exercise_analysis(probe, scenario, observed):
    """Open production slot/check/history/diff dialogs through their native UI."""
    area = "workspace-content"
    if scenario in {"empty", "partial"}:
        probe.reveal("Подтверждённых запусков ещё нет.", area)
        if scenario == "empty":
            probe.reveal("Сохранённых проверок пока нет.", area)
            probe.reveal("Для сравнения нужны два сохранённых вывода.", area)
            checks = ["no-invented-run-or-comparison"]
        else:
            probe.reveal("Причина: С прошлого анализа прошло недостаточно времени", area)
            probe.reveal("Проверка условий не создала новый вывод модели.", area)
            probe.reveal("Платные обращения приостановлены.", area)
            probe.reveal("Модель пока недоступна: достигнут лимит расхода", area)
            checks = ["cooldown-not-new-analysis", "unresolved-cost-blocks-paid-run"]
        if probe.reveal(RUN, area).get("enabled") != "false":
            raise AssertionError("Unavailable analysis exposes an enabled paid-run action")
        return checks + ["unavailable-run-disabled"]
    if scenario != "ready":
        raise ValueError("Timeline ready/empty/partial only; source error uses the common retry contract")

    probe.reveal("Утренний и вечерний результаты", area)
    probe.reveal("Вывод сохранён", area)
    probe.tap("Открыть этот отчёт", area)
    _navigation(probe, observed, "report:synthetic-analysis")
    baseline = observed()["requests"]
    probe.tap_resource("analysis-check-synthetic-monitor-check", area)
    probe.find(CHECK_TITLE)
    probe.reveal(COMPOSITION_REASON, area)
    probe.tap("Наблюдения, на которых принято решение", area)
    probe.tap("Синтетическое изменение позиции", area)
    probe.reveal("Предыдущее наблюдение", area)
    _reveal_money(probe, "1000")
    probe.reveal("Новое наблюдение", area)
    _reveal_money(probe, "1100")
    probe.tap("Основания (1)", area)
    probe.reveal(SOURCE, area)
    probe.tap("Показать связанную позицию", area)
    probe.tap(CLOSE, area)
    # Native dialogs obscure the marker behind their window; inspect it after close.
    _more_requests(probe, observed, baseline)
    _navigation(probe, observed, "instrument:synthetic-stock:synthetic-account:")

    probe.reveal("Новый анализ не требовался", area)
    probe.reveal("Основание: В подтверждённом календаре нет торговой сессии", area)
    baseline = observed()["requests"]
    probe.tap_resource("analysis-check-synthetic-evening-check", area)
    probe.find(CHECK_TITLE)
    probe.reveal("Причина: В подтверждённом календаре нет торговой сессии", area)
    probe.reveal("Проверка условий не создала новый вывод модели.", area)
    probe.tap(CLOSE, area)
    _more_requests(probe, observed, baseline)

    probe.tap("Последние проверки · 1", area)
    baseline = observed()["requests"]
    probe.tap("Основания этой проверки", area)
    probe.find(CHECK_TITLE)
    probe.reveal(COMPOSITION_REASON, area)
    probe.tap(CLOSE, area)
    _more_requests(probe, observed, baseline)

    baseline = observed()["requests"]
    probe.tap("Сравнить факты портфеля", area)
    probe.find("Сравнение наблюдений")
    probe.tap("Изменилось · position", area)
    probe.reveal("Было", area)
    _reveal_money(probe, "1000")
    probe.reveal("Стало", area)
    _reveal_money(probe, "1100")
    probe.reveal("Время или источник наблюдения изменились.", area)
    probe.tap("Основания (1)", area)
    probe.reveal(SOURCE, area)
    probe.tap(CLOSE, area)
    _more_requests(probe, observed, baseline)
    return ["morning-report-exact-id", "saved-check-loaded", "saved-source-and-account-destination",
            "closed-evening-not-paid-analysis", "past-check-loaded", "fact-diff-1000-to-1100-rub",
            "source-change-distinct-from-value"]
