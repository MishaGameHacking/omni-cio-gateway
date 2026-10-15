package ru.omnicio.app.ui.portfolio

import java.math.MathContext

/** Reuses all timestamp, duplicate, precision and size validation of portfolioHistory.
 * Only line drawing coordinates use the observed range; exact source amounts are unchanged.
 * The renderer must display this range explicitly and retain the source-value table.
 */
internal fun portfolioLineHistory(points: List<HistoryPoint>): HistoryGeometry? {
    val validated = portfolioHistory(points) ?: return null
    val high = validated.coordinates.maxOf { it.point.value }
    val low = validated.coordinates.minOf { it.point.value }
    val span = high.subtract(low)
    val coordinates = validated.coordinates.map { coordinate ->
        val y = if (span.signum() == 0) .5f else high.subtract(coordinate.point.value)
            .divide(span, MathContext.DECIMAL64).toFloat().coerceIn(0f, 1f)
        coordinate.copy(y = y)
    }
    val zero = if (span.signum() == 0) {
        if (high.signum() >= 0) 1f else 0f
    } else high.divide(span, MathContext.DECIMAL64).toFloat().coerceIn(0f, 1f)
    return HistoryGeometry(coordinates, zero, high, low)
}
