package ru.omnicio.app

import java.math.BigDecimal
import kotlin.math.abs
import ru.omnicio.app.ui.portfolio.*

internal fun runPortfolioGeometryChecks(): Int {
    var passed = 0
    fun verify(value: Boolean) { check(value); passed++ }
    val halves = portfolioFractions(listOf(ChartSlice("A", Float.MAX_VALUE), ChartSlice("B", Float.MAX_VALUE)))!!
    verify(halves.all { it.fraction == 0.5 })
    verify(portfolioFractions(emptyList()) == null)
    verify(portfolioFractions(listOf(ChartSlice("A", 0f))) == null)
    for (bad in listOf(-1f, Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY)) {
        verify(portfolioFractions(listOf(ChartSlice("A", 1f), ChartSlice("B", bad))) == null)
    }
    verify(portfolioFractions(listOf(ChartSlice(" ", 1f))) == null)
    val extremes = portfolioFractions(listOf(ChartSlice("A", Float.MIN_VALUE), ChartSlice("B", Float.MAX_VALUE)))!!
    verify(extremes.first().fraction > 0 && extremes.all { it.fraction.isFinite() })
    val parts = portfolioFractions(listOf(ChartSlice("A", 1f), ChartSlice("B", 2f), ChartSlice("C", 0f)))!!
    verify(abs(parts.sumOf { it.fraction } - 1.0) < 0.000001 && parts.size == 2)
    val a = HistoryPoint("2026-10-12T00:00:00Z", BigDecimal("100"))
    val b = HistoryPoint("2026-10-13T00:00:00Z", BigDecimal("200"))
    val model = portfolioHistory(listOf(b, a))!!
    verify(model.coordinates.map { it.point } == listOf(a, b))
    verify(model.coordinates.map { it.x } == listOf(0f, 1f))
    verify(model.coordinates.map { it.y } == listOf(0.5f, 0f) && model.zero == 1f)
    verify(portfolioHistory(listOf(a, a.copy(value = BigDecimal("100.0")), b))!!.coordinates.size == 2)
    verify(portfolioHistory(listOf(a, a.copy(value = BigDecimal("99")), b)) == null)
    verify(portfolioHistory(listOf(a, a)) == null)
    verify(portfolioHistory(listOf(a)) == null)
    verify(portfolioHistory(emptyList()) == null)
    verify(portfolioHistory(listOf(a.copy(date = "invalid"), b)) == null)
    verify(portfolioHistory(listOf(a.copy(date = "2026-10-12T00:00:00"), b)) == null)
    val nano = portfolioHistory(listOf(a, a.copy(date = "2026-10-12T00:00:00.000000001Z", value = BigDecimal("101"))))!!
    verify(nano.coordinates.last().x == 1f)
    val huge = portfolioHistory(listOf(a.copy(value = BigDecimal("1e100")), b.copy(value = BigDecimal("2e100"))))!!
    verify(huge.coordinates.map { it.y } == listOf(0.5f, 0f))
    val tiny = portfolioHistory(listOf(a.copy(value = BigDecimal("1e-100")), b.copy(value = BigDecimal("2e-100"))))!!
    verify(tiny.coordinates.map { it.y } == listOf(0.5f, 0f))
    val negative = portfolioHistory(listOf(a.copy(value = BigDecimal("-200")), b.copy(value = BigDecimal("200"))))!!
    verify(negative.zero == 0.5f && negative.coordinates.map { it.y } == listOf(1f, 0f))
    val zeros = portfolioHistory(listOf(a.copy(value = BigDecimal.ZERO), b.copy(value = BigDecimal.ZERO)))!!
    verify(zeros.coordinates.all { it.y == zeros.zero })
    verify(portfolioHistory(listOf(a.copy(value = BigDecimal("1e1000")), b)) == null)
    verify(portfolioHistory(List(10_001) { a }) == null)
    val original = listOf(b, a)
    portfolioHistory(original)
    verify(original == listOf(b, a))
    val middle = HistoryPoint("2026-10-12T06:00:00Z", BigDecimal("150"))
    verify(portfolioHistory(listOf(a, middle, b))!!.coordinates[1].x == 0.25f)
    for (total in listOf(0, 1, 9, 10, 11, 100, 10_000)) {
        val window = historyWindow(total, Int.MAX_VALUE)
        verify(window.end <= total && window.first <= window.end && window.end - window.first <= 10)
        verify(historyWindow(total, Int.MIN_VALUE).page == 0)
    }
    verify(runCatching { historyWindow(-1, 0) }.isFailure)
    verify(runCatching { historyWindow(10_001, 0) }.isFailure)
    verify(portfolioStackedLayout(280f, 1f))
    verify(portfolioStackedLayout(400f, 2f))
    verify(!portfolioStackedLayout(400f, 1f))
    verify(portfolioStackedLayout(0f, 1f))
    verify(portfolioStackedLayout(Float.NaN, 1f))
    return passed
}
