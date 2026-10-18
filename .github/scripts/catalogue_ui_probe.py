"""Actual new-asset search and purchase-check UI, with synthetic network inputs."""
from native_input_evidence import focused_editor
from profile_ui_probe import button_label, matching_node

PURCHASE_ACTION = "Проверить ограничения"


def exercise_catalogue(case):
    probe, scenario = case.probe, case.scenario
    area = "workspace-content"
    if scenario == "empty":
        probe.reveal("Найдено: 0 · Данные: 2026-10-18T10:00:00Z", area)
        case.checks.append("empty-catalogue-does-not-invent-assets")
        return
    probe.tap_resource("catalogue-query", area)
    probe.command("shell", "input", "text", "new1")
    probe.wait_for(lambda: focused_editor(probe.tree(), "new1"), "Catalogue query did not reach the native editor")
    probe.dismiss_keyboard()
    probe.tap("Найти", area)
    probe.reveal("СИНТЕТИЧЕСКИЙ НОВЫЙ АКТИВ", area)
    probe.tap("Проверить покупку", area)
    probe.reveal(PURCHASE_ACTION, area)
    disabled = probe.wait_for(lambda: button_label(probe.tree(), PURCHASE_ACTION), "Missing purchase-check button")
    if disabled.get("enabled") != "false":
        raise AssertionError("A missing price permits a purchase check")
    probe.tap_resource("purchase-price", area, direction="start")
    probe.command("shell", "input", "text", "95")
    probe.wait_for(lambda: focused_editor(probe.tree(), "95"), "Purchase price did not reach the native editor")
    probe.dismiss_keyboard()
    probe.tap(PURCHASE_ACTION, area)
    expected = "Проверенные ограничения соблюдены" if scenario == "ready" else "Покупка не прошла проверку"
    probe.reveal(expected, area)
    probe.reveal("Расчёт сохранён: synthetic-purchase-check", area)
    if scenario == "partial":
        probe.reveal("Покупка затрагивает защищённый резерв.", area, direction="start")
    probe.tap_resource("purchase-price", area, direction="start")
    probe.command("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    probe.command("shell", "input", "text", "0")
    probe.wait_for(lambda: focused_editor(probe.tree(), "950"), "Edited purchase price did not change")
    probe.dismiss_keyboard()
    probe.reveal(PURCHASE_ACTION, area)
    if matching_node(probe.tree(), expected) is not None:
        raise AssertionError("Changed input retains the previous purchase result")
    probe.tap("Закрыть", area)
    case.checks.extend(("search-outside-current-holdings", "missing-price-blocked", "typed-purchase-request",
                        "constraint-result-shown", "edited-input-invalidates-result", "no-broker-order"))
