package ru.omnicio.app.ui

import java.math.BigDecimal
import java.math.MathContext
import java.text.NumberFormat
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

internal data class HistoryPoint(val at: Instant, val value: BigDecimal?, val complete: Boolean)
internal data class SourceInfo(val name: String, val url: String?, val at: String?, val status: String?)

internal fun money(value: BigDecimal?, hidden: Boolean = false, currency: String = "RUB"): String {
    if (hidden) return "••••"
    if (value == null) return "Нет данных"
    val formatted = NumberFormat.getNumberInstance(Locale.forLanguageTag("ru-RU")).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }.format(value)
    return "$formatted ${if (currency == "RUB") "₽" else currency}"
}

internal fun timestampLabel(value: String?): String {
    val instant = value?.let { runCatching { Instant.parse(it) }.getOrNull() } ?: return "Время не указано"
    return DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm z", Locale.forLanguageTag("ru-RU"))
        .withZone(ZoneId.systemDefault()).format(instant)
}

internal fun chartFraction(value: BigDecimal, min: BigDecimal, max: BigDecimal): Float =
    if (max.compareTo(min) == 0) 0.5f else value.subtract(min).divide(max.subtract(min), MathContext.DECIMAL64)
        .toFloat().coerceIn(0f, 1f)

internal fun statusLabel(status: String?): String = when (status) {
    "fresh", "observed", "complete" -> "Данные получены"
    "stale" -> "Данные устарели"
    "partial" -> "Неполные данные"
    "pending" -> "Ожидаем данные"
    "not_connected" -> "Счёт не подключён"
    else -> "Нет подтверждённых данных"
}
