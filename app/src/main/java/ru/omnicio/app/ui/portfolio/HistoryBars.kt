package ru.omnicio.app.ui.portfolio

import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.temporal.ChronoUnit

internal data class HistoryBar(val start: LocalDate, val end: LocalDate, val points: List<HistoryPoint>) {
    val close: HistoryPoint? get() = points.lastOrNull()
    val period: PortfolioPeriod get() = PortfolioPeriod(start.toString(), end.toString())
}

internal data class HistoryBars(val bars: List<HistoryBar>, val source: HistoryGeometry, val interval: String)

/** Calendar buckets in the same Moscow timezone as the analytics endpoint.
 * The bar is the LAST observed balance, never a sum/average of account balances.
 * Missing buckets stay empty, and exact source amounts survive aggregation.
 */
internal fun historyBars(points: List<HistoryPoint>, grouping: String = "auto"): HistoryBars? {
    val source = portfolioHistory(points) ?: return null
    val ordered = source.coordinates.map { it.point }
    fun day(point: HistoryPoint) = Instant.parse(point.date).atZone(Moscow).toLocalDate()
    val first = day(ordered.first())
    val last = day(ordered.last())
    val days = ChronoUnit.DAYS.between(first, last)
    if (days > 36600) return null
    val unit = when (grouping) {
        "day" -> ChronoUnit.DAYS; "week" -> ChronoUnit.WEEKS; "month" -> ChronoUnit.MONTHS
        else -> when { days < 35 -> ChronoUnit.DAYS; days < 224 -> ChronoUnit.WEEKS; days < 1095 -> ChronoUnit.MONTHS; else -> ChronoUnit.YEARS }
    }
    if (unit == ChronoUnit.DAYS && days > 730 || unit == ChronoUnit.WEEKS && days > 5110) return null
    val count = if (unit == ChronoUnit.YEARS) maxOf(1L, (last.year - first.year + 31L) / 32L) else 1L
    var start = when (unit) { ChronoUnit.MONTHS -> first.withDayOfMonth(1); ChronoUnit.YEARS -> first.withDayOfYear(1); else -> first }
    val bars = mutableListOf<HistoryBar>()
    var cursor = 0
    while (start <= last) {
        val next = start.plus(count, unit)
        val values = mutableListOf<HistoryPoint>()
        while (cursor < ordered.size && day(ordered[cursor]) < next) values.add(ordered[cursor++])
        bars.add(HistoryBar(maxOf(start, first), minOf(next.minusDays(1), last), values))
        start = next
    }
    val interval = when (unit) { ChronoUnit.DAYS -> "день"; ChronoUnit.WEEKS -> "неделя"; ChronoUnit.MONTHS -> "месяц"; else -> if (count == 1L) "год" else "$count года" }
    return HistoryBars(bars, source, interval)
}

internal fun historyBarIndex(x: Float, width: Float, count: Int): Int {
    require(count > 0 && width.isFinite() && width > 0 && x.isFinite())
    return ((x / width) * count).toInt().coerceIn(0, count - 1)
}

internal fun historyChange(points: List<HistoryPoint>): BigDecimal? =
    if (points.size < 2) null else points.last().value.subtract(points.first().value)

