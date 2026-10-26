"""Precise native values, actual chart gestures and source-period contracts."""
from calendar import monthrange
from datetime import date, timedelta
import re
import time
import xml.etree.ElementTree as ET

from business_ui_probe import labels
from portfolio_research_probe import ACCOUNT_A
from profile_launch import PACKAGE
from profile_ui_probe import node_bounds

SELECTED_HISTORY_VALUE = '901,75 ₽'
DISCUSS_PERIOD = 'Обсудить этот период'


AREA = "workspace-content"
BOND = "synthetic-bond"
EXACT_MISSING = "Наблюдение с этим точным моментом не найдено в полученной выборке. Другая запись этого дня не подставляется. Возможно, детальная история уже вышла из срока хранения; проверьте источник и диапазон."


def quote_interval_target(tree, text, *, selected=False):
    """Scope an action or selected-state observation to the exact candle rail."""
    if text not in {"Час", "День", "Неделя", "Месяц"}:
        raise ValueError("Unsupported quote interval label")
    rows = [node for node in tree.iter("node") if node.get("package") == PACKAGE
            and node.get("visible-to-user") == "true"
            and node.get("resource-id") in {"quotes-intervals", PACKAGE + ":id/quotes-intervals"}]
    if len(rows) != 1:
        return None
    row = rows[0]
    x1, y1, x2, y2 = node_bounds(row)
    for node in row.iter("node"):
        required_state = "selected" if selected else "clickable"
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true" \
                or node.get(required_state) != "true" or node.get("enabled") == "false":
            continue
        if not any(text in labels(child) for child in node.iter("node") if child.get("visible-to-user") == "true"):
            continue
        left, top, right, bottom = node_bounds(node)
        left, top, right, bottom = max(left, x1), max(top, y1), min(right, x2), min(bottom, y2)
        if right - left >= 48 and bottom - top >= 48:
            target = ET.Element(node.tag, dict(node.attrib))
            target.set("bounds", f"[{left},{top}][{right},{bottom}]")
            return target
    return None


def _tap_interval(case, text, direction="end"):
    p = case.probe
    p.resource_tap_target("quotes-intervals", AREA, direction="start")
    reader = getattr(p.read_tree, "__self__", None)
    for _ in range(11):
        target = quote_interval_target(p.tree(), text)
        if target is not None:
            p.tap_node(target)
            p.wait_for(lambda: quote_interval_target(p.tree(), text, selected=True),
                       "Candle interval did not acquire its actual native selected state")
            return
        if not reader.scroll_list("quotes-intervals", direction):
            break
        time.sleep(.1)
    raise AssertionError("Candle interval is not reachable in its exact native rail: " + text)


def month_before(day):
    year, month = (day.year - 1, 12) if day.month == 1 else (day.year, day.month - 1)
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def range_description(node, prefix):
    matches = [text[len(prefix):] for text in labels(node) if text.startswith(prefix)]
    if len(matches) != 1 or re.fullmatch(r"\d{4}-\d{2}-\d{2}", matches[0]) is None:
        raise AssertionError("Native range handle has no single exact calendar date")
    return date.fromisoformat(matches[0])


def _range_handles(case):
    p = case.probe
    p.reveal_resource("history-range-selector", AREA)
    tree = p.tree()
    result = []
    for prefix in ("Начало периода: ", "Конец периода: "):
        found = [node for node in tree.iter("node")
                 if node.get("package") == PACKAGE and node.get("visible-to-user") == "true"
                 and any(text.startswith(prefix) for text in labels(node))]
        if len(found) != 1:
            raise AssertionError("Expected two distinct visible native range handles")
        node = found[0]
        result.append((node_bounds(node), range_description(node, prefix)))
    if result[0][1] > result[1][1]:
        raise AssertionError("Native range handles cross calendar boundaries")
    return result


def _drag_range(case):
    p = case.probe
    p.tap("Выбрать две границы", AREA)
    (start_box, first), (end_box, last) = _range_handles(case)
    if (first, last) != (case.history_start, case.history_end):
        raise AssertionError("Range control did not start from the actual received history")
    start_x, end_x = (start_box[0] + start_box[2]) // 2, (end_box[0] + end_box[2]) // 2
    if end_x - start_x < 100:
        raise AssertionError("The actual range control has insufficient usable width")
    y = (start_box[1] + start_box[3]) // 2
    p.command("shell", "input", "swipe", str(start_x), str(y), str(start_x + (end_x - start_x) * 4 // 13), str(y), "600")
    (_, chosen_start), (end_box, same_end) = _range_handles(case)
    if not first < chosen_start < last or same_end != last:
        raise AssertionError("Dragging the start handle changed the wrong date boundary")
    y = (end_box[1] + end_box[3]) // 2
    p.command("shell", "input", "swipe", str((end_box[0] + end_box[2]) // 2), str(y),
              str(start_x + (end_x - start_x) * 9 // 13), str(y), "600")
    (_, final_start), (_, chosen_end) = _range_handles(case)
    if final_start != chosen_start or not chosen_start < chosen_end < last:
        raise AssertionError("Dragging the end handle changed the wrong date boundary")
    p.reveal(f"{chosen_start} — {chosen_end}", AREA, direction="start")
    p.tap("Показать статистику диапазона", AREA)
    params = {"start": str(chosen_start), "end": str(chosen_end), "currency": "RUB"}
    case.call("/tinvest/accounts/" + ACCOUNT_A + "/analytics", params)
    case.extra["range"] = {"initial_start": str(first), "initial_end": str(last), **params,
                           "input": "two actual native handle drags; observed dates"}
    case.capture("range")
    return params


def _select_history_bar(case, index, expected, *, direction="end"):
    p = case.probe
    chart = p.resource_tap_target("history-bars", AREA, direction=direction)
    left, top, right, bottom = node_bounds(chart)
    p.command("shell", "input", "tap", str(left + int((right - left) * (index + .5) / 14)), str((top + bottom) // 2))
    selected_day = case.history_start + timedelta(days=index)
    interval = f"Выбранный интервал: {selected_day} — {selected_day}"
    p.reveal(interval, AREA, direction="start")
    # The tooltip is above the chart. Its clipped bottom edge may expose the
    # description while the value is still above the viewport.
    p.reveal(expected, AREA, direction="start")
    records = [node for node in p.tree().iter("node") if node.get("package") == PACKAGE
               and node.get("visible-to-user") == "true" and interval in labels(node)]
    if len(records) != 1 or not any(expected in labels(child) for child in records[0].iter("node")
            if child.get("package") == PACKAGE and child.get("visible-to-user") == "true"):
        raise AssertionError("The selected history tooltip did not expose its exact interval value")


def exercise_history(case):
    p = case.probe
    path = "/tinvest/accounts/" + ACCOUNT_A + "/analytics"
    case.call(path, {"start": str(case.history_start), "end": str(case.history_end), "currency": "RUB", "history_resolution": "hour"})
    p.reveal("Точное наблюдение по ссылке", AREA)
    # The fixture's exact timestamp is 10:00 UTC, displayed in Moscow by the
    # real history screen; it is deliberately not the later close of that day.
    expected_time = (case.history_instant + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M:%S")
    p.reveal(expected_time, AREA)
    if case.scenario == "partial":
        p.reveal(EXACT_MISSING, AREA)
        p.reveal("Частота исходного наблюдения: часовая", AREA)
        p.reveal(SELECTED_HISTORY_VALUE, AREA)
        case.extra["exact_instant"] = {"time": case.before["history_instant"], "state": "missing",
                                       "same_day_close": "901.75", "replacement_rejected": True}
        return ["exact-instant-request", "missing-instant-not-substituted-by-same-day-close"]
    p.reveal("101.25 ₽", AREA)
    p.reveal("Частота исходного наблюдения: часовая", AREA)
    p.reveal(SELECTED_HISTORY_VALUE, AREA)
    case.capture("exact-observation")
    _select_history_bar(case, 10, SELECTED_HISTORY_VALUE)
    p.tap("Подробнее о графике", AREA)
    selected_row = p.reveal_resource("history-observation-10", AREA)
    close = case.history_instant.replace(hour=18, minute=0, second=0, microsecond=0)
    closing_label = "Выбрано · " + (close + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M:%S") + " · 901.75 ₽"
    # Compose exports Selected through checked/checkable for non-tab controls.
    native_selected = selected_row.get("selected") == "true" or (
        selected_row.get("checkable") == "true" and selected_row.get("checked") == "true")
    if not native_selected or closing_label not in [label for node in selected_row.iter("node") for label in labels(node)]:
        raise AssertionError("Selecting the daily bar did not select its exact closing observation in the native table")
    case.extra["bar_table_selection"] = {"native_resource": selected_row.get("resource-id"),
                                         "native_selected": selected_row.get("selected"), "native_checked": selected_row.get("checked"),
                                         "native_checkable": selected_row.get("checkable"), "exact_close": close.isoformat(),
                                         "visible_label": closing_label, "earlier_link_replaced_only_by_user_selection": True}
    p.tap("Подробнее о графике", AREA, direction="start")
    _select_history_bar(case, 4, "0,00 ₽", direction="start")
    _select_history_bar(case, 5, "-25,50 ₽")
    _select_history_bar(case, 7, "Нет наблюдений")
    p.reveal("За этот интервал снимков нет. Это не нулевой баланс.", AREA)
    case.capture("missing-observation")
    p.tap_resource("history-selection-reset", AREA, direction="start")
    params = _drag_range(case)
    for heading in ("Сравнить два периода", "События рядом с графиком", "Движение денег"):
        p.reveal(heading, AREA)
    p.reveal("Денежные потоки в исходных валютах. Это не расчёт инвестиционной прибыли.", AREA)
    p.tap("Обсудить выбранный период", AREA)
    p.find("Ассистент")
    expected = {"mode": "portfolio", "instrument_uid": None, "account_id": ACCOUNT_A,
                "start": params["start"], "end": params["end"], "event_id": None,
                "title": f"СИНТЕТИЧЕСКИЙ счёт A · {params['start']} — {params['end']}"}
    case.expect(lambda value: value["current_page"] == "assistant" and value["chat_context"] == expected,
                "Selected history dates did not reach the real assistant unchanged")
    case.call("/workspace/chat/threads/synthetic-portfolio-thread/messages", {})
    return ["exact-instant-versus-daily-close", "bar-selects-exact-closing-native-table-row", "zero-negative-and-missing-bars",
            "two-native-date-handle-drags", "cashflow-request-exact-selected-period",
            "cashflow-not-investment-return", "selected-period-opens-real-assistant"]


def _candle_query(case, interval, *, status=200, after=0):
    params = {"start": str(month_before(case.day)), "end": str(case.day), "interval": interval}
    return case.call("/workspace/instruments/" + BOND + "/candles", params, status=status, after=after)


def _first_candle(case):
    p = case.probe
    p.tap("Сбросить", AREA)
    p.tap("Следующая", AREA)
    p.reveal("98.125000001 / 98.375000001 % номинала", AREA, direction="start")
    for value in ("97.625000001 / 99.125000001 % номинала", "100 лотов"):
        p.reveal(value, AREA)


def exercise_quotes(case):
    p = case.probe
    p.tap("Котировки", "profile-tabs")
    _candle_query(case, "day")
    p.reveal(f"% номинала · {month_before(case.day)} — {case.day}", AREA)
    _first_candle(case)
    case.capture("exact-ohlc")
    p.tap("Сбросить", AREA)
    p.tap("Предыдущая", AREA, direction="start")
    p.reveal("Текущий интервал ещё формируется", AREA, direction="start")
    _tap_interval(case, "Неделя")
    failed = _candle_query(case, "week", status=503)
    p.reveal("СИНТЕТИЧЕСКИЙ источник временно недоступен. Повторите чтение выбранной недели.", AREA)
    p.reveal(f"Показана предыдущая выборка: {month_before(case.day)} · {case.day} · day. Новая ещё не получена.", AREA)
    from profile_ui_probe import button_label

    p.reveal(DISCUSS_PERIOD, AREA)
    blocked = p.wait_for(lambda: button_label(p.tree(), DISCUSS_PERIOD),
                         "Stale-period discussion has no native Button")
    if blocked.get("enabled") != "false":
        raise AssertionError("Stale candle period can be passed to the assistant as current")
    case.capture("stale-week")
    p.tap("Повторить запрос", AREA, direction="start")
    _candle_query(case, "week", after=failed["requests"])
    _tap_interval(case, "Месяц")
    _candle_query(case, "month")
    _tap_interval(case, "Час", direction="start")
    _candle_query(case, "hour")
    _first_candle(case)
    p.tap("Лупа выбранного интервала", AREA)
    p.reveal("Увеличенный фрагмент; локальная шкала цены.", AREA)
    case.capture("magnifier")
    p.tap("Точная таблица свечей", AREA)
    node = case.prefix("Выбрано · ")
    expected = "О 98.125000001 · В 99.125000001 · Н 97.625000001 · З 98.375000001"
    if expected not in labels(node):
        raise AssertionError("The selected native OHLC table rounded or changed the source quotation")
    p.tap(DISCUSS_PERIOD, AREA)
    p.find("Ассистент")
    start, end = str(month_before(case.day)), str(case.day)
    context = {"mode": "instrument", "instrument_uid": BOND, "account_id": ACCOUNT_A,
               "start": start, "end": end, "event_id": None, "title": f"SYN-BOND · {start} — {end}"}
    case.expect(lambda value: value["current_page"] == "assistant" and value["chat_context"] == context,
                "The real assistant lost the exact successful OHLC period or bond")
    case.call("/workspace/chat/threads/synthetic-portfolio-thread/messages", {})
    return ["exact-unrounded-ohlc-percent-of-nominal", "current-candle-incomplete",
            "failed-week-retains-explicit-old-period", "retry-completes-exact-week",
            "day-week-month-hour-source-requests", "hour-magnifier-and-native-table",
            "successful-period-opens-real-assistant"]
