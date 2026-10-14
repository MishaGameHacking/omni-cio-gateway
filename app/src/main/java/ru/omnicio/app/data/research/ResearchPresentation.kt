package ru.omnicio.app.data.research

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

/** Previous data is explicitly stale on transport failure, and cleared on terminal failure. */
data class ResearchLoadState<T>(
    val data: T? = null,
    val error: String? = null,
    val loading: Boolean = false,
    val stale: Boolean = false,
) {
    fun start(): ResearchLoadState<T> = copy(loading = true)
    fun success(value: T): ResearchLoadState<T> = ResearchLoadState(data = value)
    fun failure(message: String, retryable: Boolean): ResearchLoadState<T> =
        ResearchLoadState(data = data.takeIf { retryable }, error = message, stale = retryable && data != null)
    fun stopped(): ResearchLoadState<T> = copy(loading = false)
}

data class ResearchPage(val first: Int, val endExclusive: Int, val page: Int, val pageCount: Int) {
    val hasPrevious: Boolean get() = page > 0
    val hasNext: Boolean get() = page + 1 < pageCount
}

/** At most ten eager cards inside the parent's LazyColumn item, never one hundred. */
fun researchPage(total: Int, requestedPage: Int, expanded: Boolean): ResearchPage {
    require(total in 0..100)
    if (!expanded) return ResearchPage(0, minOf(total, 3), 0, 1)
    val count = maxOf(1, (total + 9) / 10)
    val page = requestedPage.coerceIn(0, count - 1)
    return ResearchPage(page * 10, minOf(total, page * 10 + 10), page, count)
}

fun researchTime(raw: String?, zone: ZoneId = ZoneId.systemDefault()): String? = runCatching {
    val instant = Instant.parse(raw)
    DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm z", Locale.forLanguageTag("ru-RU"))
        .withZone(zone).format(instant)
}.getOrNull()

data class ResearchScenario(
    val breaches: Int, val paths: Int, val horizon: Int, val floor: Double,
    val lower: Double, val upper: Double,
) {
    val summary: String get() = "В $breaches из $paths сценариев капитал опускался ниже ${percent(floor)}% исходной суммы за $horizon торговых сессий."
    val interval: String get() = "Интервал только для случайности моделирования: ${percent(lower)}–${percent(upper)}%. Он не учитывает все ошибки модели и будущие кризисы."
    private fun percent(value: Double): String = String.format(Locale.forLanguageTag("ru-RU"), "%.2f", value * 100)
}

private fun finiteNumber(value: Any?): Double? = (value as? Number)?.toDouble()?.takeIf { it.isFinite() }
private fun count(value: Any?, range: IntRange): Int? {
    val exact = when (value) {
        is Int -> value.toLong()
        is Long -> value
        else -> return null
    }
    return exact.takeIf { it >= range.first && it <= range.last }?.toInt()
}

/** Accept only the server's documented conditional simulation, never a default probability. */
fun researchScenario(fields: Map<String, Any?>): ResearchScenario? {
    if (fields["method"] != "joint_moving_block_buy_and_hold_v1" ||
        fields["is_default_probability"] != false || fields["guarantee"] != false) return null
    val paths = count(fields["paths"], 100..5000) ?: return null
    val horizon = count(fields["horizon_sessions"], 1..252) ?: return null
    val floor = finiteNumber(fields["capital_floor"])?.takeIf { it > 0 && it < 1 } ?: return null
    val frequency = finiteNumber(fields["conditional_breach_frequency"])?.takeIf { it in 0.0..1.0 } ?: return null
    val bounds = fields["monte_carlo_interval_only"] as? List<*> ?: return null
    if (bounds.size != 2) return null
    val lower = finiteNumber(bounds[0]) ?: return null
    val upper = finiteNumber(bounds[1]) ?: return null
    if (lower !in 0.0..frequency || upper !in frequency..1.0) return null
    val events = (frequency * paths).roundToInt()
    if (abs(frequency * paths - events) > 0.000001 || (events == 0 && upper <= 0)) return null
    return ResearchScenario(events, paths, horizon, floor, lower, upper)
}

/** Counts describe the displayed subset, not completeness of investment due diligence. */
data class ResearchCoverage(val examined: Int, val total: Int, val issuers: Int) {
    val allPositionsIncluded: Boolean get() = examined == total
    val summary: String get() = "Разобрано $examined из $total позиций портфеля."
    val issuerSummary: String get() = "Компания установлена для $issuers из $examined разобранных позиций."
    val omittedWarning: String? get() = if (allPositionsIncluded) null else
        "Ещё ${total - examined} позиций не вошли в этот результат. Это не проверка всего портфеля."
}

fun researchCoverage(fields: Map<String, Any?>, displayedCards: Int): ResearchCoverage? {
    if (displayedCards !in 0..100) return null
    val examined = count(fields["examined_positions"], 0..100) ?: return null
    val total = count(fields["total_positions"], 0..Int.MAX_VALUE) ?: return null
    val issuers = count(fields["issuer_coverage_count"], 0..100) ?: return null
    if (examined != displayedCards || total < examined || issuers > examined) return null
    return ResearchCoverage(examined, total, issuers)
}
