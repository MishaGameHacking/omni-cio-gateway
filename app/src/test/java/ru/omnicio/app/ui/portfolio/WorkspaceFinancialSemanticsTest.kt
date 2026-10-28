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
    @Test fun refreshedPortfolioKeepsExistingRowsInPlaceAndAppendsNewPositions() {
        val original = listOf("account-a:bond", "account-b:share", "account-a:expired")
        val refreshed = listOf("account-b:new", "account-b:share", "account-a:bond", "account-a:new")
        assertEquals(listOf("account-a:bond", "account-b:share", "account-b:new", "account-a:new"),
            stablePortfolioRowKeys(original, refreshed))
        assertEquals(refreshed, stablePortfolioRowKeys(null, refreshed))
        assertEquals(refreshed, stablePortfolioRowKeys(emptyList(), refreshed))
        assertEquals(emptyList<String>(), stablePortfolioRowKeys(original, emptyList()))
        // Equal instrument IDs on different accounts are different positions.
        assertEquals(listOf("account-b:same", "account-a:same"),
            stablePortfolioRowKeys(listOf("account-b:same"), listOf("account-a:same", "account-b:same")))
    }

    private fun history(day: String, value: String) = HistoryPoint("${day}T12:00:00Z", BigDecimal(value))

    @Test fun derivativeClassesDoNotLeakIntoOtherAssetsOrTheCashFilter() {
        for (kind in listOf("futures", "option")) {
            assertTrue(matchingKind(kind, kind))
            assertTrue(matchingKind(kind, "all"))
            assertFalse(matchingKind(kind, "other"))
            assertFalse(matchingKind(kind, "cash"))
        }
        assertTrue(matchingKind("structured_product", "other"))
        assertTrue(matchingKind("currency", "cash"))
        assertFalse(matchingKind("currency", "other"))
    }

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

    @Test fun anEvidenceInstantResolvesTheObservationAndNeverAnotherBalanceOnTheSameDay() {
        assertTrue(sameHistoryInstant("2026-10-01T12:00:00Z", "2026-10-01T15:00:00+03:00"))
        assertFalse(sameHistoryInstant("2026-10-01T12:00:00Z", "2026-10-01T15:00:01+03:00"))
        assertFalse(sameHistoryInstant("2026-10-01T12:00:00Z", "2026-10-01"))
    }

    @Test fun barAndTableSelectionShareTheExactClosingObservationWithoutSubstitutingMissingEvidence() {
        val earlier = HistoryPoint("2026-10-01T10:00:00Z", BigDecimal("101.25"))
        val close = HistoryPoint("2026-10-01T18:00:00Z", BigDecimal("901.75"))
        val later = HistoryPoint("2026-10-03T18:00:00Z", BigDecimal("500.00"))
        val daily = historyBars(listOf(earlier, close, later), "day")!!
        assertEquals(close, historySelectedObservation(daily, 0, null))
        assertEquals(earlier, historySelectedObservation(daily, 0, "2026-10-01T13:00:00+03:00"))
        assertNull(historySelectedObservation(daily, 0, "2026-10-01T11:00:00Z"))
        assertNull(historySelectedObservation(daily, 1, null))
        assertNull(historySelectedObservation(daily, -1, null))
        val monthly = historyBars(listOf(earlier, close, later), "month")!!
        assertEquals(later, historySelectedObservation(monthly, 0, null))
        assertEquals(earlier, historySelectedObservation(monthly, 0, earlier.date))
    }

    @Test fun restoredRangeDatesStayInsideTheSelectedBucketsAfterGroupingChanges() {
        val points = listOf(history("2026-10-01", "100"), history("2026-10-31", "105"))
        val start = LocalDate.parse("2026-10-13")
        val end = LocalDate.parse("2026-10-23")
        for (grouping in listOf("day", "week", "month")) {
            val bars = historyBars(points, grouping)!!.bars
            val indices = historyRangeIndices(bars, start.toString(), end.toString())
            assertTrue(start in bars[indices.first].start..bars[indices.first].end)
            assertTrue(end in bars[indices.last].start..bars[indices.last].end)
        }
    }

    @Test fun rangeDatesOutsideTheReceivedSeriesClampWithoutInventingObservations() {
        val bars = historyBars(listOf(history("2026-10-10", "100"), history("2026-10-20", "101")), "day")!!.bars
        assertEquals(0..bars.lastIndex, historyRangeIndices(bars, "2026-01-01", "2026-12-31"))
        assertEquals(0..0, historyRangeIndices(bars, "2026-01-01", "2026-01-02"))
        assertEquals(bars.lastIndex..bars.lastIndex, historyRangeIndices(bars, "2026-12-01", "2026-12-02"))
    }

    @Test fun reportPublicationRequiresASeparateDatedSourceAndHonorsAnExplicitUnconfirmedFlag() {
        assertEquals(ReportPublicationState.Scheduled, reportPublicationState("scheduled", false, true))
        assertEquals(ReportPublicationState.Unconfirmed, reportPublicationState("published", false, true))
        assertEquals(ReportPublicationState.Unconfirmed, reportPublicationState("published", true, false))
        assertEquals(ReportPublicationState.Published, reportPublicationState("published", null, true))
    }

    @Test fun reportDatesUseMoscowCalendarForInstantsAndPreserveSourceCalendarDates() {
        assertEquals(LocalDate.parse("2026-10-02"), reportCalendarDate("2026-10-01T22:30:00Z"))
        assertEquals(LocalDate.parse("2026-10-01"), reportCalendarDate("2026-10-01"))
        assertNull(reportCalendarDate("не опубликовано"))
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

    @Test fun aConflictOnlyInAnAdditionalFundamentalFieldRemainsVisibleAlongsideNamedMetrics() {
        val named = setOf("revenueTtm", "netIncomeTtm", "freeCashFlowTtm", "netDebtToEbitda", "currentRatioMrq")
        val first: Map<String, Any?> = named.associateWith { "12.5" } + mapOf(
            "currency" to "RUB", "fiscalPeriodEndDate" to "2026-06-30T00:00:00Z",
            "ebitdaTtm" to "20.000000001", "unconfirmedExtra" to null)
        val second = first + ("ebitdaTtm" to "40.000000001")
        val firstVisible = additionalConflictFields(first, named)
        val secondVisible = additionalConflictFields(second, named)
        assertEquals(setOf("ebitdaTtm", "unconfirmedExtra"), firstVisible.keys)
        assertEquals("20.000000001", firstVisible["ebitdaTtm"])
        assertEquals("40.000000001", secondVisible["ebitdaTtm"])
        assertNotEquals(firstVisible, secondVisible)
        assertTrue(firstVisible.containsKey("unconfirmedExtra"))
        assertNull(firstVisible["unconfirmedExtra"])
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

    @Test fun restoredPaymentIdentityCannotMatchAnotherUserAccountOrCalendarEvent() {
        val selected = paymentSelectionKey("user-a", "account-a", "paper", "coupon", "2026-11-01", "2026-10-20")
        assertNotNull(selected)
        assertNotEquals(selected, paymentSelectionKey("user-b", "account-a", "paper", "coupon", "2026-11-01", "2026-10-20"))
        assertNotEquals(selected, paymentSelectionKey("user-a", "account-b", "paper", "coupon", "2026-11-01", "2026-10-20"))
        assertNotEquals(selected, paymentSelectionKey("user-a", "account-a", "paper", "coupon", "2026-12-01", "2026-10-20"))
        assertNotEquals(selected, paymentSelectionKey("user-a", "account-a", "paper", "dividend", "2026-11-01", "2026-10-20"))
        assertNotNull(paymentSelectionKey("user-a", "account-a", "paper", "coupon", null, null))
        assertNull(paymentSelectionKey("user-a", "account-a", null, "coupon", null, null))
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
