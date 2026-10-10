package ru.omnicio.app.ui

private const val T_INVEST_PUBLIC_URL = "https://www.tbank.ru/invest/"
private const val OPEN_POSITION_LABEL = "Открыть позицию"

internal enum class AssistantEventType(val label: String) {
    MATERIAL_EVENT("Существенное событие"),
    RISK_CHANGE("Изменение риска"),
    PAYOUT("Выплата"),
    CASH_CHANGE("Доступные деньги"),
    SCENARIO_RESULT("Результат сценария"),
    ANALYSIS_STALE("Анализ устарел"),
    SYNC_REQUIRED("Нужна синхронизация"),
}

internal enum class AssistantActionKind {
    OPEN_SOURCE,
    OPEN_POSITION,
    RUN_SCENARIO,
    SYNC,
}

internal enum class AssistantImpactUnit {
    MONEY_MINOR,
    BASIS_POINTS,
    MINUTES,
}

internal data class AssistantImpact(
    val value: Long,
    val unit: AssistantImpactUnit,
    val currency: DisplayCurrency = DisplayCurrency.RUB,
)

internal data class AssistantSource(
    val name: String,
    val url: String?,
)

internal data class AssistantAction(
    val kind: AssistantActionKind,
    val label: String,
    val target: String?,
)

internal data class AssistantRawEvent(
    val eventKey: String,
    val revision: Int,
    val type: AssistantEventType,
    val changed: String,
    val relevance: String,
    val impact: AssistantImpact?,
    val sources: List<AssistantSource>,
    val occurredAt: String,
    val action: AssistantAction?,
    val sufficientData: Boolean = true,
)

internal data class AssistantMessage(
    val eventKey: String,
    val type: AssistantEventType,
    val changed: String,
    val relevance: String,
    val impact: AssistantImpact?,
    val sources: List<AssistantSource>,
    val occurredAt: String,
    val action: AssistantAction?,
    val sufficientData: Boolean,
)

internal data class AssistantPushPreview(
    val title: String,
    val body: String,
)

internal fun assistantFeed(
    rawEvents: List<AssistantRawEvent> = assistantRawFixture(),
): List<AssistantMessage> {
    val latestByEvent = linkedMapOf<String, AssistantRawEvent>()
    rawEvents.forEach { event ->
        val current = latestByEvent[event.eventKey]
        if (current == null || event.revision >= current.revision) {
            latestByEvent[event.eventKey] = event
        }
    }

    return latestByEvent.values.map { event ->
        AssistantMessage(
            eventKey = event.eventKey,
            type = event.type,
            changed = event.changed,
            relevance = event.relevance,
            impact = if (event.sufficientData) event.impact else null,
            sources = event.sources,
            occurredAt = event.occurredAt,
            action = if (event.sufficientData) event.action else null,
            sufficientData = event.sufficientData,
        )
    }
}

internal fun formatAssistantImpact(impact: AssistantImpact?): String {
    if (impact == null) {
        return "Числовое влияние: недостаточно данных"
    }

    val value = when (impact.unit) {
        AssistantImpactUnit.MONEY_MINOR -> formatMoney(
            minorUnits = impact.value,
            currency = impact.currency,
            hidden = false,
        )
        AssistantImpactUnit.BASIS_POINTS -> signedNumber(impact.value) + " б.п."
        AssistantImpactUnit.MINUTES -> impact.value.toString() + " мин."
    }
    return "Числовое влияние: " + value
}

internal fun assistantPushPreview(message: AssistantMessage): AssistantPushPreview {
    val body = when (message.type) {
        AssistantEventType.MATERIAL_EVENT -> "Появилось существенное событие. Откройте OMNICIO для деталей."
        AssistantEventType.RISK_CHANGE -> "Изменился аналитический статус. Детали доступны внутри приложения."
        AssistantEventType.PAYOUT -> "Появилось новое событие по выплатам. Детали доступны внутри приложения."
        AssistantEventType.CASH_CHANGE -> "Изменилось состояние доступных денег. Откройте OMNICIO для деталей."
        AssistantEventType.SCENARIO_RESULT -> "Локальный сценарий завершён. Результат доступен внутри приложения."
        AssistantEventType.ANALYSIS_STALE -> "Часть анализа потеряла актуальность. Проверьте OMNICIO."
        AssistantEventType.SYNC_REQUIRED -> "Для актуальных данных требуется синхронизация в OMNICIO."
    }
    return AssistantPushPreview(
        title = "OMNICIO · важное обновление",
        body = body,
    )
}

private fun signedNumber(value: Long): String =
    if (value > 0L) "+$value" else value.toString()

private fun assistantRawFixture(): List<AssistantRawEvent> = listOf(
    AssistantRawEvent(
        eventKey = "issuer-sber-demo",
        revision = 1,
        type = AssistantEventType.MATERIAL_EVENT,
        changed = "Зафиксировано новое событие по эмитенту, но данных недостаточно для числовой оценки.",
        relevance = "Инструмент присутствует в локальном fixture-портфеле.",
        impact = null,
        sources = listOf(
            AssistantSource(
                name = "Общий источник эмитента · fixture",
                url = T_INVEST_PUBLIC_URL,
            ),
        ),
        occurredAt = "сегодня · 10:15 · fixture",
        action = AssistantAction(
            kind = AssistantActionKind.OPEN_POSITION,
            label = OPEN_POSITION_LABEL,
            target = "uid-sber-demo",
        ),
        sufficientData = false,
    ),
    AssistantRawEvent(
        eventKey = "risk-ofz-demo",
        revision = 1,
        type = AssistantEventType.RISK_CHANGE,
        changed = "Локальный risk/data status по ОФЗ требует внимания из-за устаревшей цены.",
        relevance = "Позиция занимает заметную долю локального fixture-портфеля.",
        impact = AssistantImpact(
            value = 80,
            unit = AssistantImpactUnit.BASIS_POINTS,
        ),
        sources = listOf(
            AssistantSource(
                name = "T-Invest bond fixture",
                url = T_INVEST_PUBLIC_URL,
            ),
        ),
        occurredAt = "сегодня · 09:40 · fixture",
        action = AssistantAction(
            kind = AssistantActionKind.OPEN_SOURCE,
            label = "Открыть источник",
            target = T_INVEST_PUBLIC_URL,
        ),
    ),
    AssistantRawEvent(
        eventKey = "payout-demo",
        revision = 1,
        type = AssistantEventType.PAYOUT,
        changed = "Обнаружена ожидаемая выплата по позиции.",
        relevance = "Выплата относится к инструменту из локального портфеля.",
        impact = AssistantImpact(
            value = 32_500,
            unit = AssistantImpactUnit.MONEY_MINOR,
        ),
        sources = listOf(
            AssistantSource(
                name = "Календарь выплат · fixture",
                url = null,
            ),
        ),
        occurredAt = "сегодня · 09:10 · fixture",
        action = AssistantAction(
            kind = AssistantActionKind.OPEN_POSITION,
            label = OPEN_POSITION_LABEL,
            target = "uid-ofz-26238-demo",
        ),
    ),
    AssistantRawEvent(
        eventKey = "payout-demo",
        revision = 2,
        type = AssistantEventType.PAYOUT,
        changed = "Ожидаемая выплата уточнена общим источником.",
        relevance = "Событие относится к той же локальной позиции и не создаётся повторно.",
        impact = AssistantImpact(
            value = 32_500,
            unit = AssistantImpactUnit.MONEY_MINOR,
        ),
        sources = listOf(
            AssistantSource(
                name = "Календарь выплат · fixture revision 2",
                url = null,
            ),
        ),
        occurredAt = "сегодня · 09:12 · fixture",
        action = AssistantAction(
            kind = AssistantActionKind.OPEN_POSITION,
            label = OPEN_POSITION_LABEL,
            target = "uid-ofz-26238-demo",
        ),
    ),
    AssistantRawEvent(
        eventKey = "cash-demo",
        revision = 1,
        type = AssistantEventType.CASH_CHANGE,
        changed = "Свободные деньги увеличились после локального обновления fixture.",
        relevance = "Доступные деньги показываются отдельно от общей стоимости портфеля.",
        impact = AssistantImpact(
            value = 1_500_000,
            unit = AssistantImpactUnit.MONEY_MINOR,
        ),
        sources = listOf(
            AssistantSource(
                name = "Локальный snapshot · fixture",
                url = null,
            ),
        ),
        occurredAt = "вчера · 18:30 · fixture",
        action = AssistantAction(
            kind = AssistantActionKind.RUN_SCENARIO,
            label = "Открыть локальный сценарий",
            target = "cash-change-demo",
        ),
    ),
    AssistantRawEvent(
        eventKey = "scenario-demo",
        revision = 1,
        type = AssistantEventType.SCENARIO_RESULT,
        changed = "Пользовательский сценарий завершён локальным deterministic code.",
        relevance = "Результат относится только к выбранному пользователем fixture-сценарию.",
        impact = AssistantImpact(
            value = -750_000,
            unit = AssistantImpactUnit.MONEY_MINOR,
        ),
        sources = listOf(
            AssistantSource(
                name = "Локальный scenario calculator · fixture",
                url = null,
            ),
        ),
        occurredAt = "вчера · 17:05 · fixture",
        action = AssistantAction(
            kind = AssistantActionKind.RUN_SCENARIO,
            label = "Повторить сценарий",
            target = "scenario-demo",
        ),
    ),
    AssistantRawEvent(
        eventKey = "stale-demo",
        revision = 1,
        type = AssistantEventType.ANALYSIS_STALE,
        changed = "Часть общей аналитики стала устаревшей.",
        relevance = "Старые данные не должны выглядеть как актуальные.",
        impact = AssistantImpact(
            value = 190,
            unit = AssistantImpactUnit.MINUTES,
        ),
        sources = listOf(
            AssistantSource(
                name = "Локальная отметка свежести · fixture",
                url = null,
            ),
        ),
        occurredAt = "сегодня · 08:50 · fixture",
        action = AssistantAction(
            kind = AssistantActionKind.SYNC,
            label = "Проверить синхронизацию",
            target = null,
        ),
    ),
    AssistantRawEvent(
        eventKey = "sync-demo",
        revision = 1,
        type = AssistantEventType.SYNC_REQUIRED,
        changed = "Последняя персональная синхронизация не подтверждена.",
        relevance = "Без свежего snapshot персональные расчёты ограничены.",
        impact = AssistantImpact(
            value = 240,
            unit = AssistantImpactUnit.MINUTES,
        ),
        sources = listOf(
            AssistantSource(
                name = "Локальное состояние синхронизации · fixture",
                url = null,
            ),
        ),
        occurredAt = "сегодня · 08:20 · fixture",
        action = AssistantAction(
            kind = AssistantActionKind.SYNC,
            label = "Проверить синхронизацию",
            target = null,
        ),
    ),
)
