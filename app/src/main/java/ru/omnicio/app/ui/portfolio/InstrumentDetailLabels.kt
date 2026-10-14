package ru.omnicio.app.ui.portfolio

import java.util.Locale

/** Labels only: never infer a price, yield, rating or broker action. */
internal data class InstrumentDetailLabels(
    val type: String,
    val quantity: String,
    val accrued: String?,
)

internal fun instrumentDetailLabels(type: String, hasAccrued: Boolean): InstrumentDetailLabels {
    val kind = type.trim().lowercase(Locale.ROOT)
    val label = when (kind) {
        "cash" -> "Деньги"
        "currency" -> "Валюта"
        "share" -> "Акция"
        "bond" -> "Облигация"
        "etf" -> "Фонд"
        "future" -> "Фьючерс"
        "option" -> "Опцион"
        else -> "Тип не определён"
    }
    val quantity = when (kind) {
        "cash", "currency" -> "Количество, единиц валюты"
        "share", "bond", "etf" -> "Количество, шт."
        else -> "Количество по данным брокера"
    }
    val accrued = when {
        kind == "bond" -> "НКД на одну облигацию"
        hasAccrued -> "Начисленный доход (данные API)"
        else -> null
    }
    return InstrumentDetailLabels(label, quantity, accrued)
}
