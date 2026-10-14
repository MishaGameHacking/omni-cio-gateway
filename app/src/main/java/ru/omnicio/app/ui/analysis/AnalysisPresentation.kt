package ru.omnicio.app.ui.analysis

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.roundToInt

/** These messages describe a server reply, never infer completion from queue acceptance. */
internal fun refreshDescription(state: String, model: String?): String = when (state) {
    "queued", "coalesced" -> "Запрос принят в очередь. Проверка ещё не завершена; результат появится после обработки."
    "running", "in_progress" -> "Проверка выполняется. Это ещё не результат анализа."
    "completed" -> model?.takeIf(String::isNotBlank)?.let { "Анализ завершён. Модель: $it." }
        ?: "Проверка завершена. Использование модели этим ответом не подтверждено."
    "fallback" -> "Получен алгоритмический вывод. Проверьте его ограничения и источники в карточке."
    "skipped" -> "Новый расширенный анализ не выполнялся. Это не подтверждение отсутствия риска."
    "disabled" -> "Фоновая обработка отключена. Запрос не означает выполненную проверку."
    else -> "Сервер не подтвердил завершение проверки. Обновите ленту позже."
}

internal fun ideasHeading(state: String): String = when (state) {
    "ready" -> "Есть направления для выравнивания"
    "balanced" -> "Структура близка к целевой"
    "profile_required" -> "Нужен инвестиционный профиль"
    "portfolio_required" -> "Нужен актуальный портфель"
    "no_excess_cash" -> "Свободный резерв не превышен"
    else -> "Состояние проверки не подтверждено"
}

internal fun analysisPercent(value: Double): String = if (value.isFinite())
    String.format(Locale.forLanguageTag("ru-RU"), "%.1f%%", value) else "нет данных"

/** Material Slider.steps excludes endpoints: 5..60 by 5 has ten internal stops. */
internal fun profileSliderSteps(range: ClosedFloatingPointRange<Float>): Int {
    require(range.start.isFinite() && range.endInclusive.isFinite())
    val span = range.endInclusive - range.start
    require(range.start >= 0 && span >= 5 && range.endInclusive <= 100 && span % 5f == 0f)
    return (span / 5f).toInt() - 1
}

/** Snap only a new user gesture; loading a fractional saved limit must not rewrite it. */
internal fun selectedProfilePercent(value: Float, range: ClosedFloatingPointRange<Float>): Double {
    profileSliderSteps(range)
    require(value.isFinite())
    val bounded = value.coerceIn(range)
    return (range.start + ((bounded - range.start) / 5f).roundToInt() * 5f).coerceIn(range).toDouble()
}

internal fun profileLimitsValid(position: Double, cash: Double): Boolean =
    position.isFinite() && cash.isFinite() && position in 5.0..60.0 && cash in 0.0..50.0

internal fun analysisTime(raw: String?, zone: ZoneId = ZoneId.systemDefault()): String? = runCatching {
    DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm z", Locale.forLanguageTag("ru-RU"))
        .withZone(zone).format(Instant.parse(raw))
}.getOrNull()

internal fun insightValidity(created: String, validUntil: String?, now: Instant): String {
    val checked = runCatching { Instant.parse(created) }.getOrNull()
    if (checked == null || checked > now) return "Время проверки не подтверждено. Не считайте вывод актуальным."
    val expiry = runCatching { Instant.parse(validUntil) }.getOrNull()
        ?: return "Срок актуальности не указан. Перед решением проверьте свежие данные."
    if (expiry <= checked) return "Срок актуальности некорректен. Нужна новая проверка."
    if (expiry <= now) return "Срок актуальности истёк. Это предыдущий вывод, нужна новая проверка."
    return "Срок проверки: до ${analysisTime(validUntil)}. Это не гарантия неизменности ситуации."
}
