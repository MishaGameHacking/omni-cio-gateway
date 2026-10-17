package ru.omnicio.app.ui.portfolio

import java.math.BigDecimal
import java.time.LocalDate
import org.junit.Assert.*
import org.junit.Test
import ru.omnicio.app.data.market.CandleSnapshot
import ru.omnicio.app.data.market.MarketCandle
import ru.omnicio.app.data.portfolio.ApiDecimal
import ru.omnicio.app.data.portfolio.MoneyAmount
import ru.omnicio.app.data.portfolio.PortfolioAccount
import ru.omnicio.app.data.portfolio.PortfolioPosition

/** Financial contracts: no invented observations, incompatible comparisons or stale cross-account values. */
class WorkspaceFinancialSemanticsTest {
    private fun history(day: String, value: String) = HistoryPoint("${day}T12:00:00Z", BigDecimal(value))

    @Test fun dailyHistoryKeepsAnUnobservedDateSelectableWithoutInventingZero() {
        val result = historyBars(listOf(history("2026-10-01", "100.25"), history("2026-10-03", "105.75")), "day")!!
        assertEquals(3, result.bars.size)
        val gap = result.bars[1]
        assertEquals(LocalDate.parse("2026-10-02"), gap.start)
        assertEquals("2026-10-02", gap.period.end)
        assertNull(gap.close)
        assertEquals(BigDecimal("105.75"), result.bars.last().close!!.value)
    }

    @Test fun monthlyBalanceUsesTheLastObservationRatherThanAddingBalances() {
        val result = historyBars(listOf(history("2026-10-01", "100.25"), history("2026-10-31", "-20.50"),
            history("2026-11-01", "400.00")), "month")!!
        assertEquals(2, result.bars.size)
        assertEquals(BigDecimal("-20.50"), result.bars.first().close!!.value)
        assertEquals(BigDecimal("-20.50"), result.source.low)
        assertEquals(BigDecimal("400.00"), result.bars.last().close!!.value)
    }

    @Test fun aSelectedCalendarDateRemainsInsideItsDayWeekAndMonthBuckets() {
        val source = listOf(history("2026-10-01", "100"), history("2026-10-31", "105"))
        val selectedDate = LocalDate.parse("2026-10-14")
        for (grouping in listOf("day", "week", "month")) {
            val result = historyBars(source, grouping)!!
            assertEquals(1, result.bars.count { selectedDate in it.start..it.end })
        }
    }

    @Test fun conflictingValuesAtTheSameInstantStopHistoryEvenWithDifferentOffsets() {
        val result = historyBars(listOf(HistoryPoint("2026-10-01T12:00:00Z", BigDecimal("100")),
            HistoryPoint("2026-10-01T15:00:00+03:00", BigDecimal("101"))), "day")
        assertNull(result)
    }

    private fun candle(day: Int, price: String, complete: Boolean = true): MarketCandle {
        val value = BigDecimal(price)
        return MarketCandle("2026-10-${day.toString().padStart(2, '0')}T00:00:00Z", value, value, value, value,
            BigDecimal.TEN, complete, "verified-source")
    }

    private fun series(uid: String = "a", unit: String? = "quote_currency", currency: String? = "RUB",
        candles: List<MarketCandle> = listOf(candle(1, "100"), candle(2, "105")),
        state: String = "available", interval: String = "day") = CandleSnapshot(uid, interval,
        "2026-10-01", "2026-10-10", "2026-10-11T00:00:00Z", currency ?: "единица", currency,
        state, null, candles, emptyList(), emptyList(), unit)

    @Test fun comparisonUsesOnlySharedCompleteClosings() {
        val first = series(candles = listOf(candle(1, "99"), candle(2, "100.25"), candle(3, "110", false), candle(4, "105.75")))
        val second = series("b", candles = listOf(candle(2, "200.50"), candle(3, "202"), candle(4, "205.50"), candle(5, "207")))
        val result = comparableQuotePeriod(listOf(first, second))!!
        assertEquals("2026-10-02T00:00:00Z", result.start)
        assertEquals("2026-10-04T00:00:00Z", result.end)
        assertEquals(listOf(BigDecimal("100.25"), BigDecimal("200.50")), result.openings)
        assertEquals(listOf(BigDecimal("105.75"), BigDecimal("205.50")), result.closings)
    }

    @Test fun priceUnitsCurrenciesAndIntervalsMustBeVerifiedAndCompatible() {
        assertNull(comparableQuotePeriod(listOf(series(), series("b", currency = "USD"))))
        assertNull(comparableQuotePeriod(listOf(series(unit = "points", currency = null), series("b", unit = "percent_of_nominal", currency = null))))
        assertNull(comparableQuotePeriod(listOf(series(unit = null), series("b", unit = null))))
        assertNull(comparableQuotePeriod(listOf(series(unit = "quote_units", currency = null), series("b", unit = "quote_units", currency = null))))
        assertNull(comparableQuotePeriod(listOf(series(currency = null), series("b", currency = null))))
        assertNull(comparableQuotePeriod(listOf(series(), series("b", interval = "hour"))))
        assertNotNull(comparableQuotePeriod(listOf(series(unit = "percent_of_nominal", currency = null), series("b", unit = "percent_of_nominal", currency = null))))
    }

    @Test fun unavailableOrInsufficientCommonObservationsNeverProduceAComparison() {
        assertNull(comparableQuotePeriod(listOf(series(), series("b", state = "unavailable"))))
        assertNull(comparableQuotePeriod(listOf(series(), series("b", candles = listOf(candle(1, "100"), candle(2, "105", false))))))
        assertNull(comparableQuotePeriod(listOf(series(), series("b", candles = listOf(candle(2, "105"), candle(3, "106"))))))
    }

    private fun money(units: Long, currency: String = "RUB") = MoneyAmount(ApiDecimal(units, 0), currency)
    private fun position(uid: String, amount: Long, currency: String = "RUB") = PortfolioPosition(uid, "Одинаковое название",
        "SAME", ApiDecimal(1, 0), money(amount, currency), null, instrumentType = "share")
    private fun account(id: String, positions: List<PortfolioPosition>) = PortfolioAccount(id, "Счёт $id", money(1000), null, positions)

    @Test fun selectedPositionResolvesTheCurrentAccountAndRefusesAmbiguousOrRemovedRows() {
        val selected = PositionSelection("account-a", "paper")
        fun resolve(accounts: List<PortfolioAccount>) = resolveSelectedPosition(selected, accounts, PortfolioAccount::id,
            { account, virtual -> if (virtual) account.virtualPositions else account.positions }, PortfolioPosition::id)
        val latest = position("paper", 222)
        assertSame(latest, resolve(listOf(account("account-a", listOf(latest)), account("account-b", listOf(position("paper", 999))))))
        assertNull(resolve(listOf(account("account-a", emptyList()), account("account-b", listOf(latest)))))
        assertNull(resolve(listOf(account("account-a", listOf(latest, latest)))))
        assertNull(resolve(listOf(account("account-a", listOf(latest)), account("account-a", listOf(latest)))))
    }

    @Test fun equalValuationsSortByStableIdentityAndForeignCurrencyIsNotRankedAsRubles() {
        val a = account("a", listOf(position("two", 100), position("one", 100)))
        val b = account("b", listOf(position("one", 100), position("foreign", 9000, "USD")))
        val rows = listOf(b, a).flatMap { account -> account.positions.map { PortfolioRow(account, it) } }
        val expected = listOf("a:one", "a:two", "b:one", "b:foreign")
        assertEquals(expected, sortedPortfolioRows(rows, 1, "RUB").map(::portfolioRowKey))
        assertEquals(expected, sortedPortfolioRows(rows.reversed(), 1, "RUB").map(::portfolioRowKey))
    }
}
