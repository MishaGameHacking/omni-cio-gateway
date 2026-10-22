"""Observe the production hypothesis panel without treating it as a fact."""

import xml.etree.ElementTree as ET

from profile_scroll import PACKAGE, _visible_app_node, tappable_resource, visible_resource

BASIS = "assistant-impact-basis"
CHANNEL = "assistant-impact-channel-0"
CHANNEL_SOURCES = "assistant-impact-channel-0-sources"
AREA = "workspace-content"
EXPANDED = "Развёрнуто"
COLLAPSED = "Свёрнуто"


def native_fold_state(tree, resource_id, expected_state):
    names = {resource_id, f"{PACKAGE}:id/{resource_id}"}
    matches = [node for node in tree.iter("node")
               if node.get("resource-id") in names and _visible_app_node(node)]
    if len(matches) != 1:
        return None
    target = matches[0]
    if (target.get("clickable") == "true"
            and target.get("enabled") == "true" and target.get("state-description") == expected_state):
        return target
    return None


def _fold_signature(tree, target, clipped):
    if target is None or clipped is None:
        return None
    display = [tree.get(name, "") for name in ("display-width", "display-height", "active-window-id")]
    if not all(value.isdecimal() and len(value) <= 6 for value in display):
        return None
    width, height, window = map(int, display)
    viewport = visible_resource(tree, AREA)
    if width <= 0 or height <= 0 or viewport is None:
        return None
    return (window, width, height, viewport.get("bounds"), target.get("bounds"), clipped.get("bounds"))


def wait_for_fold(probe, resource_id, expected_state, message):
    """Observe one completed native toggle before scrolling its changed layout.

    The next full-page accessibility scroll can skip a newly adjacent button if
    its first frame still describes the old expanded layout. Three fresh equal
    frames bind the state to settled visible geometry within the usual wait.
    No action, extra tap, or new timeout is introduced here.
    """
    previous, stable = None, 0

    def read():
        nonlocal previous, stable
        try:
            tree = probe.tree()
            target = native_fold_state(tree, resource_id, expected_state)
            clipped = tappable_resource(tree, resource_id, AREA) if target is not None else None
        except (RuntimeError, ET.ParseError, ValueError):
            previous, stable = None, 0
            raise
        signature = _fold_signature(tree, target, clipped)
        stable = stable + 1 if signature is not None and signature == previous else int(signature is not None)
        previous = signature
        return target if stable >= 3 else None

    return probe.wait_for(read, message)


def exercise_impact(probe, observed, screenshot):
    area = AREA
    probe.reveal("Гипотеза влияния ИИ", area)
    probe.reveal("Возможный механизм, предпосылки и неопределённость. Причинное влияние на цену не установлено.", area)
    probe.tap("Публикация, компания и мои позиции", area)
    wait_for_fold(probe, BASIS, EXPANDED, "The hypothesis basis fold did not expand")
    probe.reveal("СИНТЕТИЧЕСКОЕ событие влияния", area)
    probe.reveal("СИНТЕТИЧЕСКИЙ эмитент гипотезы", area)
    probe.tap_resource("assistant-impact-position", area)
    probe.wait_for(lambda: (value if (value := observed())["navigation"] == "instrument:synthetic-stock:synthetic-account:" else None),
                   "Hypothesis position lost its exact account or instrument")
    probe.tap("Публикация, компания и мои позиции", area, direction="start")
    wait_for_fold(probe, BASIS, COLLAPSED, "The hypothesis basis fold did not collapse")
    probe.tap("Возможный канал 1", area)
    wait_for_fold(probe, CHANNEL, EXPANDED, "The hypothesis channel fold did not expand")
    for text in ("СИНТЕТИЧЕСКИЙ канал: издержки компании могут измениться",
                 "Направление гипотезы: Недостаточно оснований для направления",
                 "Горизонт гипотезы: Не определён",
                 "1. СИНТЕТИЧЕСКОЕ допущение: компания использует затронутый ресурс",
                 "СИНТЕТИЧЕСКАЯ неопределённость: величина изменения не подтверждена"):
        probe.reveal(text, area)
    # The surrounding answer has another identically labelled source fold.
    # Open this channel's native toggle and observe its actual expanded state
    # before a subsequent scroll can move past the newly inserted metadata.
    probe.tap_resource(CHANNEL_SOURCES, area)
    wait_for_fold(probe, CHANNEL_SOURCES, EXPANDED, "The hypothesis channel source fold did not expand")
    probe.reveal("СИНТЕТИЧЕСКИЙ источник визуального теста", area)
    probe.capture(screenshot)
    probe.tap("Ограничения разбора", area)
    probe.reveal("СИНТЕТИЧЕСКИЙ пример: численное влияние не рассчитано", area)
    probe.reveal("Денежный эффект и доходность не рассчитаны. Разбор не создаёт торговое поручение.", area)
    return ["hypothesis-explicitly-separated-from-facts", "hypothesis-exact-owned-position",
            "hypothesis-channel-assumptions-uncertainty", "hypothesis-source-metadata",
            "uncomputed-financial-impact-explicit"]
