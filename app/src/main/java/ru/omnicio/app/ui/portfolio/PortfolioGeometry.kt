package ru.omnicio.app.ui.portfolio

import java.math.BigDecimal
import java.math.MathContext
import java.time.Duration
import java.time.Instant

internal data class ChartSlice(val title: String, val weight: Float)
internal data class ChartFraction(val title: String, val fraction: Double)
internal data class HistoryPoint(val date: String, val value: BigDecimal)
internal data class HistoryCoordinate(val point: HistoryPoint, val x: Float, val y: Float)
internal data class HistoryGeometry(
    val coordinates: List<HistoryCoordinate>, val zero: Float,
    val high: BigDecimal, val low: BigDecimal,
)

/** Do not omit invalid/negative buckets and turn the remainder into a false 100%. */
internal fun portfolioFractions(slices: List<ChartSlice>): List<ChartFraction>? {
    if (slices.isEmpty() || slices.size > 10_000) return null
    if (slices.any { it.title.isBlank() || !it.weight.isFinite() || it.weight < 0 }) return null
    val total = slices.sumOf { it.weight.toDouble() }
    if (total <= 0 || !total.isFinite()) return null
    return slices.filter { it.weight > 0 }.map { ChartFraction(it.title, it.weight / total) }
}

private data class DatedPoint(val point: HistoryPoint, val instant: Instant)

private fun orderedHistory(points: List<HistoryPoint>): List<DatedPoint>? {
    if (points.size !in 2..10_000) return null
    if (points.any { it.date.length > 64 || it.value.precision() > 128 || it.value.scale() !in -128..128 }) return null
    val dated = try { points.map { DatedPoint(it, Instant.parse(it.date)) }.sortedBy { it.instant } }
        catch (_: java.time.DateTimeException) { return null }
    val result = ArrayList<DatedPoint>()
    for (item in dated) {
        val last = result.lastOrNull()
        if (last?.instant == item.instant) {
            if (last.point.value.compareTo(item.point.value) != 0) return null
        } else result.add(item)
    }
    return result.takeIf { it.size >= 2 }
}

private fun seconds(duration: Duration): BigDecimal = BigDecimal.valueOf(duration.seconds)
    .add(BigDecimal.valueOf(duration.nano.toLong(), 9))

private fun ratio(value: BigDecimal, total: BigDecimal): Float =
    value.divide(total, MathContext.DECIMAL64).toFloat().coerceIn(0f, 1f)

/** Exact source amounts remain intact; only drawing coordinates are normalized.
 * Invalid dates never become epoch zero. Equal-timestamp contradictions stop drawing.
 * Identical repeated observations are deduplicated; unordered input is sorted by time.
 */
internal fun portfolioHistory(points: List<HistoryPoint>): HistoryGeometry? {
    val dated = orderedHistory(points) ?: return null
    val high = dated.maxOf { it.point.value }.max(BigDecimal.ZERO)
    val low = dated.minOf { it.point.value }.min(BigDecimal.ZERO)
    val span = high.subtract(low)
    val first = dated.first().instant
    val duration = seconds(Duration.between(first, dated.last().instant))
    if (duration.signum() <= 0) return null
    val zero = if (span.signum() == 0) 1f else ratio(high, span)
    val coordinates = dated.map {
        val x = ratio(seconds(Duration.between(first, it.instant)), duration)
        val y = if (span.signum() == 0) zero else ratio(high.subtract(it.point.value), span)
        HistoryCoordinate(it.point, x, y)
    }
    return HistoryGeometry(coordinates, zero, high, low)
}

internal data class HistoryWindow(val page: Int, val pages: Int, val first: Int, val end: Int)
internal fun historyWindow(total: Int, requested: Int): HistoryWindow {
    require(total in 0..10_000)
    val pages = maxOf(1, (total + 9) / 10)
    val page = requested.coerceIn(0, pages - 1)
    return HistoryWindow(page, pages, page * 10, minOf(total, page * 10 + 10))
}

internal fun portfolioStackedLayout(widthDp: Float, fontScale: Float): Boolean =
    !widthDp.isFinite() || !fontScale.isFinite() || widthDp < 288f || fontScale >= 1.5f
