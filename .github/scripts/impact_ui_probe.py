"""Observe the production hypothesis panel without treating it as a fact."""

from profile_scroll import visible_resource

CHANNEL_SOURCES = "assistant-impact-channel-0-sources"


def expanded_channel_sources(tree):
    target = visible_resource(tree, CHANNEL_SOURCES)
    if (target is not None and target.get("clickable") == "true"
            and target.get("enabled") == "true" and target.get("state-description") == "Развёрнуто"):
        return target
    return None


def exercise_impact(probe, observed, screenshot):
    area = "workspace-content"
    probe.reveal("Гипотеза влияния ИИ", area)
    probe.reveal("Возможный механизм, предпосылки и неопределённость. Причинное влияние на цену не установлено.", area)
    probe.tap("Публикация, компания и мои позиции", area)
    probe.reveal("СИНТЕТИЧЕСКОЕ событие влияния", area)
    probe.reveal("СИНТЕТИЧЕСКИЙ эмитент гипотезы", area)
    probe.tap_resource("assistant-impact-position", area)
    probe.wait_for(lambda: (value if (value := observed())["navigation"] == "instrument:synthetic-stock:synthetic-account:" else None),
                   "Hypothesis position lost its exact account or instrument")
    probe.tap("Публикация, компания и мои позиции", area, direction="start")
    probe.tap("Возможный канал 1", area)
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
    probe.wait_for(lambda: expanded_channel_sources(probe.tree()),
                   "The hypothesis channel source fold did not expand")
    probe.reveal("СИНТЕТИЧЕСКИЙ источник визуального теста", area)
    probe.capture(screenshot)
    probe.tap("Ограничения разбора", area)
    probe.reveal("СИНТЕТИЧЕСКИЙ пример: численное влияние не рассчитано", area)
    probe.reveal("Денежный эффект и доходность не рассчитаны. Разбор не создаёт торговое поручение.", area)
    return ["hypothesis-explicitly-separated-from-facts", "hypothesis-exact-owned-position",
            "hypothesis-channel-assumptions-uncertainty", "hypothesis-source-metadata",
            "uncomputed-financial-impact-explicit"]
