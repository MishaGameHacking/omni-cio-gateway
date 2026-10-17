"""Observe the production hypothesis panel without treating it as a fact."""


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
    # The basis fold is closed, so the next source fold belongs to this
    # expanded mechanism, rather than to an unrelated earlier company.
    probe.tap("Основания (1)", area)
    probe.reveal("СИНТЕТИЧЕСКИЙ источник визуального теста", area)
    probe.capture(screenshot)
    probe.tap("Ограничения разбора", area)
    probe.reveal("СИНТЕТИЧЕСКИЙ пример: численное влияние не рассчитано", area)
    probe.reveal("Денежный эффект и доходность не рассчитаны. Разбор не создаёт торговое поручение.", area)
    return ["hypothesis-explicitly-separated-from-facts", "hypothesis-exact-owned-position",
            "hypothesis-channel-assumptions-uncertainty", "hypothesis-source-metadata",
            "uncomputed-financial-impact-explicit"]
